"""CIVIL.md — the job folder's standing instructions, read before every task.

This is what AGENTS.md is to Codex: facts and house rules that belong to the project rather
than to one request. Two things are taken from it:

- *slots* — explicit ``key: value`` lines (项目 / 辖区 / 业主 / 合同号 / 地点 / 单位制 / 负责人).
  They seed a new session and are handed to the drafting tools as stated facts, so a draft
  stops saying UNSPECIFIED for something the project file states. A blank slot stays blank:
  nothing here is inferred.
- the *text* — given to the model as project instructions when a model drives the turn.

Files are read from the most general to the most specific (``~/.civil-buddy/CIVIL.md``, the
job root, then each folder down to the current one); a more specific file overrides a slot.
The total is capped at 32 KiB, as Codex caps its project doc.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

NAME = "CIVIL.md"
MAX_BYTES = 32 * 1024

_SLOT_KEYS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ("project", ("项目名称", "工程名称", "项目", "project")),
    ("jurisdiction", ("辖区", "法域", "jurisdiction")),
    ("client", ("建设单位", "发包人", "业主", "client", "owner")),
    ("contract_no", ("合同编号", "合同号", "contract no", "contract")),
    ("location", ("工程地点", "项目地点", "地点", "location", "site")),
    ("units", ("单位制", "units")),
    ("tech_lead", ("技术负责人",)),
    ("safety_lead", ("安全负责人",)),
)
_SLOT_LABELS = {
    "project": "项目", "jurisdiction": "辖区", "client": "业主", "contract_no": "合同号",
    "location": "地点", "units": "单位制", "tech_lead": "技术负责人", "safety_lead": "安全负责人",
}
_JURISDICTIONS = {
    "cn": "CN", "中国": "CN", "中国大陆": "CN", "内地": "CN", "大陆": "CN",
    "sg": "SG", "新加坡": "SG", "singapore": "SG",
    "eu": "EU", "欧盟": "EU",
    "dual": "DUAL", "双辖区": "DUAL", "多辖区": "DUAL",
}
_COMMENT = re.compile(r"<!--.*?-->", re.S)
_LINE = re.compile(
    # [ \t] rather than \s around the value: a blank slot must not swallow the next line.
    r"^[ \t]*(?:[-*+][ \t]*)?(?:\*\*)?(?P<key>" + "|".join(
        re.escape(k) for _slot, keys in _SLOT_KEYS for k in sorted(keys, key=len, reverse=True)
    ) + r")(?:\*\*)?[ \t]*[:：][ \t]*(?P<value>[^\r\n]*?)[ \t]*$",
    re.I | re.M,
)
_KEY_TO_SLOT = {k.lower(): slot for slot, keys in _SLOT_KEYS for k in keys}

TEMPLATE = """# CIVIL.md · 本工程说明（Civil Buddy 每次任务前都会读）

> 作用相当于 Codex 的 AGENTS.md。只写你确认过的事实；不确定的留空——
> 留空的栏在成稿里保持 UNSPECIFIED，不会被猜出来。

## 项目信息

- 项目：
- 辖区：            <!-- CN / SG / EU / DUAL -->
- 业主：
- 合同号：
- 地点：
- 单位制：mm / kg

## 签认

- 技术负责人：
- 安全负责人：

## 本工程约定

<!-- 例：日报统一用 24 小时制；装柜默认 40HQ；只引用「依据清单」里列出的规范标题 -->

## 依据清单（只写标题与年份，不贴正文）

"""


@dataclass
class ProjectInstructions:
    files: List[Path] = field(default_factory=list)
    text: str = ""
    slots: Dict[str, str] = field(default_factory=dict)
    truncated: bool = False

    def fact_block(self) -> str:
        """Stated project facts, one per line, in the form the drafting tools already read."""
        return "\n".join(f"{_SLOT_LABELS[slot]}：{self.slots[slot]}" for slot, _keys in _SLOT_KEYS
                         if self.slots.get(slot))

    def prompt_block(self) -> str:
        if not self.text.strip():
            return ""
        note = "（超过 32 KiB 的部分已截断）" if self.truncated else ""
        return f"## 本工程说明（CIVIL.md{note}）\n\n{self.text.strip()}"


def parse_slots(text: str) -> Dict[str, str]:
    slots: Dict[str, str] = {}
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")   # a file saved on Windows
    for match in _LINE.finditer(_COMMENT.sub("", text)):
        slot = _KEY_TO_SLOT[match.group("key").lower()]
        value = match.group("value").strip().strip("*").strip()
        if not value:
            continue
        if slot == "jurisdiction":
            value = _JURISDICTIONS.get(value.lower(), "")
            if not value:
                continue
        slots[slot] = value[:200]
    return slots


def _candidates(job_root: Optional[Path], cwd: Optional[Path]) -> List[Path]:
    paths = [Path.home() / ".civil-buddy" / NAME]
    if job_root is None:
        return paths
    job_root = Path(job_root).resolve()
    paths.append(job_root / NAME)
    here = Path(cwd or Path.cwd())
    try:
        relative = here.resolve().relative_to(job_root)
    except (OSError, ValueError):
        return paths
    folder = job_root
    for part in relative.parts:
        folder = folder / part
        paths.append(folder / NAME)
    return paths


def load(job_root: Optional[Path] = None, cwd: Optional[Path] = None) -> ProjectInstructions:
    """Read every CIVIL.md that applies. With no job folder only the user-level file applies."""
    if job_root is None:
        from packing_assistant.runtime.workspace import active, find_job_root

        job_root = active() or find_job_root(cwd)
    found = ProjectInstructions()
    budget = MAX_BYTES
    pieces: List[str] = []
    for path in _candidates(job_root, cwd):
        try:
            if not path.is_file():
                continue
            raw = path.read_bytes()
        except OSError:
            continue
        if len(raw) > budget:
            raw, found.truncated = raw[:budget], True
        budget -= len(raw)
        text = raw.decode("utf-8", errors="ignore").lstrip(chr(0xFEFF)).replace("\r\n", "\n")
        found.files.append(path)
        found.slots.update(parse_slots(text))   # a more specific file overrides
        pieces.append(text.strip())
        if budget <= 0:
            break
    found.text = "\n\n".join(p for p in pieces if p)
    return found


def init(job_root: Path) -> Tuple[Path, bool]:
    """Write the template into the job folder. An existing CIVIL.md is never touched."""
    path = Path(job_root) / NAME
    if path.exists():
        return path, False
    path.write_text(TEMPLATE, encoding="utf-8")
    return path, True


def seed_session(session_id: str) -> bool:
    """Give a new session the project file's 项目 / 辖区. An existing session keeps its own."""
    from packing_assistant.runtime.memory import load_summary, save_summary
    from packing_assistant.runtime.workspace import active

    if active() is None or load_summary(session_id) is not None:
        return False
    slots = load().slots
    if not (slots.get("project") or slots.get("jurisdiction")):
        return False
    save_summary(session_id, jurisdiction=slots.get("jurisdiction", ""), project=slots.get("project", ""))
    return True


def with_facts(text: str) -> str:
    """The task text with the project file's stated facts in front, for the drafting tools.

    A fact the user states in this task wins: a slot whose label already appears in the
    text is not repeated.
    """
    from packing_assistant.runtime.workspace import active

    if active() is None:
        return text
    instructions = load()
    lines = [line for line in instructions.fact_block().splitlines()
             if not re.search(re.escape(line.split("：", 1)[0]) + r"\s*[:：]", text or "")]
    return ("\n".join(lines) + "\n" + (text or "")) if lines else text
