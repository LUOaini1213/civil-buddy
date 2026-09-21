#!/usr/bin/env python3
"""A REAL tender document, run once through the real entry point and scored against a gold somebody read off it.

    python scripts/eval_real_document.py 招标文件.pdf                      # run, write the drafts, print what was found
    python scripts/eval_real_document.py 招标文件.pdf --gold gold.json     # ... and score it
    python scripts/eval_real_document.py 招标文件.pdf --gold gold.json --out output/real/run1 -v

Neither the document nor its gold belongs in this repository: a tender is its buyer's text. Keep both under
output/ (ignored). What is committed are the numbers (test/benchmarks/real_tender/README.md) and this script.

gold.json - every string a literal stretch of the document, compared after folding whitespace and width:

    {"fields":     [{"label": "工期", "expect": "80 日历天"}, {"label": "招标编号", "absent": true}],
     "rejections": ["其响应文件作废标处理", ...],        clauses that get a bid thrown out
     "review":     ["具备有效的营业执照", ...],          the standards of the preliminary review
     "scores":     [["技术部分", "40"], ...],
     "forms":      ["响应函及响应函附录", ...]}

    right     a row whose label starts with `label` holds the expected text
    wrong     rows with that label show values and none holds it - or a row shows a value where the tender has none
    missing   no such row, or 未检出

The first run on a document, with the rules frozen, is the number to quote. Whatever is fixed afterwards on the same
document is a development number.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
import sys
import tempfile
import time
import unicodedata
from pathlib import Path
from typing import Dict, List
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["PYTHON_DOTENV_DISABLED"] = "1"
for _key in [k for k in os.environ if k.endswith("_API_KEY")] + ["CIVIL_AGENT_MODE"]:
    os.environ.pop(_key, None)


def flat(text: str) -> str:
    return re.sub(r"[\s,，]+", "", unicodedata.normalize("NFKC", text or ""))


def rows_of(md: str) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    header = None
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
            continue
        out.append(dict(zip(header, cells)))
    return out


def deliver(source: Path, out_dir: Path) -> Dict:
    from packing_assistant.runtime import workspace
    from packing_assistant.runtime.agent_loop import run_agent

    out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="civil-real-", dir=str(ROOT / "output")) as folder:
        job = Path(folder).resolve()
        (job / "CIVIL.md").write_text("- 项目：未填\n", encoding="utf-8")
        target = job / ("招标文件" + source.suffix.lower())
        shutil.copyfile(source, target)
        cwd = Path.cwd()
        os.chdir(job)
        try:
            with patch.object(Path, "home", return_value=job / "no-home"):
                workspace.activate(job)
            started = time.monotonic()
            result = run_agent(f"解析招标 {target.name}", session_id="civil-cli")
            seconds = time.monotonic() - started
            for f in result.get("files") or []:
                path = Path(f["path"])
                if path.exists():
                    shutil.copyfile(path, out_dir / path.name)
        finally:
            workspace.deactivate()
            os.chdir(cwd)
    return {"ok": bool(result.get("ok")), "seconds": seconds, "reply": str(result.get("reply") or "")}


def score(md: str, gold: Dict, verbose: bool) -> Dict[str, object]:
    rows = rows_of(md)
    tally = {"right": 0, "wrong": 0, "missing": 0}
    for item in gold.get("fields", []):
        shown = [r for r in rows if r.get("事项", "").startswith(item["label"]) and r.get("是否检出") == "已检出"]
        if item.get("absent"):
            state = "wrong" if shown else "right"
        elif any(flat(item["expect"]) in flat(r.get("要求原文", "")) for r in shown):
            state = "right"
        else:
            state = "wrong" if shown else "missing"
        tally[state] += 1
        if verbose or state != "right":
            print(f"  {state.upper():8s}{item['label']}: want {item.get('expect', '(nothing)')!r}  shown={[r.get('要求原文', '')[:50] for r in shown][:3]}")
    out: Dict[str, object] = {"fields": f"{tally['right']}/{len(gold.get('fields', []))}", "fields_wrong": tally["wrong"]}
    print(f"fields {out['fields']}  wrong {tally['wrong']}  missing {tally['missing']}")
    for key, prefixes in (("rejections", ("否决条款", "★")), ("review", ("形式", "资格", "响应性", "符合性", "实质性")), ("forms", ("组成",))):
        wanted = gold.get(key) or []
        if not wanted:
            continue
        mine = [flat(r.get("要求原文", "")) for r in rows if r.get("事项", "").startswith(prefixes)]
        net = [flat(r.get("要求原文", "")) for r in rows if r.get("事项", "").startswith("弱信号")] if key == "rejections" else []
        got = [w for w in wanted if any(flat(w) in m for m in mine)]
        caught = [w for w in wanted if any(flat(w) in m for m in mine + net)]
        out[key] = f"{len(got)}/{len(wanted)}"
        print(f"{key} {out[key]}  listed {len(mine)}" + (f"  with the weak-signal net {len(caught)}/{len(wanted)} (net {len(net)})" if key == "rejections" else ""))
        for w in wanted:
            if w not in caught:
                print(f"  MISS {key}: {w}")
    wanted = gold.get("scores") or []
    if wanted:
        mine = [(flat(r.get("事项", "")), flat(r.get("要求原文", ""))) for r in rows if r.get("事项", "").startswith("评分点")]
        got = [pair for pair in wanted if any(flat(pair[0]) in a and flat(pair[1]) in b for a, b in mine)]
        out["scores"] = f"{len(got)}/{len(wanted)}"
        print(f"scores {out['scores']}  listed {len(mine)}")
        for pair in wanted:
            if pair not in got:
                print(f"  MISS score: {pair}")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("tender", help="the tender document: .pdf / .docx / .txt / .md")
    parser.add_argument("--gold", help="gold.json read off the document by hand")
    parser.add_argument("--out", help="where the drafts go (default: output/real/<file name>)")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()
    source = Path(args.tender).resolve()
    out_dir = Path(args.out).resolve() if args.out else ROOT / "output" / "real" / source.stem
    run = deliver(source, out_dir)
    draft = out_dir / "tender.parse.md"
    md = draft.read_text(encoding="utf-8") if draft.exists() else ""
    banner = next((line for line in md.splitlines() if line.startswith("> 按文件结构解析")), "")
    print(f"{source.name}: run ok={run['ok']}, {run['seconds']:.1f}s, draft {len(md)} chars -> {out_dir}")
    print(" ", banner[2:80] if banner else "(not read as a document)")
    if args.gold:
        score(md, json.loads(Path(args.gold).read_text(encoding="utf-8")), args.verbose)
    else:
        rows = rows_of(md)
        for label in ("否决条款", "弱信号", "评分点", "组成"):
            print(f"  {label}: {sum(1 for r in rows if r.get('事项', '').startswith(label))} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
