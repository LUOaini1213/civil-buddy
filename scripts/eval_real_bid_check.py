#!/usr/bin/env python3
"""Does the full bid check find what is wrong with a bid - and leave alone what is right?

    python scripts/eval_real_bid_check.py                      # bid_cn_construction (dev)
    python scripts/eval_real_bid_check.py --set bid_cn_municipal -v
    python scripts/eval_real_bid_check.py --show               # print the compliance draft

A set is a real-shaped tender of test/benchmarks/real_tender, our own bid files with planted defects, and
what the compliance draft has to say. Everything runs through the real entry point
(`civil exec "全面检查投标响应：…"` in a job folder, Word files with real tables) and is read off
bid-compliance.md, by table cell:

    exceeds            the field's row is 未响应·数值不符, shows the offending value and names the file
    inconsistent       section 9 lists the field as 不一致 with every writing of it
    missing_special    the named 危大 item's row says it is not in our files
    no_response        the field's row is 未响应
    ok                 the field's row shows our value and is 已响应·待核验          (a false alarm otherwise)
    present_special    the named item's row is 已响应·待核验                        (a false alarm otherwise)
    not_inconsistent   section 9 does not list the field as 不一致                  (a false alarm otherwise)

caught = defects found / defects planted; false alarms = right things flagged. No model is involved.
"""
from __future__ import annotations

import argparse
import html
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
DEFECTS = ("exceeds", "inconsistent", "missing_special", "no_response")


def flat(text: str) -> str:
    return re.sub(r"[\s,，]+", "", text or "")


def tables(md: str) -> List[List[Dict[str, str]]]:
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


def deliver(case: Dict) -> Dict:
    from packing_assistant.runtime import workspace
    from packing_assistant.runtime.agent_loop import run_agent
    from packing_assistant.word_export import markdown_docx_bytes

    tender = (BENCH / f"{case['tender']}.md").read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory(prefix="civil-bidcheck-") as folder:
        job = Path(folder).resolve()
        (job / "CIVIL.md").write_text("- 项目：未填\n", encoding="utf-8")
        (job / "招标文件.docx").write_bytes(markdown_docx_bytes(tender))
        for name, text in case["files"].items():
            (job / name).write_bytes(markdown_docx_bytes(text))
        cwd = Path.cwd()
        os.chdir(job)
        try:
            with patch.object(Path, "home", return_value=job / "no-home"):
                workspace.activate(job)
            started = time.monotonic()
            out = run_agent(case["request"], session_id="civil-cli")
            seconds = time.monotonic() - started
            draft = next((Path(f["path"]).read_text(encoding="utf-8") for f in out.get("files") or []
                          if Path(f["path"]).name == "bid-compliance.md"), "")
        finally:
            workspace.deactivate()
            os.chdir(cwd)
    return {"ok": bool(out.get("ok")), "reply": str(out.get("reply") or ""), "draft": draft, "seconds": seconds}


def judge(draft: str, expect: List[Dict]) -> List[Dict]:
    rows = [row for table in tables(draft) for row in table]
    fields = [r for r in rows if "三态" in r]
    nine = [r for r in rows if "是否一致" in r]
    out: List[Dict] = []
    for item in expect:
        kind = item["kind"]
        mine = [r for r in fields if next(iter(r.values()), "").startswith(item.get("row", "\0"))]
        named = [r for r in fields if item.get("name") and item["name"] in "".join(r.values()) and next(iter(r.values()), "").startswith("点名专项")]
        listed = [r for r in nine if r.get("事项", "").startswith(item.get("label", "\0"))]
        if kind == "exceeds":
            ok = any("数值不符" in r["三态"] and flat(item["value"]) in flat(r["响应原文或证据"]) and item["file"] in r["缺口"] + r["响应原文或证据"] for r in mine)
        elif kind == "inconsistent":
            ok = any("不一致" in r["是否一致"] and all(flat(v) in flat(r["各文件写法"]) for v in item["values"]) for r in listed)
            in_row = [r for r in fields if next(iter(r.values()), "").startswith(item["label"])]
            ok = ok and any("不一致" in r["缺口"] for r in in_row)   # ... and the field's own row says so too
        elif kind == "missing_special":
            ok = any(r["三态"].startswith("未响应") for r in named)
        elif kind == "no_response":
            ok = any(r["三态"] == "未响应" for r in mine)
        elif kind == "ok":
            ok = any(r["三态"] == "已响应·待核验" and flat(item["value"]) in flat(r["响应原文或证据"]) for r in mine)
        elif kind == "present_special":
            ok = any(r["三态"] == "已响应·待核验" for r in named)
        elif kind == "not_inconsistent":
            ok = not any("不一致" in r["是否一致"] for r in listed)
        else:
            raise ValueError(kind)
        shown = [f"{next(iter(r.values()), '')}｜{r.get('响应原文或证据', r.get('各文件写法', ''))[:60]}｜{r.get('三态', r.get('是否一致', ''))}"
                 for r in (mine or named or listed)][:3]
        out.append({**item, "pass": bool(ok), "shown": shown})
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--set", default="bid_cn_construction")
    parser.add_argument("--show", action="store_true")
    parser.add_argument("--json")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()
    case = json.loads((BENCH / f"{args.set}.json").read_text(encoding="utf-8"))
    run = deliver(case)
    if args.show:
        print(run["draft"])
    verdicts = judge(run["draft"], case["expect"])
    defects = [v for v in verdicts if v["kind"] in DEFECTS]
    rights = [v for v in verdicts if v["kind"] not in DEFECTS]
    caught, alarms = sum(v["pass"] for v in defects), sum(not v["pass"] for v in rights)
    print(f"{args.set}: run ok={run['ok']}, {run['seconds']:.1f}s, draft {len(run['draft'])} chars")
    print(f"  defects caught {caught}/{len(defects)}   false alarms {alarms}/{len(rights)}")
    if args.verbose or caught < len(defects) or alarms:
        for v in verdicts:
            if not v["pass"]:
                what = {k: v[k] for k in v if k not in ("pass", "shown")}
                print(f"    MISS {json.dumps(what, ensure_ascii=False)}  shown={v['shown']}")
    if args.json:
        Path(args.json).write_text(json.dumps({"set": args.set, "seconds": run["seconds"], "caught": caught, "defects": len(defects),
                                               "false_alarms": alarms, "rights": len(rights), "verdicts": verdicts}, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
