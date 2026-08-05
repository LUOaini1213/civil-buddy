#!/usr/bin/env python3
"""非标件检验 CLI。

用法:
  python scripts/inspect_nonstandard.py
  python scripts/inspect_nonstandard.py --preset steel_light
  python scripts/inspect_nonstandard.py --preset high_util --with-boxes
  python scripts/inspect_nonstandard.py --materials output/cases_446t/materials.json
  python scripts/inspect_nonstandard.py --preset steel_light --with-boxes --all-presets
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUT_DIR = ROOT / "output" / "nonstandard_inspect"


def _load_materials(path: Path) -> List[Dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return list(data.get("materials") or data.get("items") or [])
    return []


def _preset_materials(name: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    from packing_assistant.demo_presets import (
        materials_five_boxes,
        materials_high_util,
        materials_steel_light,
        packing_options_high_util,
        packing_options_standard,
    )

    n = (name or "steel_light").lower().strip()
    if n in ("high_util", "满载", "full"):
        return materials_high_util(), packing_options_high_util()
    if n in ("five", "five_boxes", "5"):
        return materials_five_boxes(), packing_options_standard()
    return materials_steel_light(), packing_options_standard()


def _maybe_boxes(
    materials: List[Dict[str, Any]],
    opts: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    from packing_assistant.agents.box_scheme import agent_box_scheme

    out = agent_box_scheme(
        {
            "materials": materials,
            "packing_options": dict(opts or {}),
            "messages": [],
        }
    )
    return list(out.get("boxes") or [])


def run_one(
    *,
    case_id: str,
    materials: List[Dict[str, Any]],
    boxes: Optional[List[Dict[str, Any]]] = None,
    container_type: str = "40HQ",
) -> Dict[str, Any]:
    from packing_assistant.tools.nonstandard_inspect import inspect_nonstandard, report_markdown

    from packing_assistant.tools.nl_nonstandard_enrich import enrich_materials
    from packing_assistant.tools.nonstandard_inspect import public_summary

    mats = enrich_materials(list(materials or []), force_llm=False)
    rep = inspect_nonstandard(
        materials=mats,
        boxes=boxes,
        container_type=container_type,
        case_id=case_id,
    )
    rep["generated_at"] = datetime.now(timezone.utc).isoformat()
    rep["markdown"] = report_markdown(rep)
    rep["public_summary"] = public_summary(rep)
    return rep


def main() -> int:
    ap = argparse.ArgumentParser(description="非标件检验")
    ap.add_argument("--materials", type=str, default="", help="materials.json 路径")
    ap.add_argument(
        "--preset",
        type=str,
        default="steel_light",
        help="steel_light | high_util | five",
    )
    ap.add_argument("--all-presets", action="store_true", help="跑全部演示预设")
    ap.add_argument("--with-boxes", action="store_true", help="先成箱再检箱")
    ap.add_argument("--container", type=str, default="40HQ")
    ap.add_argument("--also-446t", action="store_true", help="附加 446t 物料表")
    ap.add_argument("--out-dir", type=str, default=str(OUT_DIR))
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    jobs: List[Tuple[str, List[Dict[str, Any]], Dict[str, Any]]] = []

    if args.materials:
        p = Path(args.materials)
        if not p.is_absolute():
            p = ROOT / p
        jobs.append((p.stem, _load_materials(p), {}))
    elif args.all_presets:
        for name in ("steel_light", "high_util", "five"):
            mats, opts = _preset_materials(name)
            jobs.append((f"preset_{name}", mats, opts))
    else:
        mats, opts = _preset_materials(args.preset)
        jobs.append((f"preset_{args.preset}", mats, opts))

    if args.also_446t or (not args.materials and args.all_presets):
        p446 = ROOT / "output" / "cases_446t" / "materials.json"
        if p446.exists():
            jobs.append(("case_446t", _load_materials(p446), {
                "crate_passthrough": True,
                "dense_mode": True,
                "standard_boxes": False,
            }))

    index: List[Dict[str, Any]] = []
    for case_id, materials, opts in jobs:
        print(f"=== {case_id} n_mats={len(materials)} ===")
        boxes = None
        if args.with_boxes and materials:
            try:
                boxes = _maybe_boxes(materials, opts)
                print(f"  boxes={len(boxes)}")
            except Exception as e:
                print(f"  box_scheme skip: {e}")
        rep = run_one(
            case_id=case_id,
            materials=materials,
            boxes=boxes,
            container_type=args.container,
        )
        stem = case_id.replace("/", "_")
        jp = out_dir / f"{stem}.json"
        mp = out_dir / f"{stem}.md"
        # strip markdown from json duplicate bulk? keep short
        payload = {k: v for k, v in rep.items() if k != "markdown"}
        # trim checks in materials for size on huge tickets
        if len(payload.get("materials") or []) > 200:
            for row in payload["materials"]:
                row.pop("checks", None)
            for row in payload.get("nonstandard_materials") or []:
                row.pop("checks", None)
        jp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        mp.write_text(rep["markdown"], encoding="utf-8")
        sm = rep.get("summary") or {}
        print(
            f"  overall={rep.get('overall')} ns_mat={sm.get('n_nonstandard_materials')} "
            f"fail={sm.get('n_fail')} warn={sm.get('n_warn')} → {mp}"
        )
        index.append(
            {
                "case_id": case_id,
                "overall": rep.get("overall"),
                "summary": sm,
                "json": str(jp.relative_to(ROOT)),
                "md": str(mp.relative_to(ROOT)),
            }
        )

    # combined summary report
    summary_md = ["# 非标件检验汇总", "", f"生成: {datetime.now().isoformat(timespec='seconds')}", ""]
    summary_md += ["| case | overall | mats | ns_mat | fail | warn | report |", "|------|---------|-----:|-------:|-----:|-----:|--------|"]
    for it in index:
        sm = it.get("summary") or {}
        summary_md.append(
            f"| {it['case_id']} | **{it['overall']}** | {sm.get('n_materials')} | "
            f"{sm.get('n_nonstandard_materials')} | {sm.get('n_fail')} | {sm.get('n_warn')} | "
            f"`{it['md']}` |"
        )
    summary_md += [
        "",
        "## 使用",
        "",
        "```bash",
        "python scripts/inspect_nonstandard.py --all-presets --with-boxes --also-446t",
        "python scripts/inspect_nonstandard.py --materials path/to/materials.json --with-boxes",
        "```",
        "",
        "规则: `packing_assistant/tools/nonstandard_inspect.py`",
        "",
    ]
    (out_dir / "SUMMARY.md").write_text("\n".join(summary_md), encoding="utf-8")
    (out_dir / "INDEX.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    print("wrote", out_dir / "SUMMARY.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
