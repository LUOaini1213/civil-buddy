#!/usr/bin/env python3
"""比赛一键演示：材料表/样例 → Agent 全流程报告（O-01）。

用法:
  python scripts/competition_demo_one_shot.py
  python scripts/competition_demo_one_shot.py --table test/generic_tables/G1_ecommerce_cartons/materials.csv
  python scripts/competition_demo_one_shot.py --preset high_util
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env")
    except Exception:
        pass


def materials_from_preset(name: str) -> List[Dict[str, Any]]:
    from packing_assistant import demo_presets as dp

    fn = {
        "high_util": getattr(dp, "materials_high_util", None),
        "steel_light": getattr(dp, "materials_steel_light", None),
        "five_boxes": getattr(dp, "materials_five_boxes", None),
    }.get(name)
    if not fn:
        raise SystemExit(f"unknown preset {name}")
    return list(fn())


def materials_from_table(path: Path) -> List[Dict[str, Any]]:
    from packing_assistant.tools.table_mapper import parse_table_file

    r = parse_table_file(path)
    if not r["ok"]:
        raise SystemExit(f"parse failed: {path}")
    mats = r["materials"]
    # expand modest quantities for demo visibility
    out: List[Dict[str, Any]] = []
    for m in mats:
        qty = max(1, int(m.get("quantity") or 1))
        if qty > 20:
            # keep as bulk row
            out.append(m)
            continue
        for i in range(qty):
            item = dict(m)
            item["quantity"] = 1
            item["total_weight_kg"] = float(m.get("weight_kg") or 0)
            if qty > 1:
                item["id"] = f"{m.get('id')}-{i+1}"
            out.append(item)
    return out


def main() -> int:
    _load_dotenv()
    ap = argparse.ArgumentParser(description="Competition one-shot demo")
    ap.add_argument("--table", type=str, default="", help="CSV/XLSX/JSON path")
    ap.add_argument("--preset", type=str, default="high_util", help="demo preset if no table")
    ap.add_argument("--container", type=str, default="40HQ")
    ap.add_argument("--out", type=str, default="")
    args = ap.parse_args()

    if args.table:
        table_path = Path(args.table)
        if not table_path.is_absolute():
            table_path = ROOT / table_path
        mats = materials_from_table(table_path)
        label = table_path.name
        source = str(table_path.relative_to(ROOT)) if table_path.is_relative_to(ROOT) else str(table_path)
    else:
        mats = materials_from_preset(args.preset)
        label = args.preset
        source = f"preset:{args.preset}"

    from packing_assistant.config import HARNESS_VERSION
    from packing_assistant.harness import public_response, run_agent_pipeline

    t0 = time.time()
    st = run_agent_pipeline(
        f"competition demo {label}",
        materials=mats,
        container_type=args.container,
        enable_auto_confirm=True,
        session_id=f"demo-{label}",
        packing_options={"crate_passthrough": True, "multi_start": True, "cog_aware": True},
    )
    pub = public_response(st)
    ms = int((time.time() - t0) * 1000)

    plan = pub.get("container_plan") or {}
    used = plan.get("containers_used") or plan.get("used") or pub.get("containers_used")
    mid50 = None
    lq = plan.get("layout_quality") or pub.get("layout_quality") or {}
    if isinstance(lq, dict):
        mid50 = lq.get("mid50") or lq.get("mid50_ratio")
    if mid50 is None:
        mid50 = plan.get("mid50") or pub.get("mid50")

    # recommended container from team_a if present
    ta = pub.get("team_a_summary") or st.get("team_a_summary") or {}
    recommend = ta.get("recommended_containers") or ta.get("suggest_containers") or pub.get("recommended_container")

    report = {
        "title": "competition_demo_one_shot",
        "ts": datetime.now(timezone.utc).isoformat(),
        "harness": HARNESS_VERSION,
        "source": source,
        "container_type": args.container,
        "n_materials": len(mats),
        "phase": pub.get("phase") or st.get("phase"),
        "team_mode": pub.get("team_mode") or st.get("team_mode"),
        "can_fit": plan.get("can_fit"),
        "containers_used": used,
        "ship_ok": pub.get("ship_ok"),
        "mid50": mid50,
        "risk": pub.get("risk") or plan.get("risk"),
        "strategy": plan.get("strategy") or pub.get("strategy"),
        "recommended_containers": recommend,
        "n_agent_steps": len(pub.get("agent_steps") or st.get("agent_steps") or []),
        "n_boxes": len(pub.get("boxes") or st.get("boxes") or []),
        "ms": ms,
        "ok": bool(plan.get("can_fit") or pub.get("ship_ok")),
    }

    out_dir = Path(args.out) if args.out else ROOT / "output" / "competition"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "demo_one_shot_latest.json"
    md_path = out_dir / "demo_one_shot_latest.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    md = [
        "# 比赛一键演示报告",
        "",
        f"- **时间**: {report['ts']}",
        f"- **Harness**: {report['harness']}",
        f"- **来源**: `{report['source']}`",
        f"- **材料行/件**: {report['n_materials']}",
        f"- **phase**: {report['phase']}",
        f"- **can_fit**: {report['can_fit']}",
        f"- **used**: {report['containers_used']}",
        f"- **ship_ok**: {report['ship_ok']}",
        f"- **mid50**: {report['mid50']}",
        f"- **strategy**: {report['strategy']}",
        f"- **recommended**: {report['recommended_containers']}",
        f"- **agent_steps**: {report['n_agent_steps']}",
        f"- **耗时 ms**: {report['ms']}",
        "",
        "## 答辩一句话",
        "",
        "> 任意材料表 → tools 对齐字段 → boxes → N0* + 3D/CoG；坐标由引擎写，模型只做意图与解释。",
        "",
    ]
    md_path.write_text("\n".join(md), encoding="utf-8")

    print("OK" if report["ok"] else "WARN", json.dumps({k: report[k] for k in (
        "source", "n_materials", "can_fit", "containers_used", "ship_ok", "mid50", "phase", "ms", "ok"
    )}, ensure_ascii=False))
    print("WROTE", json_path)
    print("WROTE", md_path)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
