"""统一 KB 检索层（data-plan M3/M4 · D-R3）。

三栈收敛为"SQLite FTS5 粗召回 + 现行公式精排"：
  - knowledge_base 栈（packing_assistant.tools.search_knowledge，90 篇 md）
  - demo/kb 栈（demo.rag.search_kb，66 岗三层 346 篇 md）
共用同一 data/civilbuddy.db 里 kb_index/kb_chunks/kb_fts 三张表（schema 见 storage.py，
M1 已建好）；精排公式各自保留原实现（search_knowledge._score / demo.rag scan），
本层只负责候选召回与索引构建/新鲜度，公式逻辑零改动（金句不退步为硬约束）。

分词方案（audit C1 结论）：FTS5 unicode61 tokenizer + 入库文本预切 CJK bigram
（空格连接）；查询侧同切法。2 字中文查询=1 个 bigram token 精确命中；
不用 trigram tokenizer（对 2 字查询不走索引）。

开关 CB_RAG=json|fts（默认 fts）：json 走各栈旧全盘扫描路径（与 14ec2bd 等价）；
fts 模式任何异常自动回退扫描路径并打 WARNING。Rust workbench 只读同一 kb_fts
（workbench/src/kbstore.rs），CB_RUST_RAG=scan 保留旧扫描回退。

索引构建：rebuild_index(full=False) 增量（mtime+size 判据）/ --rebuild 全量；
写钩子 demo/kbio.py 落盘后即时 upsert（reindex_kb_file）；查询侧每 30s 一次
新鲜度检查（stat 对比），兜住绕过写钩子的改动（如 workbench/Rust 写盘）。
"""

from __future__ import annotations

import logging
import os
import re
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from packing_assistant.storage import Storage, get_storage

logger = logging.getLogger("civil.kb_search")

REPO_ROOT = Path(__file__).resolve().parents[1]
DEMO_KB_ROOT = REPO_ROOT / "demo" / "kb"
KB_ROOT = REPO_ROOT / "knowledge_base"

# 候选召回上限：FTS OR 召回按 bm25 rank 截断；knowledge_base 90 篇几乎全覆盖
_FTS_CAND_CAP = 220
_KB_FTS_CAND_CAP = 250
_FRESH_INTERVAL_S = 30.0

_WORD_OR_CJK = re.compile(r"[a-z0-9_]+|[\u4e00-\u9fff]+")
_CJK_ONLY = re.compile(r"[\u4e00-\u9fff]+$")
_DEMO_TOKEN_RE = re.compile(r"[\u4e00-\u9fff]{2,}|[A-Za-z0-9_\-]{2,}")

_LAST_FRESH_CHECK = 0.0


# ---------- 开关与分词 ----------

def rag_mode() -> str:
    """CB_RAG=json|fts（默认 fts；非法值回落 fts）。"""
    raw = (os.getenv("CB_RAG") or "fts").strip().lower()
    return raw if raw in ("json", "fts") else "fts"


def bigram_text(text: str) -> str:
    """入库文本：CJK 切 bigram + 英文/数字词，空格连接（unicode61 直接可分）。"""
    text = text.lower()
    out: List[str] = []
    for p in _WORD_OR_CJK.findall(text):
        if _CJK_ONLY.match(p):
            if len(p) < 2:
                continue
            for i in range(len(p) - 1):
                out.append(p[i : i + 2])
        else:
            out.append(p)
    return " ".join(out)


def fts_match_string(q_tokens: List[str]) -> str:
    """查询文本同切法 → FTS5 MATCH 串（OR 召回，精排交给现行公式）。"""
    terms: List[str] = []
    seen: Set[str] = set()
    for t in q_tokens:
        t = str(t or "").lower().strip()
        if not t:
            continue
        if _CJK_ONLY.match(t):
            if len(t) < 2:
                continue  # 单字查询无 bigram；调用方零召回时回退全量打分
            cands = [f'"{t[i : i + 2]}"' for i in range(len(t) - 1)]
        else:
            cands = [f'"{t}"']  # 引号包裹：search_knowledge 等含 _ 词按相邻 phrase 命中
        for c in cands:
            if c not in seen:
                seen.add(c)
                terms.append(c)
    return " OR ".join(terms)


def demo_tokens(query: str) -> List[str]:
    """demo/rag._tokens 同款（整段 CJK 串 / 字母数字串，≥2 字符）。"""
    return _DEMO_TOKEN_RE.findall((query or "").lower())


# ---------- 文件盘点与元数据 ----------

def scan_kb_files() -> Dict[str, Dict[str, Tuple[int, int]]]:
    """磁盘盘点 {kb: {rel_posix: (mtime_int, size)}}。demo_kb=md+txt，knowledge_base=md。"""
    disk: Dict[str, Dict[str, Tuple[int, int]]] = {"demo_kb": {}, "knowledge_base": {}}
    if DEMO_KB_ROOT.is_dir():
        for p in DEMO_KB_ROOT.rglob("*"):
            if p.is_file() and p.suffix.lower() in (".md", ".txt"):
                rel = p.relative_to(DEMO_KB_ROOT).as_posix()
                stt = p.stat()
                disk["demo_kb"][rel] = (int(stt.st_mtime), stt.st_size)
    if KB_ROOT.is_dir():
        for p in KB_ROOT.rglob("*.md"):
            rel = p.relative_to(KB_ROOT).as_posix()
            stt = p.stat()
            disk["knowledge_base"][rel] = (int(stt.st_mtime), stt.st_size)
    return disk


def _demo_meta(rel: str) -> Tuple[str, Optional[str], Optional[str]]:
    """demo/kb 路径 → (layer, category, expert_id)。与旧 kb_layers 三根一致：
    expert=<category>/<expert_id>/，category=<category>/_shared/，company=company/；
    其余（docs/ 顶层、散落文件）打标记且不进任何专家检索范围（旧行为不可见）。"""
    parts = rel.split("/")
    if parts[0] == "company":
        return ("company", None, None)
    if len(parts) >= 3 and parts[1] == "_shared":
        return ("category", parts[0], None)
    if len(parts) >= 3:
        return ("expert", parts[0], parts[1])
    if len(parts) == 2 and parts[1] == "_shared":
        return ("category", parts[0], None)
    return ("other", parts[0] if len(parts) > 1 else None, None)


_TITLE_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)


def _extract_title(raw_text: str, stem: str) -> str:
    m = _TITLE_RE.search(raw_text)
    return m.group(1).strip() if m else stem


_HEADING_LINE = re.compile(r"^#{1,6}(\s|$)")


def _split_chunks(raw_text: str) -> List[Tuple[Optional[str], str]]:
    """md 按标题行分节；每节 body 为原文的精确切片（含标题行本身），
    "".join(body) == raw_text（无损，供 Rust 侧拼回全文做短语加分）。"""
    lines = raw_text.splitlines(keepends=True)
    chunks: List[Tuple[Optional[str], str]] = []
    cur_head: Optional[str] = None
    buf: List[str] = []
    for ln in lines:
        if _HEADING_LINE.match(ln):
            if buf:
                chunks.append((cur_head, "".join(buf)))
            cur_head = ln.lstrip("#").strip()[:120] or None
            buf = [ln]
        else:
            buf.append(ln)
    if buf:
        chunks.append((cur_head, "".join(buf)))
    return chunks or [("", raw_text)]


def _parse_kb_frontmatter(raw: str) -> dict:
    from packing_assistant.tools.search_knowledge import _parse_frontmatter

    fm, _ = _parse_frontmatter(raw)
    return fm if isinstance(fm, dict) else {}


# ---------- 索引构建 ----------

def _boost_rules() -> List[dict]:
    """rag.rs 5 处硬编码 boost 的数据化（audit A3-1）。无条件项进 kb_index.boost；
    sg 查询条件惩罚为查询侧规则，导出 contract/kb_boosts.v1.json 供 Rust 读取。"""
    return [
        {"id": "web_knowledge", "kind": "filename_eq", "value": "web-knowledge.md",
         "boost": 6.0, "scope": "demo_kb", "note": "联网核对要点文件加权"},
        {"id": "web_portals", "kind": "filename_eq", "value": "web-portals.md",
         "boost": 5.0, "scope": "demo_kb", "note": "官方门户文件加权"},
        {"id": "content_2026_08_14", "kind": "body_contains", "value": "2026-08-14",
         "boost": 1.5, "scope": "demo_kb", "note": "口径更新日期加权（rag.rs 只扫 demo/kb，随源迁移）"},
        {"id": "content_appbca_2026_12", "kind": "body_contains", "value": "APPBCA-2026-12",
         "boost": 2.0, "scope": "demo_kb", "note": "APPBCA 规范加权（同上）"},
        {"id": "sg_order37_penalty", "kind": "sg_query_penalty",
         "match_filename": "order-37", "match_body": "37 号令永远标 CN",
         "boost": -10.0, "note": "新加坡类 query 对中国 37 号令惩罚（查询侧条件）"},
    ]


def write_boost_contract() -> Path:
    import json

    out = REPO_ROOT / "contract" / "kb_boosts.v1.json"
    payload = {
        "version": "kb_boosts.v1",
        "generated_by": "packing_assistant.kb_search（build_kb_index 同源）",
        "rules": _boost_rules(),
    }
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out


def _compute_boost(kb: str, rel: str, raw_text: str) -> float:
    total = 0.0
    name = rel.rsplit("/", 1)[-1].lower()
    for r in _boost_rules():
        if r["kind"] == "filename_eq":
            if (not r.get("scope") or r["scope"] == kb) and name == r["value"]:
                total += float(r["boost"])
        elif r["kind"] == "body_contains" and r["value"] in raw_text:
            total += float(r["boost"])
    return total


def _doc_row(kb: str, rel: str, abs_path: Path, raw_text: str,
             title_resolver: Optional[Callable[[Path, str], str]] = None) -> Tuple[dict, List[dict]]:
    stt = abs_path.stat()
    stem = abs_path.stem
    if kb == "demo_kb":
        layer, category, expert_id = _demo_meta(rel)
        title = stem
        display = title_resolver(abs_path, raw_text) if title_resolver else _extract_title(raw_text, stem)
        priority, tags_json, status = "medium", "[]", "active"
        fm: dict = {}
    else:
        layer, category, expert_id = None, None, None
        fm = _parse_kb_frontmatter(raw_text)
        title = _extract_title(re.sub(r"^---\s*\n.*?\n---\s*\n", "", raw_text, count=1, flags=re.DOTALL), stem)
        display = title
        priority = str(fm.get("priority") or "medium").lower()
        tags = fm.get("tags") or []
        if isinstance(tags, str):
            tags = [tags]
        import json as _json

        tags_json = _json.dumps([str(t) for t in tags], ensure_ascii=False)
        status = str(fm.get("status") or "active").lower()
    boost = _compute_boost(kb, rel, raw_text)
    doc = {
        "kb": kb, "path": rel, "title": title, "display": display,
        "layer": layer, "category": category, "expert_id": expert_id,
        "priority": priority, "tags_json": tags_json, "status": status,
        "mtime": datetime.fromtimestamp(int(stt.st_mtime)).isoformat(timespec="microseconds"),
        "size": stt.st_size,
        "hash": _sha1(raw_text.encode("utf-8", errors="ignore")),
        "boost": boost,
    }
    chunks: List[dict] = []
    if abs_path.suffix.lower() == ".md":
        pieces = _split_chunks(raw_text)
    else:
        pieces = [(None, raw_text)]
    fm_blob = " ".join(str(v) for v in fm.values()) if fm else ""
    for i, (head, body) in enumerate(pieces):
        big = bigram_text(body)
        if i == 0:
            # 首节折叠 title + frontmatter 值（旧 token_set 覆盖 title/fm/tags 命中）
            extras = bigram_text(f"{title} {fm_blob}")
            if extras:
                big = f"{big} {extras}".strip()
        chunks.append({"heading": head, "seq": i, "body": body, "body_bigrams": big})
    return doc, chunks


def _sha1(data: bytes) -> str:
    import hashlib

    return hashlib.sha1(data).hexdigest()


def _read_text(abs_path: Path) -> str:
    return abs_path.read_text(encoding="utf-8", errors="ignore")


def reindex_kb_file(rel: str, *, kb: str = "demo_kb",
                    title_resolver: Optional[Callable[[Path, str], str]] = None) -> bool:
    """写钩子入口：单文件 upsert（写盘后即时可检索）；文件已消失则删除行。"""
    rel = str(rel or "").replace("\\", "/").lstrip("/")
    if not rel or ".." in rel.split("/"):
        return False
    root = DEMO_KB_ROOT if kb == "demo_kb" else KB_ROOT
    abs_path = root / rel
    st = get_storage()
    try:
        if abs_path.is_file() and abs_path.suffix.lower() in (".md", ".txt"):
            raw = _read_text(abs_path)
            doc, chunks = _doc_row(kb, rel, abs_path, raw, title_resolver)
            st.kb_upsert_doc(doc, chunks)
            return True
        return st.kb_delete_doc(kb, rel)
    except Exception:
        logger.warning("kb_index 单文件重建失败 kb=%s path=%s", kb, rel, exc_info=True)
        return False


def rebuild_index(full: bool = False, *,
                  title_resolver: Optional[Callable[[Path, str], str]] = None,
                  storage: Optional[Storage] = None) -> dict:
    """增量（mtime+size 判据）或全量（--rebuild）索引构建。返回统计。"""
    global _LAST_FRESH_CHECK
    st = storage or get_storage()
    t0 = time.time()
    disk = scan_kb_files()
    if full:
        for kb in disk:
            st.kb_clear(kb)
    stats: Dict[str, object] = {}
    for kb, files in disk.items():
        existing = st.kb_indexed(kb)  # {path: (mtime_iso, size)}
        added = updated = unchanged = removed = 0
        for rel, (mtime, size) in sorted(files.items()):
            iso = datetime.fromtimestamp(mtime).isoformat(timespec="microseconds")
            old = existing.get(rel)
            if old and old[1] == size and old[0] == iso:
                unchanged += 1
                continue
            raw = _read_text(DEMO_KB_ROOT / rel if kb == "demo_kb" else KB_ROOT / rel)
            doc, chunks = _doc_row(kb, rel, DEMO_KB_ROOT / rel if kb == "demo_kb" else KB_ROOT / rel,
                                   raw, title_resolver)
            st.kb_upsert_doc(doc, chunks)
            if old:
                updated += 1
            else:
                added += 1
        on_disk = set(files)
        for rel in set(existing) - on_disk:
            st.kb_delete_doc(kb, rel)
            removed += 1
        stats[kb] = {"total": len(files), "added": added, "updated": updated,
                     "unchanged": unchanged, "removed": removed}
    _LAST_FRESH_CHECK = time.time()
    stats["elapsed_s"] = round(time.time() - t0, 3)
    stats["kb_index_rows"] = st.count("kb_index")
    stats["kb_chunks_rows"] = st.count("kb_chunks")
    stats["kb_fts_rows"] = st.count("kb_fts")
    return stats


def index_is_stale(storage: Optional[Storage] = None) -> bool:
    """kb_index 与磁盘 mtime/size 对比（写钩子兜底 + CI --check 判据）。"""
    st = storage or get_storage()
    disk = scan_kb_files()
    for kb, files in disk.items():
        existing = st.kb_indexed(kb)
        if len(existing) != len(files):
            return True
        for rel, (mtime, size) in files.items():
            old = existing.get(rel)
            if not old or old[1] != size or old[0] != datetime.fromtimestamp(mtime).isoformat(timespec="microseconds"):
                return True
    return False


def ensure_index_fresh(storage: Optional[Storage] = None) -> None:
    """查询前新鲜度保障：30s 节流 stat 对比，变化即毫秒级增量重建。"""
    global _LAST_FRESH_CHECK
    now = time.time()
    if now - _LAST_FRESH_CHECK < _FRESH_INTERVAL_S:
        return
    _LAST_FRESH_CHECK = now
    try:
        if index_is_stale(storage):
            stats = rebuild_index(storage=storage)
            logger.info("kb_index 检测到过期，已增量重建: %s", stats)
    except Exception:
        logger.warning("kb_index 新鲜度检查失败（检索继续用现有索引）", exc_info=True)


# ---------- 候选召回 ----------

def _fts_candidate_paths(match: str, kb: str, cap: int) -> List[str]:
    st = get_storage()
    conn = st.read_conn()
    rows = conn.execute(
        "SELECT path FROM kb_fts WHERE kb_fts MATCH ? AND kb=? ORDER BY rank LIMIT ?",
        (match, kb, int(cap)),
    ).fetchall()
    return [r[0] for r in rows]


def _path_like_candidates(q_tokens: List[str], kb: str) -> List[str]:
    """路径/文件名子串命中也必须进候选（旧实现 path 子串 +1.2 / 文件名 +3.0 加分项）。"""
    toks = [t for t in q_tokens if t and len(t) >= 2][:8]
    if not toks:
        return []
    st = get_storage()
    conds = " OR ".join("path LIKE ?" for _ in toks)
    args = [kb] + [f"%{t}%" for t in toks]
    rows = st.read_conn().execute(
        f"SELECT DISTINCT path FROM kb_index WHERE kb=? AND ({conds}) LIMIT 400", args
    ).fetchall()
    return [r[0] for r in rows]


def kb_candidates(q_tokens: List[str], *, kb: str, cap: int) -> Optional[Set[str]]:
    """FTS OR 召回 ∪ 路径子串命中。返回 None = 索引不可用/零召回（调用方全量打分兜底）。"""
    try:
        ensure_index_fresh()
        match = fts_match_string(q_tokens)
        if not match:
            return None
        n_terms = 1 + match.count(" OR ")
        paths = _fts_candidate_paths(match, kb, cap)
        if not paths:
            return None  # 零召回：全量打分（与旧实现等价，常见于 1 字/极端查询）
        paths.extend(_path_like_candidates(q_tokens, kb))
        cand = set(paths)
        logger.info("kb_search FTS 召回 kb=%s terms=%d candidates=%d", kb, n_terms, len(cand))
        return cand
    except sqlite3.Error:
        logger.warning("kb_fts 召回失败（%s），回退全量打分", kb, exc_info=True)
        return None


def demo_candidates(expert_id: str, category: str, query: str) -> Optional[Set[str]]:
    """demo/kb 栈候选（老 search_kb 全盘扫描 → 仅对候选打分）。"""
    toks = demo_tokens(query)
    if not toks:
        return set()  # 旧实现 q 空直接返回 []
    return kb_candidates(toks, kb="demo_kb", cap=_FTS_CAND_CAP)


def knowledge_search_fts(
    q: str,
    *,
    category: Optional[str] = None,
    priority: Optional[str] = None,
    tags: Optional[List[str]] = None,
    limit: int = 5,
    path_prefixes: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """knowledge_base 栈 FTS 路径：粗召回候选 → search_knowledge 现行公式精排
    （公式与响应 schema 逐字保留，见 search_knowledge._search_knowledge_scan）。"""
    from packing_assistant.tools.search_knowledge import _search_knowledge_scan, _tokenize

    q_tokens = _tokenize(q or "")
    cands: Optional[Set[str]] = None
    if q_tokens:
        cands = kb_candidates(q_tokens, kb="knowledge_base", cap=_KB_FTS_CAND_CAP)
    return _search_knowledge_scan(
        q, category=category, priority=priority, tags=tags,
        limit=limit, path_prefixes=path_prefixes, _candidate_paths=cands,
    )
