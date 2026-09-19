"""`civil review <文稿>` — Codex has /review for a diff; a civil document gets this instead.

No model. Two questions, both answered from what is in the job folder:

    numbers     which quantities and clause numbers in the document have no source in the job's
                material — CIVIL.md, every other readable file in the folder, what the user typed
                in this folder's threads, and the user text a Civil Buddy draft quotes verbatim
    assertions  does it state a verdict nobody here may state (可以开工, 报审通过, 符合招标文件的要求 ...)
                — stated, not disclaimed, asked or made conditional (tools/verdict_guard)

A finding is not an error. It means "this number is not in your material — check where it came
from". The check is tools/number_provenance, scored on test/benchmarks/number_provenance; it
asks whether a number has a source, never whether it is right.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

_QUOTED_SECTIONS = re.compile(r"^## (?:用户原文|作业根文件)[^\n]*\n(.*?)(?=^## |\Z)", re.S | re.M)
_FILE_CHARS = 40_000
_DRAFT_CHARS = 400_000


def _line_of(text: str, position: int) -> Dict[str, Any]:
    start = text.rfind("\n", 0, position) + 1
    end = text.find("\n", position)
    return {"line": text.count("\n", 0, position) + 1, "context": text[start: len(text) if end < 0 else end].strip()[:160]}


def _thread_user_text() -> List[str]:
    from packing_assistant.runtime import threads

    said: List[str] = []
    try:
        rollouts = sorted(threads._DIR.glob("*.rollout.jsonl"))
    except OSError:
        return said
    for path in rollouts[-50:]:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError):
            continue
        for raw in lines:
            try:
                row = json.loads(raw)
            except ValueError:
                continue
            if isinstance(row, dict) and row.get("role") == "user" and isinstance(row.get("content"), str):
                said.append(row["content"])
    return said


def _own_drafts(file_name: str) -> List[Path]:
    from packing_assistant.office_job import job_file_by_name, job_root, job_root_granted

    if not file_name or not job_root_granted():
        return []
    state = job_root().resolve() / ".civil-buddy" / "out"
    try:
        found = sorted(path for path in state.rglob(file_name) if path.is_file())
    except OSError:
        return []
    return [path for path in found if job_file_by_name(str(path), by_name=False) is not None]


def review_file(name: str) -> Dict[str, Any]:
    from packing_assistant.office_job import job_file_by_name, job_root, job_tree_files, read_material
    from packing_assistant.runtime.project_instructions import load
    from packing_assistant.tools.number_provenance import untraced

    target = job_file_by_name(name)
    if target is None:
        # Civil Buddy 自己出的稿在 .civil-buddy/out 下面，不在资料清单里：按文件名去那里找。
        drafts = _own_drafts(Path(str(name)).name)
        if len(drafts) > 1:
            listed = "\n".join("  " + path.relative_to(job_root().resolve()).as_posix() for path in drafts[:12])
            return {"ok": False, "schema": "civil.review.v1", "error_code": "ambiguous",
                    "reply": f"有 {len(drafts)} 份叫 {Path(str(name)).name} 的稿，请写全路径：\n{listed}"}
        target = drafts[0] if drafts else None
    if target is None:
        return {"ok": False, "schema": "civil.review.v1", "error_code": "not_found",
                "reply": f"作业文件夹里没有 {name}（civil review 只看当前作业文件夹里的文件）。"}
    try:
        draft = read_material(target, _DRAFT_CHARS)
    except Exception as exc:  # noqa: BLE001 - a damaged document is an answer, not a crash
        return {"ok": False, "schema": "civil.review.v1", "error_code": "unreadable",
                "reply": f"{target.name} 读不出来：{type(exc).__name__}"}
    sources: List[str] = []
    evidence: List[str] = [load().text, *_thread_user_text(), *_QUOTED_SECTIONS.findall(draft)]
    for row in job_tree_files():
        path = Path(row["path"])
        if path == target:
            continue
        try:
            evidence.append(read_material(path, _FILE_CHARS))
            sources.append(row["name"])
        except Exception:  # noqa: BLE001 - an unreadable neighbour is simply not evidence
            continue
    numbers = [{**item, **_line_of(draft, item["start"])} for item in untraced(draft, evidence)]
    from packing_assistant.tools.verdict_guard import stated_verdicts

    assertions = [{**item, **_line_of(draft, item["start"])} for item in stated_verdicts(draft)]
    try:
        shown = target.relative_to(job_root().resolve()).as_posix()
    except ValueError:
        shown = target.name
    clean = not numbers and not assertions
    return {"ok": True, "schema": "civil.review.v1", "file": shown, "clean": clean, "sources": sources,
            "numbers": numbers, "assertions": assertions, "reply": _render(shown, sources, numbers, assertions)}


def _render(shown: str, sources: List[str], numbers: List[Dict[str, Any]], assertions: List[Dict[str, Any]]) -> str:
    lines = [f"review {shown}", f"  对照：CIVIL.md、本文件夹的对话记录，以及 {len(sources)} 份资料" + ("（" + "、".join(sources[:6]) + ("…" if len(sources) > 6 else "") + "）" if sources else "")]
    lines.append(f"  找不到出处的数字 / 条款号：{len(numbers)}")
    lines += [f"    L{item['line']:<4} {item['text']:<12} | {item['context']}" for item in numbers[:60]]
    lines.append(f"  不该由本稿下的结论：{len(assertions)}")
    lines += [f"    L{item['line']:<4} {item['text']:<12} | {item['context']}" for item in assertions[:30]]
    lines.append("  结果：未发现问题（只说明数字都有出处，不说明数字是对的）。" if not numbers and not assertions
                 else "  结果：以上各处请核对来源。找不到出处不等于错，但不能就这样交出去。")
    return "\n".join(lines)
