#!/usr/bin/env python3
"""What the bid posts get out of a full-length tender, measured on the deliverable a user opens.

    python scripts/eval_real_tender.py                     # the Word file, through `civil exec "解析招标 …"`
    python scripts/eval_real_tender.py --format md         # the same text as a Markdown job file
    python scripts/eval_real_tender.py -v                  # every miss, one line each
    python scripts/eval_real_tender.py --json out.json

The tender is test/benchmarks/real_tender/cn_construction.md (synthetic, the 2007 standard form's
structure, 57 000 characters); the gold is beside it. Everything is read off tender.parse.md - the table a
person opens - never off internal state:

    fields       the row a reader looks in holds the value the tender lays down          (right)
                 ... or holds a number from the contract conditions as if it were it     (wrong - worse than empty)
                 ... or the right value among others, with nothing to tell them apart    (ambiguous)
    clause       the row says which clause the value comes from (1.3.2), not just a line number
    rejections   every clause that gets a bid rejected or refused is on the list
    scores       every scoring row with its points
    specials     every named 危大 item with its figure
    forms        every document the bid must contain (第八章 / 3.1.1)
    seconds      wall time of the run

No model is involved.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Optional
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["PYTHON_DOTENV_DISABLED"] = "1"
for _key in [k for k in os.environ if k.endswith("_API_KEY")] + ["CIVIL_AGENT_MODE"]:
    os.environ.pop(_key, None)

BENCH = ROOT / "test" / "benchmarks" / "real_tender"


def flat(text: str) -> str:
    return re.sub(r"[\s,，]+", "", text or "")


def tables(md: str) -> List[List[Dict[str, str]]]:
    import html

    found: List[List[Dict[str, str]]] = []
    header: Optional[List[str]] = None
    for raw in md.splitlines():
        line = raw.strip()
        if not (line.startswith("|") and line.endswith("|")):
            header = None
            continue
        cells = [html.unescape(c.strip()) for c in line.strip("|").split("|")]
        if all(re.fullmatch(r":?-{2,}:?", c) for c in cells):
            continue
        if header is None:
            header = cells
            found.append([])
            continue
        found[-1].append(dict(zip(header, cells)))
    return found


def deliver(fmt: str, name: str = "cn_construction") -> Dict:
    """Run the real entry point on the tender in a job folder of its own; return the draft and the timing."""
    from packing_assistant.runtime import workspace
    from packing_assistant.runtime.agent_loop import run_agent

    source = (BENCH / f"{name}.md").read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory(prefix="civil-realtender-") as folder:
        job = Path(folder).resolve()
        (job / "CIVIL.md").write_text("- 项目：未填\n", encoding="utf-8")
        if fmt == "docx":
            from packing_assistant.word_export import markdown_docx_bytes

            (job / "招标文件.docx").write_bytes(markdown_docx_bytes(source))
        else:
            (job / f"招标文件.{fmt}").write_text(source, encoding="utf-8")
        cwd = Path.cwd()
        os.chdir(job)
        try:
            with patch.object(Path, "home", return_value=job / "no-home"):
                workspace.activate(job)
            started = time.monotonic()
            out = run_agent(f"解析招标 招标文件.{fmt}", session_id="civil-cli")
            seconds = time.monotonic() - started
            draft = next((Path(f["path"]).read_text(encoding="utf-8") for f in out.get("files") or []
                          if Path(f["path"]).name == "tender.parse.md"), "")
        finally:
            workspace.deactivate()
            os.chdir(cwd)
    return {"ok": bool(out.get("ok")), "reply": str(out.get("reply") or ""), "draft": draft, "seconds": seconds, "source_chars": len(source)}


def measure(draft: str, gold: Dict) -> Dict:
    rows = [row for table in tables(draft) for row in table]
    whole = flat(draft)
    result: Dict = {"fields": {}, "rejections": {}, "scores": {}, "specials": {}, "forms": {}}
    for key, item in gold["fields"].items():
        mine = [row for row in rows if re.search(item["row"], next(iter(row.values()), ""))]
        values = [flat(row.get("要求原文", "")) for row in mine if row.get("是否检出", "已检出") == "已检出"]
        right = [v for v in values if flat(item["value"]) in v]
        bad = [w for w in gold["wrong"].get(key, []) if any(re.search(r"(?<![\d.])" + re.escape(flat(w)), v) and flat(item["value"]) not in v for v in values)]
        others = [v for v in values if v and flat(item["value"]) not in v]
        state = ("wrong" if bad and not right else "ambiguous" if right and others else "right" if right else "missing")
        clause = any(item["clause"].split()[-1] in str(row.get("来源页段", "")) for row in mine if flat(item["value"]) in flat(row.get("要求原文", "")))
        result["fields"][key] = {"state": state, "clause": bool(clause and right), "shown": [row.get("要求原文", "") for row in mine][:6]}
    table_text = flat("".join("".join(row.values()) for row in rows)) + flat("".join(l for l in draft.splitlines() if l.lstrip().startswith("- ")))
    for item in gold["rejections"]:
        result["rejections"][item["id"]] = flat(item["text"]) in table_text
    for item in gold["scores"]:
        result["scores"][item["name"]] = any(flat(item["name"]) in flat("".join(row.values())) and flat(item["score"]) in flat("".join(row.values())) for row in rows)
    for item in gold["specials"]:
        result["specials"][item["name"]] = any(item["name"] in "".join(row.values()) and flat(item["detail"]) in flat("".join(row.values())) for row in rows)
    for name in gold["forms"]:
        result["forms"][name] = flat(name) in whole
    return result


def summary(result: Dict) -> Dict:
    fields = result["fields"]
    count = lambda group: sum(1 for ok in result[group].values() if ok)  # noqa: E731
    return {"fields_right": sum(1 for f in fields.values() if f["state"] == "right"), "fields_wrong": sum(1 for f in fields.values() if f["state"] == "wrong"),
            "fields_ambiguous": sum(1 for f in fields.values() if f["state"] == "ambiguous"), "fields_missing": sum(1 for f in fields.values() if f["state"] == "missing"),
            "fields": len(fields), "clause_refs": sum(1 for f in fields.values() if f["clause"]),
            "rejections": count("rejections"), "rejections_total": len(result["rejections"]), "scores": count("scores"), "scores_total": len(result["scores"]),
            "specials": count("specials"), "specials_total": len(result["specials"]), "forms": count("forms"), "forms_total": len(result["forms"])}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--format", default="docx", choices=("docx", "md", "txt"))
    parser.add_argument("--json")
    parser.add_argument("--show", action="store_true", help="print the deliverable")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()
    gold = json.loads((BENCH / "cn_construction.gold.json").read_text(encoding="utf-8"))
    run = deliver(args.format)
    if args.show:
        print(run["draft"])
    result = measure(run["draft"], gold)
    total = summary(result)
    print(f"cn_construction.{args.format}: {run['source_chars']} chars, run ok={run['ok']}, {run['seconds']:.1f}s, draft {len(run['draft'])} chars")
    print(f"  fields      right {total['fields_right']}/{total['fields']}  wrong {total['fields_wrong']}  ambiguous {total['fields_ambiguous']}  "
          f"missing {total['fields_missing']}  with clause ref {total['clause_refs']}")
    print(f"  rejections  {total['rejections']}/{total['rejections_total']}   scores {total['scores']}/{total['scores_total']}   "
          f"specials {total['specials']}/{total['specials_total']}   forms {total['forms']}/{total['forms_total']}")
    if args.verbose:
        for key, item in result["fields"].items():
            if item["state"] != "right" or not item["clause"]:
                print(f"    field {key:16} {item['state']:9} clause={item['clause']}  shown={item['shown']}")
        for group in ("rejections", "scores", "specials", "forms"):
            missed = [name for name, ok in result[group].items() if not ok]
            if missed:
                print(f"    {group} missed: {missed}")
    if args.json:
        Path(args.json).write_text(json.dumps({"format": args.format, "seconds": run["seconds"], "total": total, "result": result}, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
