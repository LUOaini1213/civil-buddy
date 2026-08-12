#!/usr/bin/env python3
"""
自然语言改方案标准交付契约回归。

驱动 shipped 入口：
  - packing_assistant.tools.nl_revision.parse_nl_revision
  - packing_assistant.tools.nl_revision.revise_with_natural_language
  - packing_assistant.harness.revise_plan_nl（不静默假成功）
  - packing_assistant.tools.packing.run_packing（prefer_single_row 可观察）

断言：
  1) 可改「要一排」→ status=applied + prefer_single_row
  2) 不可改「帮我算运费」/空串 → status=unsupported + 无此功能；boxes/materials 不变
  3) 单排 vs 两排：外宽或 two_row_ok / 特殊属性可区分
"""

from __future__ import annotations

import copy
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PACKING_SKIP_SKJOLBER", "1")
os.environ.setdefault("PACKING_FINALIZE_LLM", "0")
os.environ.setdefault("PACKING_LLM_TOOLCALL", "0")


def _base_state() -> Dict[str, Any]:
    return {
        "session_id": "nl_contract_test",
        "user_input": "契约测试物料",
        "materials": [
            {
                "name": "连接板",
                "qty": 2,
                "weight_kg": 12.0,
                "length_mm": 400,
                "width_mm": 300,
                "height_mm": 20,
            },
            {
                "name": "密实模块",
                "qty": 4,
                "weight_kg": 800.0,
                "length_mm": 1000,
                "width_mm": 1000,
                "height_mm": 1000,
            },
        ],
        "boxes": [{"id": "BOX-01", "box_type": "1.1米框(定制)"}],
        "packing_options": {"dense_mode": True, "standard_boxes": False},
        "container_type": "40HQ",
        "design_facts": {},
        "agent_steps": [],
        "messages": [],
    }


def test_parse_applied_and_unsupported() -> None:
    from packing_assistant.tools.nl_revision import parse_nl_revision

    p_ok = parse_nl_revision("要一排")
    assert p_ok.get("ok") is True, p_ok
    assert p_ok.get("feature_available") is True, p_ok
    assert p_ok.get("status") in ("parsed", "applied"), p_ok
    keys = {str(o.get("key")) for o in (p_ok.get("ops") or []) if o.get("op") == "set_packing_option"}
    assert "prefer_single_row" in keys, p_ok
    print("PASS parse 要一排 → ops prefer_single_row")

    p_bad = parse_nl_revision("帮我算运费")
    assert p_bad.get("ok") is False, p_bad
    assert p_bad.get("status") == "unsupported", p_bad
    assert p_bad.get("feature_available") is False, p_bad
    assert str(p_bad.get("message") or "").startswith("无此功能"), p_bad
    print("PASS parse 运费 → unsupported 无此功能")

    p_empty = parse_nl_revision("")
    assert p_empty.get("ok") is False, p_empty
    assert p_empty.get("status") == "unsupported", p_empty
    assert str(p_empty.get("message") or "").startswith("无此功能"), p_empty
    print("PASS parse 空串 → unsupported 无此功能")


def test_revise_with_nl_applied_and_frozen() -> None:
    from packing_assistant.tools.nl_revision import revise_with_natural_language

    base = _base_state()
    mats0 = copy.deepcopy(base["materials"])
    boxes0 = copy.deepcopy(base["boxes"])

    # unsupported: state frozen
    s_bad = revise_with_natural_language(copy.deepcopy(base), "帮我算运费")
    nr = s_bad.get("nl_revision") or {}
    assert nr.get("status") == "unsupported", nr
    assert nr.get("applied") is False, nr
    assert nr.get("feature_available") is False, nr
    assert str(nr.get("message") or "").startswith("无此功能"), nr
    assert s_bad.get("materials") == mats0, "unsupported 不得改 materials"
    assert s_bad.get("boxes") == boxes0, "unsupported 不得改 boxes"
    assert s_bad.get("packing_options") == base["packing_options"], "unsupported 不得改 packing_options"
    print("PASS revise_with_nl 运费 → frozen + 无此功能")

    # applied: prefer_single_row
    s_ok = revise_with_natural_language(copy.deepcopy(base), "要一排的")
    nr2 = s_ok.get("nl_revision") or {}
    assert nr2.get("ok") is True, nr2
    assert nr2.get("applied") is True, nr2
    assert nr2.get("status") == "applied", nr2
    assert nr2.get("feature_available") is True, nr2
    opts = s_ok.get("packing_options") or {}
    assert opts.get("prefer_single_row") is True, opts
    assert opts.get("prefer_two_row") is False, opts
    assert opts.get("standard_boxes") is False, opts
    logs = nr2.get("logs") or []
    assert logs, nr2
    assert any("prefer_single_row" in str(x) for x in logs), logs
    print("PASS revise_with_nl 要一排的 → applied + prefer_single_row")


def test_revise_plan_nl_no_silent_rerun_on_unsupported() -> None:
    """unsupported 不得进入假成功重算路径；applied 写回 status。"""
    from packing_assistant.harness import revise_plan_nl

    base = _base_state()
    mats0 = copy.deepcopy(base["materials"])
    boxes0 = copy.deepcopy(base["boxes"])

    out = revise_plan_nl(copy.deepcopy(base), "帮我算运费", rerun_team_a=True)
    nr = out.get("nl_revision") or {}
    assert nr.get("status") == "unsupported", nr
    assert nr.get("applied") is False, nr
    assert nr.get("rerun") is False, nr
    assert str(nr.get("message") or "").startswith("无此功能"), nr
    assert out.get("materials") == mats0
    assert out.get("boxes") == boxes0
    print("PASS revise_plan_nl 运费 → unsupported 不重跑")

    # applied without full team A rerun (keeps unit fast, still shipped entry)
    out2 = revise_plan_nl(copy.deepcopy(base), "要一排", rerun_team_a=False)
    nr2 = out2.get("nl_revision") or {}
    assert nr2.get("status") == "applied", nr2
    assert nr2.get("applied") is True, nr2
    assert (out2.get("packing_options") or {}).get("prefer_single_row") is True
    print("PASS revise_plan_nl 要一排 rerun=False → applied")


def test_single_row_packing_observable() -> None:
    from packing_assistant.tools.packing import run_packing

    # 中等宽度货：默认两排 snappoint；prefer_single_row 强制单排外宽
    mats: List[Dict[str, Any]] = [
        {
            "name": f"模块{i}",
            "数量": 1,
            "单重_kg": 400.0,
            "总重_kg": 400.0,
            "外尺寸_mm": {"长": 1000.0, "宽": 1000.0, "高": 900.0},
        }
        for i in range(1, 5)
    ]
    # run_packing 接受 materials 字典或内部格式；走 normalize
    mats_api = [
        {
            "name": m["name"],
            "qty": 1,
            "weight_kg": 400.0,
            "length_mm": 1000,
            "width_mm": 1000,
            "height_mm": 900,
        }
        for m in mats
    ]

    r_two = run_packing(
        mats_api,
        container_type="40HQ",
        dense_mode=True,
        standard_boxes=False,
        prefer_single_row=False,
    )
    r_one = run_packing(
        mats_api,
        container_type="40HQ",
        dense_mode=True,
        standard_boxes=False,
        prefer_single_row=True,
    )
    boxes_two = r_two.get("箱子列表") or []
    boxes_one = r_one.get("箱子列表") or []
    assert boxes_two and boxes_one, (len(boxes_two), len(boxes_one))

    def pack_sig(boxes: List[Dict[str, Any]]) -> Dict[str, Any]:
        b0 = boxes[0]
        outer = b0.get("外尺寸_mm") or {}
        special = list(b0.get("特殊属性") or [])
        return {
            "w": float(outer.get("宽") or 0),
            "two_row_ok": bool(b0.get("two_row_ok")),
            "special": special,
            "has_two_tag": "两排对齐" in special,
            "has_one_tag": "单排宽箱" in special,
            "summary_pref": (r_one if boxes is boxes_one else r_two)
            .get("结构汇总", {})
            .get("prefer_single_row"),
        }

    sig_two = pack_sig(boxes_two)
    # recompute one with correct summary
    b0 = boxes_one[0]
    outer1 = b0.get("外尺寸_mm") or {}
    sp1 = list(b0.get("特殊属性") or [])
    sig_one = {
        "w": float(outer1.get("宽") or 0),
        "two_row_ok": bool(b0.get("two_row_ok")),
        "special": sp1,
        "has_two_tag": "两排对齐" in sp1,
        "has_one_tag": "单排宽箱" in sp1,
        "summary_pref": (r_one.get("结构汇总") or {}).get("prefer_single_row"),
    }
    sig_two = {
        "w": float((boxes_two[0].get("外尺寸_mm") or {}).get("宽") or 0),
        "two_row_ok": bool(boxes_two[0].get("two_row_ok")),
        "special": list(boxes_two[0].get("特殊属性") or []),
        "has_two_tag": "两排对齐" in list(boxes_two[0].get("特殊属性") or []),
        "has_one_tag": "单排宽箱" in list(boxes_two[0].get("特殊属性") or []),
        "summary_pref": (r_two.get("结构汇总") or {}).get("prefer_single_row"),
    }

    assert sig_one["summary_pref"] is True, sig_one
    assert sig_two["summary_pref"] is False, sig_two
    # 可观察差异：外宽或 two_row_ok 或 标签
    distinguishable = (
        abs(sig_one["w"] - sig_two["w"]) > 1.0
        or sig_one["two_row_ok"] != sig_two["two_row_ok"]
        or sig_one["has_one_tag"] != sig_two["has_one_tag"]
        or sig_one["has_two_tag"] != sig_two["has_two_tag"]
    )
    assert distinguishable, {"one": sig_one, "two": sig_two}
    assert sig_one["has_one_tag"] or not sig_one["two_row_ok"], sig_one
    assert sig_two["has_two_tag"] or sig_two["two_row_ok"], sig_two
    print(
        "PASS single_row packing distinguishable",
        json.dumps({"one": sig_one, "two": sig_two}, ensure_ascii=False),
    )


def main() -> int:
    test_parse_applied_and_unsupported()
    test_revise_with_nl_applied_and_frozen()
    test_revise_plan_nl_no_silent_rerun_on_unsupported()
    test_single_row_packing_observable()
    print("ALL_GREEN test_nl_revise_contract")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as e:
        print("FAIL", e)
        raise SystemExit(1)
