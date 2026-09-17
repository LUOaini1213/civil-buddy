#!/usr/bin/env python3
"""pack-ship 不得为没有外形尺寸的行出方案，也不得把「0 个箱」报成成功。

修复前：表头写成「L (mm) / W (mm) / H (mm)」的装箱单三列尺寸全部对不上，行以
0×0×0 进引擎，run_plan 返回 ok=True、can_fit=False、containers_used=0、n_boxes=0。
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packing_assistant.tools import pack_ship_solve  # noqa: E402
from packing_assistant.tools.pack_ship_mcp import ingest_tool  # noqa: E402
from packing_assistant.tools.pack_ship_solve import (  # noqa: E402
    draft_booking,
    draft_vgm,
    rows_blocking_plan,
    rows_missing_dimensions,
    run_plan,
)

LWH_SHEET = (
    "S/N,Description of Goods,Q'ty,L (mm),W (mm),H (mm),G.W. (kg)\n"
    "1,Steel bracket,4,1200,400,300,12.5\n"
    "2,Base plate,2,800,800,50,40\n"
)
NO_DIMS_SHEET = (
    "S/N,Description of Goods,Q'ty,G.W. (kg)\n"
    "1,Steel bracket,4,12.5\n"
    "2,Base plate,2,40\n"
)


def _row(**extra):
    base = {"id": "R1", "name": "Panel", "quantity": 1, "weight_kg": 50,
            "length_mm": 2000, "width_mm": 1000, "height_mm": 100}
    base.update(extra)
    return base


def _plan_from(sheet: str) -> dict:
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "list.csv"
        path.write_text(sheet, encoding="utf-8", newline="")
        return run_plan(file_path=str(path))


def main() -> int:
    # 1. 行级判定：与引擎同口径（length_mm / sizeMm / 外尺寸_mm 任一来源为正即可）
    assert rows_missing_dimensions([_row()]) == []
    assert rows_missing_dimensions([_row(length_mm="2000")]) == []
    assert rows_missing_dimensions([_row(length_mm=0, width_mm=0, height_mm=0, sizeMm={"l": 2000, "w": 1000, "h": 100})]) == []
    assert rows_missing_dimensions([_row(length_mm=None, width_mm=None, height_mm=None,
                                         **{"外尺寸_mm": {"长": 2000, "宽": 1000, "高": 100}})]) == []
    for label, extra, want in (
        ("all zero", {"length_mm": 0, "width_mm": 0, "height_mm": 0}, ["length_mm", "width_mm", "height_mm"]),
        ("height absent", {"height_mm": None}, ["height_mm"]),
        ("negative width", {"width_mm": -5}, ["width_mm"]),
        ("NaN length", {"length_mm": float("nan")}, ["length_mm"]),
        ("inf length", {"length_mm": float("inf")}, ["length_mm"]),
        ("non-numeric", {"length_mm": "abc"}, ["length_mm"]),
        # 引擎取 `length_mm or sizeMm.l or …` 的第一个真值："0" 是真值，会挡住后面的 2000
        ("string zero shadows sizeMm", {"length_mm": "0", "sizeMm": {"l": 2000, "w": 1000, "h": 100}}, ["length_mm"]),
    ):
        flagged = rows_missing_dimensions([_row(**extra)])
        assert len(flagged) == 1 and flagged[0]["missing"] == want, (label, flagged)
        assert flagged[0]["reason"] == "missing_dimensions", (label, flagged)

    # 2. 回归：单字母加单位的表头现在能装，且确实出了箱和柜
    plan = _plan_from(LWH_SHEET)
    assert plan["ok"] is True and plan["source"] == "solver", plan
    assert plan["n_boxes"] >= 1 and isinstance(plan["containers_used"], int) and plan["containers_used"] >= 1, plan
    assert set(plan["parse"]["column_map"].values()) >= {"length_mm", "width_mm", "height_mm"}, plan["parse"]

    # 3. 整表没有尺寸列：停下来问人，不给柜数
    gated = _plan_from(NO_DIMS_SHEET)
    assert gated["ok"] is False and gated["source"] == "needs_human", gated
    assert gated["error"] == "missing_dimensions", gated
    assert len(gated["needs_human"]) == 2, gated
    assert "containers_used" not in gated, "缺尺寸时不允许给出柜数"

    # 4. 同时缺重量与尺寸：先报重量，两种原因一次列全
    both = rows_blocking_plan([_row(weight_kg=0, height_mm=0, meta={"weight_missing": True})])
    assert [r["reason"] for r in both] == ["missing_weight", "missing_dimensions"], both
    blocked = run_plan(materials=[_row(weight_kg=0, height_mm=0, meta={"weight_missing": True})])
    assert blocked["error"] == "missing_weight" and len(blocked["needs_human"]) == 2, blocked

    # 5. ingest 报的就是 plan 会拒的那些行；两个草稿工具同样被拦
    ingest = ingest_tool(materials=[_row(height_mm=0)])
    assert ingest["ok"] is False and ingest["needs_human"][0]["reason"] == "missing_dimensions", ingest
    for fn in (draft_vgm, draft_booking):
        refused = fn(materials=[_row(height_mm=0)])
        assert refused["ok"] is False and refused["error"] == "missing_dimensions", (fn.__name__, refused)

    # 6. 闸门之后引擎仍一个箱都没出：不是成功，也不给柜数
    empty = {"boxes": [], "plan": {"can_fit": False, "containers_used": 0}, "booking": {}, "feasibility": {}, "state": {}}
    with patch.object(pack_ship_solve, "_solve_boxes", return_value=empty):
        nothing = run_plan(materials=[_row()])
        assert nothing["ok"] is False and nothing["error"] == "no_boxes", nothing
        assert "containers_used" not in nothing, nothing
        for fn in (draft_vgm, draft_booking):
            assert fn(materials=[_row()])["error"] == "no_boxes", fn.__name__

    print(f"PASS pack_ship_dimension_gate lwh_sheet=containers:{plan['containers_used']},boxes:{plan['n_boxes']} "
          f"no_dims=needs_human both=weight_then_dimensions empty_plan=no_boxes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
