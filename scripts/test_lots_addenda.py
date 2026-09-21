#!/usr/bin/env python3
"""Gate: a tender in several lots with the addenda issued after it - through the real entry point, as Word files.

    python scripts/test_lots_addenda.py

Two made-up pairs of test/benchmarks/real_tender: cn_multilot (three 标段, 补遗书: 修改为 / 调整为 / an answer) and
cn_packages (two 采购包, 更正公告: 变更为 / 延期至 / an answer with no change verb). cn_packages was written after the rules
were frozen on cn_multilot and run once: fields 21/24 with 2 WRONG (the superseded deadline and duration shown as if
they stood), amended 2/4. What is asserted here are the development floors after that.

A superseded value shown as if it stood is the failure this gate exists for: the row that carries the addendum's value
has to say it is the addendum's ("amended"), and the original row has to say it was changed.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import json  # noqa: E402

import eval_real_document as erd  # noqa: E402

BENCH = ROOT / "test" / "benchmarks" / "real_tender"
PAIRS = (("cn_multilot", "cn_multilot.addendum1"), ("cn_packages", "cn_packages.correction1"))
FLOOR = {"fields": "24/24", "fields_wrong": 0, "amended": "4/4"}


def main() -> int:
    failed = []
    for tender, addendum in PAIRS:
        out_dir = ROOT / "output" / f"gate_{tender}"
        erd.deliver(BENCH / f"{tender}.md", out_dir, [BENCH / f"{addendum}.md"], as_word=True)
        md = (out_dir / "tender.parse.md").read_text(encoding="utf-8")
        gold = json.loads((BENCH / f"{tender}.gold.json").read_text(encoding="utf-8"))
        got = erd.score(md, gold, verbose=False)
        print(f"[{tender}] {got}")
        for key, floor in FLOOR.items():
            if got.get(key) != floor:
                failed.append(f"{tender}: {key} {got.get(key)}, the floor is {floor}")
        for key in ("rejections", "scores", "forms"):
            have, want = (int(x) for x in str(got.get(key, "0/0")).split("/"))
            if have < want:
                failed.append(f"{tender}: {key} {have}/{want}")
        # the original row says it was changed - nobody reads "2028年4月18日" as the date that stands
        rows = erd.rows_of(md)
        stale = [r for r in rows if r.get("事项", "").startswith("投标截止") and "补遗" not in r.get("澄清建议", "") + r.get("来源页段", "")
                 and "更正" not in r.get("澄清建议", "") + r.get("来源页段", "") and "已被" not in r.get("澄清建议", "")]
        if stale:
            failed.append(f"{tender}: a superseded 投标截止 row does not say so: {stale[0].get('要求原文')}")
    for line in failed:
        print("FAIL", line)
    print(("FAIL" if failed else "PASS") + f" lots-addenda ({len(PAIRS)} pairs)")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
