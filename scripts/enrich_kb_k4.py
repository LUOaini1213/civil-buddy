#!/usr/bin/env python3
"""One-shot: give every roster post a README field table and ≥5 faq questions.

Does not touch unique writers. Idempotent.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
KB = ROOT / "demo" / "kb"

_Q_RE = re.compile(
    r"(?m)(?:^问[：:]|^[-*]\s*问[：:]|^## Q\s|^\*\*[^*\n]{2,80}？\*\*)"
)
_NUM = re.compile(r"(?m)^\s*(\d+)\.\s+\*?\*?(.+?)\*?\*?$")
_H = re.compile(r"(?m)^#{2,3}\s+(.+)$")


def count_questions(text: str) -> int:
    return len(_Q_RE.findall(text or ""))


def outline_blob(folder: Path, outline: str) -> str:
    bits = [outline or ""]
    for name in ("scheme-11.md", "judge-card.md"):
        p = folder / name
        if name in (outline or "") and p.is_file():
            bits.append(p.read_text(encoding="utf-8"))
        elif p.is_file() and name == "scheme-11.md" and "十一章" in (outline or ""):
            bits.append(p.read_text(encoding="utf-8"))
    return "\n".join(bits)


def field_names(blob: str, delivers: str) -> list[str]:
    names: list[str] = []
    for _n, title in _NUM.findall(blob or ""):
        t = re.sub(r"\s+", " ", title).strip()
        t = t.split("：")[0].split("(")[0].split("（")[0].strip()
        t = t.strip("*").strip()
        if t and t not in names and len(t) <= 40:
            names.append(t)
        if len(names) >= 10:
            break
    if len(names) < 4:
        for title in _H.findall(blob or ""):
            t = re.sub(r"\s+", " ", title).strip()[:40]
            if t and t not in names and not t.startswith("禁"):
                names.append(t)
            if len(names) >= 8:
                break
    if delivers and delivers not in names:
        names.insert(0, delivers.split("+")[0].strip()[:24] or "交付")
    while len(names) < 4:
        names.append(["封面与声明", "用户原文", "缺数栏", "禁令"][len(names)])
    return names[:10]


def ensure_readme(path: Path, *, name: str, tool: str, fields: list[str], risk: str) -> bool:
    text = path.read_text(encoding="utf-8") if path.is_file() else f"# {name} 私库\n"
    if "| 栏 |" in text and "字段表" in text:
        return False
    rows = "\n".join(f"| {f} | 缺则 [A001] / 待填 |" for f in fields)
    extra = (
        f"\n独有工具：`{tool or 'write_deliverable'}`\n"
        "聊天可只答 faq / web-knowledge，不写盘。\n"
        "\n## 字段表\n\n"
        "| 栏 | 缺则 |\n"
        "| --- | --- |\n"
        f"{rows}\n"
        "\n内部讨论 AI 草稿。缺数不编条款号、综合单价、xyz。不下开工或投标合格结论。\n"
    )
    if "独有工具" not in text and tool:
        pass
    path.write_text(text.rstrip() + extra, encoding="utf-8")
    return True


def ensure_faq(path: Path, *, name: str, delivers: str, tool: str, fields: list[str], title: str) -> bool:
    text = path.read_text(encoding="utf-8") if path.is_file() else f"# {name}专家 · 常见问答\n"
    n = count_questions(text)
    if n >= 5:
        return False
    extras = [
        (
            f"{name}默认交付什么？是不是签认件？",
            f"默认交付「{delivers}」。内部讨论 AI 草稿，不是法定签认件。独有工具 `{tool or 'write_deliverable'}`。可以只聊天，不必成稿。",
        ),
        (
            f"{name}缺尺寸、单价或条款时怎么写？",
            "无来源数字写 [A001] 或 UNSPECIFIED。不编条款号、综合单价、xyz、柜数。用户没给的栏整栏待填。",
        ),
        (
            "SG 和 CN 口径能混着用吗？",
            "默认新加坡工地 SG。CN 标题只在用户点名 CN 或 DUAL 时用。DUAL 必须分栏点名两套门户。权威句见 company/web-portals.md。",
        ),
        (
            f"和兄弟岗怎么分？本岗范围是什么？",
            f"本岗做{title}。明显属别岗请改召唤。检索只看本岗私库 + 大类共享 + 公司层，看不见兄弟私库。",
        ),
        (
            "能不能下开工、投标或验收合格结论？",
            "不能。产出是内部讨论草稿。高风险写盘须用户打出确认句。合格、报审通过一类结论本岗不下。",
        ),
    ]
    for f in fields[:3]:
        extras.append(
            (
                f"成稿「{f}」没材料怎么办？",
                f"保留「{f}」栏，缺事实写待填 / [A001]。不拿经验做法填满。",
            )
        )
    need = 5 - n
    block = ["", ""]
    used = 0
    for q, a in extras:
        if used >= need:
            break
        if q in text:
            continue
        block.append(f"问：{q}")
        block.append(f"答：{a}")
        block.append("")
        used += 1
    path.write_text(text.rstrip() + "\n" + "\n".join(block), encoding="utf-8")
    return True


def ensure_outline_gap(path: Path, blob: str) -> bool:
    if "[A001]" in blob or "[Axxx]" in blob or "待填" in blob or "信息不足" in blob:
        return False
    text = path.read_text(encoding="utf-8") if path.is_file() else "# 成稿大纲\n"
    path.write_text(text.rstrip() + "\n\n缺数写 [A001] / UNSPECIFIED。用户未给则整栏待填。\n", encoding="utf-8")
    return True


def main() -> int:
    from packing_assistant.expert_roster import list_experts

    n_readme = n_faq = n_out = 0
    for e in list_experts():
        folder = KB / e.category / e.id
        folder.mkdir(parents=True, exist_ok=True)
        outline_p = folder / "outline.md"
        outline = outline_p.read_text(encoding="utf-8") if outline_p.is_file() else ""
        blob = outline_blob(folder, outline)
        fields = field_names(blob, e.delivers)
        tool = ""
        for n in e.exclusive:
            if not n.endswith(("__health", "__list")):
                tool = n
                break
        if not tool and e.exclusive:
            tool = e.exclusive[0]
        if ensure_readme(
            folder / "README.md",
            name=e.name,
            tool=tool,
            fields=fields,
            risk=e.risk,
        ):
            n_readme += 1
        if ensure_faq(
            folder / "faq.md",
            name=e.name,
            delivers=e.delivers,
            tool=tool,
            fields=fields,
            title=e.title,
        ):
            n_faq += 1
        if ensure_outline_gap(outline_p, blob):
            n_out += 1
    print(f"enrich_kb_k4 readme={n_readme} faq={n_faq} outline={n_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
