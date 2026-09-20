"""Which version of what a bid check was made against.

A compliance check is a statement about texts: this tender, this response, these evidence files. Once
any of them changes, the statement is about something that no longer exists - and nothing used to say
so. A check of yesterday's 投标函 read exactly like a check of today's; ``civil review`` on a draft
could not tell whether the draft had been edited since it was checked.

The record (schema ``civil.bid.check.v1``) is written beside the draft it belongs to:

    inputs   what was read, each with the sha256 of the text as it was read, its role, and - for a job
             file - its path, so that it can be read again later
    drafts   the documents the check produced or reviewed, each with its sha256
    rows     事项 / 招标要求 / 响应原文或证据 / 三态 of every row, to say later which rows moved

Two things are done with it, neither of which judges anything:

    compare(previous, current)   on the next check in the same place: which inputs changed, which
                                 rows changed state. The old conclusions held for the old inputs.
    verify(record, ...)          at any later time: does the draft still have the hash that was
                                 recorded, do the job files still read the same

A hash says "the same text" or "not the same text". It never says which of two versions is right.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

SCHEMA = "civil.bid.check.v1"
RECORD_SUFFIX = ".check.json"
WORKFLOW_RECORD = "check.json"
_MAX_BYTES = 512_000
_STATE, _LABEL, _NEED, _HAVE = "三态", "事项", "招标要求", "响应原文或证据"


def sha(text: Any) -> str:
    """sha256 of a text. Line endings are folded first: the same draft written on Windows and read back
    is the same draft."""
    return hashlib.sha256(str(text or "").replace("\r\n", "\n").encode("utf-8")).hexdigest()


def short(digest: Any) -> str:
    return str(digest or "")[:12] or "—"


def entry(title: str, role: str, text: Any, **extra: Any) -> Dict[str, Any]:
    """One input of a check: what it was, and the hash of the text as it was read."""
    body = str(text or "")
    return {"title": str(title), "role": str(role), "sha256": sha(body), "chars": len(body),
            **{key: value for key, value in extra.items() if value not in (None, "")}}


def rows_of(markdown: str) -> List[Dict[str, str]]:
    """Every row of every table that has a 三态 column: its label, what was asked, what was answered, its state.
    A label that occurs twice (one row per lot is already told apart by the lot) gets "#2"."""
    found: List[Dict[str, str]] = []
    header: Optional[List[str]] = None
    seen: Dict[str, int] = {}
    for raw in (markdown or "").splitlines():
        line = raw.strip()
        if not (line.startswith("|") and line.endswith("|")):
            header = None
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if all(re.fullmatch(r":?-{2,}:?", c) for c in cells):
            continue
        if header is None:
            header = cells
            continue
        if _STATE not in header or _LABEL not in header:
            continue
        row = dict(zip(header, cells))
        label = row.get(_LABEL, "")
        seen[label] = seen.get(label, 0) + 1
        found.append({"label": label if seen[label] == 1 else f"{label}#{seen[label]}", "state": row.get(_STATE, ""),
                      "need": row.get(_NEED, ""), "have": row.get(_HAVE, "")})
    return found


def build(*, kind: str, session_id: str, inputs: Sequence[Mapping[str, Any]], drafts: Sequence[Mapping[str, Any]],
          rows: Sequence[Mapping[str, str]], unreadable: Sequence[Mapping[str, Any]] = (),
          checked_at: Optional[float] = None, **extra: Any) -> Dict[str, Any]:
    return {"schema": SCHEMA, "kind": kind, "session_id": session_id, "checked_at": float(checked_at if checked_at is not None else time.time()),
            "inputs": [dict(item) for item in inputs], "unreadable": [dict(item) for item in unreadable],
            "drafts": [dict(item) for item in drafts], "rows": [dict(row) for row in rows],
            **{key: value for key, value in extra.items() if value not in (None, "")}}


def load(path: Path) -> Optional[Dict[str, Any]]:
    """The record at ``path``, or None: absent, too large, not JSON, or not this schema. A damaged record
    is no record - the check it belonged to simply has nothing to be compared with."""
    try:
        target = Path(path)
        if not target.is_file() or target.stat().st_size > _MAX_BYTES:
            return None
        value = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(value, dict) or value.get("schema") != SCHEMA:
        return None
    if not all(isinstance(value.get(key), list) for key in ("inputs", "drafts", "rows")):
        return None
    return value


def dumps(record: Mapping[str, Any]) -> str:
    return json.dumps(record, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# the next check in the same place
# ---------------------------------------------------------------------------
def _key(item: Mapping[str, Any]) -> Tuple[str, str]:
    return str(item.get("role") or ""), str(item.get("title") or "")


def compare(previous: Mapping[str, Any], current: Mapping[str, Any]) -> Dict[str, Any]:
    """What differs between two checks. Inputs are told apart by role and title, rows by their label."""
    before = {_key(i): i for i in previous.get("inputs") or [] if isinstance(i, Mapping)}
    after = {_key(i): i for i in current.get("inputs") or [] if isinstance(i, Mapping)}
    inputs = []
    for key in list(dict.fromkeys([*before, *after])):
        old, new = before.get(key), after.get(key)
        change = ("added" if old is None else "removed" if new is None
                  else "same" if old.get("sha256") == new.get("sha256") else "changed")
        if change != "same":
            inputs.append({"role": key[0], "title": key[1], "change": change,
                           "before": short((old or {}).get("sha256")), "after": short((new or {}).get("sha256"))})
    was_unread = {str(u.get("title")) for u in previous.get("unreadable") or [] if isinstance(u, Mapping)}
    now_unread = {str(u.get("title")) for u in current.get("unreadable") or [] if isinstance(u, Mapping)}
    for title in sorted(was_unread - now_unread):
        if not any(i["title"] == title for i in inputs):
            inputs.append({"role": "", "title": title, "change": "now_read", "before": "未读出", "after": "—"})
    for title in sorted(now_unread - was_unread):
        inputs.append({"role": "", "title": title, "change": "now_unread", "before": "—", "after": "未读出"})
    old_rows = {str(r.get("label")): r for r in previous.get("rows") or [] if isinstance(r, Mapping)}
    new_rows = {str(r.get("label")): r for r in current.get("rows") or [] if isinstance(r, Mapping)}
    rows = []
    for label in list(dict.fromkeys([*old_rows, *new_rows])):
        old, new = old_rows.get(label), new_rows.get(label)
        if old is None or new is None or old.get("state") != new.get("state"):
            rows.append({"label": label, "before": (old or {}).get("state") or "（上次无此行）",
                         "after": (new or {}).get("state") or "（这次无此行）"})
    return {"inputs": inputs, "rows": rows, "same": not inputs and not rows}


def when(record: Mapping[str, Any]) -> str:
    try:
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(float(record.get("checked_at") or 0)))
    except (TypeError, ValueError, OverflowError, OSError):
        return "时间未记录"


_CHANGE_WORD = {"added": "这次新增", "removed": "这次没有", "changed": "内容已改动", "now_read": "上次未读出，这次读到了",
                "now_unread": "这次未读出"}


def comparison_section(previous: Mapping[str, Any], current: Mapping[str, Any]) -> List[str]:
    """Markdown for "与上次核对相比". States moved are reported, never explained: which version is the one
    to submit is not something a hash knows."""
    diff = compare(previous, current)
    draft = next((d for d in previous.get("drafts") or [] if isinstance(d, Mapping)), {})
    lines = ["## 与上次核对相比", "",
             f"上次核对：{when(previous)}（稿 sha256 {short(draft.get('sha256'))}）。它的结论只对当时读到的文字成立。", ""]
    if diff["same"]:
        return lines + ["输入与上次相同（sha256 一致），各行三态未变。", ""]
    if diff["inputs"]:
        lines += ["| 输入 | 变化 | 上次 sha256 | 这次 sha256 |", "| --- | --- | --- | --- |"]
        lines += [f"| {i['title']} | {_CHANGE_WORD.get(i['change'], i['change'])} | {i['before']} | {i['after']} |" for i in diff["inputs"]]
        lines.append("")
    else:
        lines += ["输入与上次相同（sha256 一致）。", ""]
    if diff["rows"]:
        lines += ["| 事项 | 上次三态 | 这次三态 |", "| --- | --- | --- |"]
        lines += [f"| {r['label']} | {r['before']} | {r['after']} |" for r in diff["rows"]]
        lines.append("")
    else:
        lines += ["各行三态与上次相同。", ""]
    lines += ["上表只说哪里变了，不说哪一版该递交。", ""]
    return lines


def inputs_table(inputs: Sequence[Mapping[str, Any]]) -> List[str]:
    lines = ["| 核对时读到的 | 用途 | sha256（前 12 位） | 字数 |", "| --- | --- | --- | --- |"]
    lines += [f"| {i.get('title')} | {i.get('role') or '—'} | {short(i.get('sha256'))} | {i.get('chars', '—')} |" for i in inputs]
    return lines + [""]


# ---------------------------------------------------------------------------
# at any later time
# ---------------------------------------------------------------------------
def verify(record: Mapping[str, Any], *, draft_text: Optional[str] = None, draft_name: str = "",
           read_input: Optional[Callable[[str], Optional[str]]] = None,
           read_draft: Optional[Callable[[str], Optional[str]]] = None) -> Dict[str, Any]:
    """Does what the record describes still exist as it was.

    ``draft_text`` / ``draft_name``: the document somebody is looking at now. ``read_input(path)`` reads a
    job file again the way the check read it (None: gone or unreadable). ``read_draft(path)`` reads one of
    the record's other drafts. Inputs that were typed or attached have no path and cannot be looked at
    again: they are reported as such, never as unchanged.
    """
    drafts = []
    for item in record.get("drafts") or []:
        if not isinstance(item, Mapping):
            continue
        name = str(item.get("name") or "")
        if draft_text is not None and draft_name and name == draft_name:
            now: Optional[str] = draft_text
        elif read_draft is not None and item.get("path"):
            now = read_draft(str(item["path"]))
        else:
            continue
        drafts.append({"name": name, "state": "missing" if now is None else "same" if sha(now) == item.get("sha256") else "changed"})
    inputs = []
    for item in record.get("inputs") or []:
        if not isinstance(item, Mapping):
            continue
        title = str(item.get("title") or "")
        if not item.get("path") or read_input is None:
            inputs.append({"title": title, "state": "not_checkable"})
            continue
        now = read_input(str(item["path"]))
        inputs.append({"title": title, "state": "missing" if now is None else "same" if sha(now) == item.get("sha256") else "changed"})
    stale = any(d["state"] != "same" for d in drafts) or any(i["state"] in ("changed", "missing") for i in inputs)
    return {"schema": "civil.bid.check.verify.v1", "checked_at": record.get("checked_at"), "drafts": drafts, "inputs": inputs, "stale": stale}


_VERIFY_WORD = {"same": "未变", "changed": "已改动", "missing": "找不到或读不出", "not_checkable": "当时是打字或附件，无法重读"}


def verify_lines(found: Mapping[str, Any], record: Mapping[str, Any]) -> List[str]:
    lines = [f"  核对记录：{when(record)} 做的核对"]
    lines += [f"    稿   {d['name']:<28} {_VERIFY_WORD.get(d['state'], d['state'])}" for d in found.get("drafts") or []]
    lines += [f"    输入 {i['title']:<28} {_VERIFY_WORD.get(i['state'], i['state'])}" for i in found.get("inputs") or []]
    lines.append("    → 核对之后有东西变了：那次核对的三态只对当时的文字成立，请重新核对。" if found.get("stale")
                 else "    → 能重读的都和核对时一致。")
    return lines


def find_for(draft: Path) -> Optional[Tuple[Path, Dict[str, Any]]]:
    """The record a draft belongs to: beside it (``x.check.json`` for ``x.md``), or the workflow's
    ``check.json`` one or two folders up when that record lists the draft."""
    beside = draft.with_name(draft.stem + RECORD_SUFFIX)
    record = load(beside)
    if record is not None:
        return beside, record
    for folder in (draft.parent, draft.parent.parent):
        candidate = folder / WORKFLOW_RECORD
        record = load(candidate)
        if record is not None and any(isinstance(d, Mapping) and d.get("name") == draft.name for d in record.get("drafts") or []):
            return candidate, record
    return None


def latest(records: Iterable[Path], *, skip: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """The most recent loadable record among ``records``."""
    best: Optional[Dict[str, Any]] = None
    for path in records:
        if skip is not None and Path(path) == skip:
            continue
        record = load(Path(path))
        if record is not None and (best is None or float(record.get("checked_at") or 0) > float(best.get("checked_at") or 0)):
            best = record
    return best
