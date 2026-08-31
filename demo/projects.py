"""ux(round19) 项目 / 会话索引 —— Python 参考实现，Rust 侧 workbench/src/projects.rs 的镜像。

契约单源：``contract/projects.v1.json``（schema 名、保留 id、上限、字段清单）。
两侧都是消费者，不许各留一份手工副本 —— 与 ``contract/intents.v1.json`` 同一套纪律。

**评委下载的是 Rust exe，不跑这份。** 但两个 :8765 后端已经分叉过一次
（Python 有 /api/threads 无 /api/harness/*，Rust 反过来），不补镜像分叉只会继续扩大。
行为差异由 ``scripts/test_projects_parity.py`` 逐字段对拍钉住。
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTRACT = REPO_ROOT / "contract" / "projects.v1.json"


def _contract() -> dict[str, Any]:
    """契约必须存在且可解析；缺失/损坏一律 fail-fast，不静默回退内联默认值
    —— 与 contract/README.md 对 intents.v1.json 的要求一致。"""
    with open(CONTRACT, encoding="utf-8") as f:
        return json.load(f)


C = _contract()
SCHEMA_PROJECTS = C["schemas"]["projects"]
SCHEMA_SESSIONS = C["schemas"]["sessions"]
SCHEMA_SESSION_DETAIL = C["schemas"]["session_detail"]
SCHEMA_SESSION_META = C["schemas"]["session_meta"]
INBOX_ID = C["inbox"]["id"]
INBOX_NAME = C["inbox"]["name"]
_L = C["limits"]
DEFAULT_LIMIT = _L["default_limit"]
MAX_LIMIT = _L["max_limit"]
NAME_MAX = _L["name_max_chars"]
TITLE_MAX = _L["title_max_chars"]
TRANSCRIPT_TAIL = _L["transcript_tail"]
TEXT_MAX_BYTES = _L["text_max_bytes"]
_PID_RE = re.compile(C["project_id_pattern"])
_SID = C["session_id"]


def _index_max() -> int:
    raw = os.environ.get(_L["session_index_max_env"], "")
    try:
        return int(raw)
    except (TypeError, ValueError):
        return _L["session_index_max_default"]


def _now() -> int:
    return int(time.time())


# ------------------------------------------------------------------ 守卫


def safe_session_id(s: str) -> str:
    """与 Rust ``projects::safe_session_id`` 同语义：ASCII 字母数字与 -_，长度 4-32，
    **拒 `_` 前缀**（demo/out/_threads 与 _index 是真实存在的非会话目录）。"""
    if not s or s.startswith("_"):
        raise ValueError("session_id 无效")
    out = "".join(c for c in s if c.isascii() and (c.isalnum() or c in "-_"))[: _SID["max_len"]]
    if len(out) < _SID["min_len"] or out.startswith("_"):
        raise ValueError("session_id 无效")
    return out


def safe_project_id(s: str) -> str:
    if s == INBOX_ID:
        return s
    if _PID_RE.match(s or ""):
        return s
    raise ValueError("project_id 无效")


def clean_name(s: str) -> str:
    t = (s or "").strip()
    if not t:
        raise ValueError("项目名不能为空")
    if any(ord(c) < 32 or ord(c) == 127 for c in t):
        raise ValueError("项目名含控制字符")
    return t[:NAME_MAX]  # 按字符数不是字节，中文名不炸


# ------------------------------------------------------------------ 路径


def _index_dir(out_root: Path) -> Path:
    return out_root / "_index"


def _registry_path(out_root: Path) -> Path:
    return _index_dir(out_root) / "projects.v1.json"


def _meta_path(out_root: Path, sid: str) -> Path:
    return out_root / sid / "session.meta.json"


def _transcript_path(out_root: Path, sid: str) -> Path:
    return out_root / sid / "transcript.jsonl"


def _write_atomic(path: Path, text: str) -> None:
    """先写 .tmp 再 rename —— 注册表比 catalog 值钱，不用裸 write。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


# ------------------------------------------------------------------ 注册表


def _empty_registry() -> dict[str, Any]:
    return {"schema": SCHEMA_PROJECTS, "version": 1, "projects": []}


def load_registry(out_root: Path) -> dict[str, Any]:
    p = _registry_path(out_root)
    if not p.is_file():
        return _empty_registry()
    try:
        v = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return _empty_registry()
    if not isinstance(v, dict) or not isinstance(v.get("projects"), list):
        return _empty_registry()
    return v


def _save_registry(out_root: Path, reg: dict[str, Any]) -> None:
    _write_atomic(_registry_path(out_root), json.dumps(reg, ensure_ascii=False, indent=2))


def _is_tombstone(p: dict) -> bool:
    return isinstance(p.get("merged_into"), str)


def _is_active(p: dict) -> bool:
    return not _is_tombstone(p) and not p.get("archived", False)


def _resolve_pid(reg: dict, pid: str) -> str:
    """跟随墓碑 merged_into **一跳**（限一跳防环）。空 / 不存在 / 已归档 → inbox。"""
    if not pid:
        return INBOX_ID
    lst = reg.get("projects", [])
    found = next((p for p in lst if p.get("id") == pid), None)
    if found is None:
        return INBOX_ID
    into = found.get("merged_into")
    if isinstance(into, str):
        hop = next((p for p in lst if p.get("id") == into), None)
        return into if (hop and _is_active(hop)) else INBOX_ID
    return pid if _is_active(found) else INBOX_ID


def _gen_pid(reg: dict) -> str:
    lst = reg.get("projects", [])
    seed = (_now() * 31 + len(lst)) & 0xFFFFFFFF
    while True:
        pid = f"p-{seed:08x}"
        if not any(p.get("id") == pid for p in lst):
            return pid
        seed = (seed + 1) & 0xFFFFFFFF


def create_project(out_root: Path, name: str) -> tuple[dict, bool]:
    name = clean_name(name)
    reg = load_registry(out_root)
    fold = name.casefold()
    for p in reg.get("projects", []):
        if not _is_active(p):
            continue
        names = [p.get("name", "")] + list(p.get("aliases") or [])
        if any((n or "").casefold() == fold for n in names):
            return p, True
    now = _now()
    item = {
        "id": _gen_pid(reg), "name": name, "aliases": [],
        "created_at": now, "updated_at": now, "archived": False,
    }
    reg.setdefault("projects", []).append(item)
    _save_registry(out_root, reg)
    return item, False


def patch_project(out_root: Path, pid: str, name: str | None = None,
                  archived: bool | None = None) -> dict:
    pid = safe_project_id(pid)
    if pid == INBOX_ID:
        raise ValueError("未归类是内置项目，不能改名或归档")
    reg = load_registry(out_root)
    for p in reg.get("projects", []):
        if p.get("id") != pid:
            continue
        if name is not None:
            n = clean_name(name)
            old = p.get("name", "")
            if old and old != n:
                al = list(p.get("aliases") or [])
                if old not in al:
                    al.append(old)
                p["aliases"] = al
            p["name"] = n
        if archived is not None:
            p["archived"] = bool(archived)
        p["updated_at"] = _now()
        _save_registry(out_root, reg)
        return p
    raise ValueError("项目不存在")


def merge_project(out_root: Path, src: str, into: str) -> dict:
    src = safe_project_id(src)
    into = safe_project_id(into)
    if src == into:
        raise ValueError("不能合并到自身")
    if INBOX_ID in (src, into):
        raise ValueError("未归类是内置项目，不参与合并")
    reg = load_registry(out_root)
    lst = reg.get("projects", [])
    s = next((p for p in lst if p.get("id") == src), None)
    if s is None:
        raise ValueError("源项目不存在")
    if not any(p.get("id") == into and _is_active(p) for p in lst):
        raise ValueError("目标项目不存在或已归档")
    carry = [s.get("name", "")] + list(s.get("aliases") or [])
    out = None
    for i, p in enumerate(lst):
        if p.get("id") == src:
            lst[i] = {"id": src, "merged_into": into}
        elif p.get("id") == into:
            al = list(p.get("aliases") or [])
            for c in carry:
                if c and c not in al:
                    al.append(c)
            p["aliases"] = al
            p["updated_at"] = _now()
            out = p
    _save_registry(out_root, reg)
    if out is None:
        raise ValueError("合并失败")
    return out


# ------------------------------------------------------------------ 会话侧车


def _load_meta(out_root: Path, sid: str) -> dict | None:
    p = _meta_path(out_root, sid)
    if not p.is_file():
        return None
    try:
        v = json.loads(p.read_text(encoding="utf-8"))
        return v if isinstance(v, dict) else None
    except Exception:
        return None


def _match_project(reg: dict, text: str) -> str | None:
    """大小写不敏感子串包含 + 最长优先首命中。**永不新建项目。**"""
    hay = (text or "").casefold()
    if not hay.strip():
        return None
    best: tuple[int, str] | None = None
    for p in reg.get("projects", []):
        if not _is_active(p):
            continue
        pid = p.get("id") or ""
        if not pid:
            continue
        for n in [p.get("name", "")] + list(p.get("aliases") or []):
            if n and n.casefold() in hay:
                ln = len(n)
                if best is None or ln > best[0]:
                    best = (ln, pid)
    return best[1] if best else None


def _new_meta(sid: str) -> dict:
    return {
        "schema": SCHEMA_SESSION_META, "session_id": sid,
        "title": "", "title_source": "auto",
        "project_id": "", "project_source": "auto",
        "created_at": _now(), "turns": 0,
    }


def touch_session(out_root: Path, session: str, user_text: str, project_hint: str = "") -> None:
    try:
        sid = safe_session_id(session)
    except ValueError:
        return
    reg = load_registry(out_root)
    meta = _load_meta(out_root, sid) or _new_meta(sid)
    if not meta.get("title") and (user_text or "").strip():
        meta["title"] = (user_text.splitlines() or [""])[0].strip()[:TITLE_MAX]
    if meta.get("project_source") != "manual":
        if project_hint:
            try:
                meta["project_id"] = _resolve_pid(reg, safe_project_id(project_hint))
                meta["project_source"] = "manual"
            except ValueError:
                pass
        elif not meta.get("project_id"):
            pid = _match_project(reg, user_text)
            if pid:
                meta["project_id"] = pid
                meta["project_source"] = "auto"
    meta["turns"] = int(meta.get("turns") or 0) + 1
    meta["updated_at"] = _now()
    if (user_text or "").strip():
        meta["last_user"] = user_text.strip()[:120]
    try:
        _write_atomic(_meta_path(out_root, sid), json.dumps(meta, ensure_ascii=False, indent=2))
    except OSError:
        pass


def set_session_meta(out_root: Path, session: str, project_id: str | None = None,
                     title: str | None = None) -> dict:
    sid = safe_session_id(session)
    reg = load_registry(out_root)
    meta = _load_meta(out_root, sid) or _new_meta(sid)
    if project_id is not None:
        pid = INBOX_ID if project_id == "" else safe_project_id(project_id)
        meta["project_id"] = _resolve_pid(reg, pid)
        meta["project_source"] = "manual"
    if title is not None:
        t = title.strip()
        if not t:
            raise ValueError("标题不能为空")
        meta["title"] = t[:TITLE_MAX]
        meta["title_source"] = "manual"
    meta["updated_at"] = _now()
    _write_atomic(_meta_path(out_root, sid), json.dumps(meta, ensure_ascii=False, indent=2))
    return meta


def append_turn(out_root: Path, session: str, role: str, text: str) -> None:
    try:
        sid = safe_session_id(session)
    except ValueError:
        return
    t = text or ""
    if len(t.encode("utf-8")) > TEXT_MAX_BYTES:
        t = t[: TEXT_MAX_BYTES // 3]
    line = json.dumps({"ts": _now(), "role": role, "text": t}, ensure_ascii=False)
    p = _transcript_path(out_root, sid)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        f.write(line + "\n")


# ------------------------------------------------------------------ 索引


def _scan_rows(out_root: Path) -> list[dict]:
    """分级扫描：优先读几百字节的 meta，没有的降级为「目录名 + mtime」，
    **绝不打开 trace.json**。按 mtime 降序截断到 CIVIL_SESSION_INDEX_MAX。"""
    reg = load_registry(out_root)
    rows: list[dict] = []
    if not out_root.is_dir():
        return rows
    for ent in out_root.iterdir():
        if not ent.is_dir():
            continue
        name = ent.name
        try:
            sid = safe_session_id(name)
        except ValueError:
            continue  # _index / _threads 等在此被挡掉
        if sid != name:
            continue
        m = _load_meta(out_root, sid)
        try:
            mt = int(ent.stat().st_mtime)
        except OSError:
            mt = 0
        if m:
            rows.append({
                "session_id": sid,
                "title": m.get("title") or sid,
                "project_id": _resolve_pid(reg, m.get("project_id") or ""),
                "updated_at": int(m.get("updated_at") or mt),
                "turns": int(m.get("turns") or 0),
            })
        else:
            rows.append({
                "session_id": sid, "title": sid, "project_id": INBOX_ID,
                "updated_at": mt, "turns": 0,
            })
    rows.sort(key=lambda r: r["updated_at"], reverse=True)
    return rows[: _index_max()]


def list_sessions(out_root: Path, project_id: str = "", q: str = "",
                  limit: int = DEFAULT_LIMIT, offset: int = 0) -> dict:
    lim = max(1, min(int(limit or DEFAULT_LIMIT), MAX_LIMIT))
    off = max(0, int(offset or 0))
    rows = _scan_rows(out_root)
    ql = (q or "").strip().casefold()
    sel = [
        r for r in rows
        if (not project_id or r["project_id"] == project_id)
        and (not ql or ql in r["title"].casefold() or ql in r["session_id"].casefold())
    ]
    return {
        "ok": True, "schema": SCHEMA_SESSIONS,
        "total": len(sel), "limit": lim, "offset": off,
        "sessions": sel[off: off + lim],
    }


def list_projects(out_root: Path) -> dict:
    reg = load_registry(out_root)
    rows = _scan_rows(out_root)
    out = []
    for p in reg.get("projects", []):
        if not _is_active(p):
            continue
        pid = p.get("id") or ""
        out.append({
            "id": pid, "name": p.get("name", ""),
            "aliases": list(p.get("aliases") or []),
            "n_sessions": sum(1 for r in rows if r["project_id"] == pid),
            "updated_at": int(p.get("updated_at") or 0),
            "archived": False,
        })
    out.sort(key=lambda x: x["updated_at"], reverse=True)
    return {
        "ok": True, "schema": SCHEMA_PROJECTS, "projects": out,
        "inbox": {
            "id": INBOX_ID, "name": INBOX_NAME,
            "n_sessions": sum(1 for r in rows if r["project_id"] == INBOX_ID),
            "builtin": True,
        },
    }


def session_detail(out_root: Path, session: str) -> dict:
    sid = safe_session_id(session)
    reg = load_registry(out_root)
    m = _load_meta(out_root, sid)
    d = out_root / sid
    try:
        mt = int(d.stat().st_mtime)
    except OSError:
        mt = 0
    turns: list[dict] = []
    truncated = False
    tp = _transcript_path(out_root, sid)
    if tp.is_file():
        lines = [l for l in tp.read_text(encoding="utf-8").splitlines() if l.strip()]
        if len(lines) > TRANSCRIPT_TAIL:
            truncated = True
        for l in lines[-TRANSCRIPT_TAIL:]:
            try:
                turns.append(json.loads(l))
            except Exception:
                pass
    return {
        "ok": True, "schema": SCHEMA_SESSION_DETAIL,
        "session_id": sid,
        "title": (m or {}).get("title") or sid,
        "project_id": _resolve_pid(reg, (m or {}).get("project_id") or ""),
        "updated_at": int((m or {}).get("updated_at") or mt),
        "turns": int((m or {}).get("turns") or 0),
        "transcript": turns,
        "truncated": truncated,
    }
