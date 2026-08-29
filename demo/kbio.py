from __future__ import annotations

import re
from pathlib import Path

from config import KB_ROOT, SKILL_HARD_RULES

ALLOWED_SUFFIX = {".md", ".txt"}
MAX_FILE_BYTES = 512 * 1024
ID_RE = re.compile(r"^[a-z][a-z0-9-]{1,31}$")
FILE_RE = re.compile(r"^[A-Za-z0-9_\u4e00-\u9fff][A-Za-z0-9_\u4e00-\u9fff.\-]{0,80}$")


def ensure_kb_root() -> None:
    KB_ROOT.mkdir(parents=True, exist_ok=True)
    company = KB_ROOT / "company"
    company.mkdir(exist_ok=True)
    dest = company / "hard-rules.md"
    if not dest.exists() and SKILL_HARD_RULES.is_file():
        dest.write_text(SKILL_HARD_RULES.read_text(encoding="utf-8"), encoding="utf-8")


def valid_id(value: str) -> bool:
    return bool(ID_RE.match(value or "")) and value not in {"company", "static", "api", "_shared"}


def valid_filename(name: str) -> bool:
    name = Path(name).name
    if not FILE_RE.match(name):
        return False
    return Path(name).suffix.lower() in ALLOWED_SUFFIX


def resolve_rel(rel: str) -> Path | None:
    rel = (rel or "").replace("\\", "/").lstrip("/")
    if not rel or ".." in rel.split("/") or rel.startswith("/"):
        return None
    parts = rel.split("/")
    if any(p in {".", ""} for p in parts):
        return None
    target = (KB_ROOT / rel).resolve()
    try:
        target.relative_to(KB_ROOT.resolve())
    except ValueError:
        return None
    return target


def iter_text_files(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(
        p
        for p in root.rglob("*")
        if p.is_file() and p.suffix.lower() in ALLOWED_SUFFIX
    )


_LAYER_LABEL = {
    "expert": "本岗知识",
    "category": "大类共享",
    "company": "公司规则",
}

_KB_TITLES = {
    "web-knowledge.md": "联网核对要点",
    "web-portals.md": "官方门户与现行口径",
    "faq.md": "常见问答",
    "outline.md": "成稿大纲",
    "readme.md": "本库说明",
    "hard-rules.md": "硬规则",
    "hard-rules-short.md": "硬规则（摘要）",
    "disclaimer.md": "免责声明",
    "ask-anyone.md": "谁都可以问",
    "ask-from-others.md": "跨岗怎么问",
    "parse-checklist.md": "招标摘录清单",
    "reject-traps.md": "废标与否决雷区",
    "tender-workflow.md": "投标工序",
    "scheme-11.md": "专项方案十一章",
    "judge-card.md": "危大判定卡",
    "hazard-triggers.md": "危大触发",
    "order-37-points.md": "37号令要点（仅中国）",
    "calc-outline.md": "计算书提纲",
    "principles.md": "设计原则",
    "discipline-split.md": "专业拆分",
    "jurisdiction-codes.md": "辖区规范族",
    "model-rules.md": "模型规则",
    "plan-levels.md": "计划层级",
    "brief-rules.md": "交底口径",
    "tech-brief.md": "技术交底骨架",
    "no-fake-price.md": "禁止编造单价",
    "no-price.md": "采购不编价格",
    "takeoff.md": "工程量拆分口径",
    "lab-rules.md": "试验室纪律",
    "finance-rules.md": "财务口径",
    "legal-tone.md": "劳动人事用语",
    "no-secrets.md": "不写密钥",
    "plant-rules.md": "物机纪律",
    "seal.md": "用印",
    "closing.md": "资料闭合",
    "archive.md": "归档目录",
    "script.md": "工友口播稿骨架",
    "worker-tone.md": "工友白话语气",
    "experiment.md": "交通试验口径",
}


def layer_label(layer: str) -> str:
    return _LAYER_LABEL.get(layer, "公司规则")


def known_kb_title(filename: str) -> str | None:
    return _KB_TITLES.get(Path(filename).name.lower())


def first_heading(text: str) -> str | None:
    for line in text.splitlines()[:12]:
        t = line.strip()
        if t.startswith("##") or not t.startswith("#"):
            continue
        s = t.lstrip("#").strip()
        if s and len(s) <= 48:
            return s
    return None


def display_title(filename: str, text: str) -> str:
    mapped = known_kb_title(filename)
    if mapped:
        return mapped
    heading = first_heading(text)
    if heading:
        return heading
    return Path(filename).stem


def file_stat(path: Path, rel: str, layer: str) -> dict:
    raw = path.read_bytes()
    text = raw.decode("utf-8", errors="ignore")
    return {
        "path": rel.replace("\\", "/"),
        "title": path.stem,
        "display": display_title(path.name, text),
        "layer": layer,
        "layer_label": layer_label(layer),
        "bytes": len(raw),
        "chars": len(text),
        "lines": text.count("\n") + (1 if text and not text.endswith("\n") else 0),
    }


def folder_stats(root: Path, prefix: str, layer: str) -> dict:
    files = []
    total = 0
    for path in iter_text_files(root):
        rel = str(path.relative_to(KB_ROOT)).replace("\\", "/")
        st = file_stat(path, rel, layer)
        files.append(st)
        total += st["bytes"]
    return {"bytes": total, "files": files, "count": len(files)}


def read_text(rel: str) -> tuple[str, dict] | None:
    path = resolve_rel(rel)
    if path is None or not path.is_file():
        return None
    if path.suffix.lower() not in ALLOWED_SUFFIX:
        return None
    text = path.read_text(encoding="utf-8", errors="ignore")
    st = file_stat(path, rel.replace("\\", "/"), "")
    return text, st


def _kb_index_hook(rel_posix: str) -> None:
    """写钩子（data-plan M3）：KB 落盘成功后即时更新 SQLite FTS 索引。
    失败只降级不阻断编辑——查询侧 30s 新鲜度检查会兜底重建。"""
    try:
        import sys

        if str(REPO_ROOT) not in sys.path:
            sys.path.insert(0, str(REPO_ROOT))
        from packing_assistant.kb_search import reindex_kb_file

        reindex_kb_file(
            rel_posix, kb="demo_kb",
            title_resolver=lambda p, text: display_title(p.name, text),
        )
    except Exception:
        pass


def write_text(rel: str, content: str) -> dict:
    if len(content.encode("utf-8")) > MAX_FILE_BYTES:
        raise ValueError(f"单文件不能超过 {MAX_FILE_BYTES} 字节")
    path = resolve_rel(rel)
    if path is None:
        raise ValueError("非法路径")
    if path.suffix.lower() not in ALLOWED_SUFFIX:
        raise ValueError("只允许 .md / .txt")
    if not valid_filename(path.name):
        raise ValueError("文件名只能用中文、字母、数字、_ -")
    try:
        import sys

        from config import REPO_ROOT

        if str(REPO_ROOT) not in sys.path:
            sys.path.insert(0, str(REPO_ROOT))
        from packing_assistant.sandbox import guarded_write_text

        guarded_write_text(path, content)
    except PermissionError:
        raise
    except Exception:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    rel_posix = str(path.relative_to(KB_ROOT)).replace("\\", "/")
    _kb_index_hook(rel_posix)
    return file_stat(path, rel_posix, "")


def create_file(rel: str) -> dict:
    path = resolve_rel(rel)
    if path is None:
        raise ValueError("非法路径")
    if path.exists():
        raise ValueError("文件已存在")
    return write_text(rel, f"# {path.stem}\n\n")


def delete_file(rel: str) -> None:
    path = resolve_rel(rel)
    if path is None or not path.is_file():
        raise ValueError("文件不存在")
    path.unlink()


def ensure_expert_kb(category: str, expert_id: str, name: str) -> None:
    shared = KB_ROOT / category / "_shared"
    shared.mkdir(parents=True, exist_ok=True)
    marker = shared / "README.md"
    if not marker.exists():
        marker.write_text(
            f"# {category} 大类共享库\n\n本大类专家都能检索到这里的文件。\n",
            encoding="utf-8",
        )
    private = KB_ROOT / category / expert_id
    private.mkdir(parents=True, exist_ok=True)
    readme = private / "README.md"
    if not readme.exists():
        readme.write_text(
            f"# {name} 私库\n\n只有本专家默认优先检索。同类专家不读这里。\n",
            encoding="utf-8",
        )


def remove_expert_kb(category: str, expert_id: str) -> None:
    import shutil

    private = KB_ROOT / category / expert_id
    if private.is_dir():
        shutil.rmtree(private)


def format_bytes(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f" {n / 1024:.1f} KB".strip()
    return f"{n / (1024 * 1024):.2f} MB"
