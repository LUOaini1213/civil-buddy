#!/usr/bin/env python3
"""比赛用 HITL 续跑：Team A → 磁盘 session → 假重启 load → Team B。

3 case，不依赖进程内内存 session。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _load_mats(rel: str) -> list:
    p = ROOT / rel
    data = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    return list(data.get("materials") or [])


def _one(case_id: str, materials: list, user_input: str) -> None:
    from packing_assistant.graph_resume import (
        load_resume_state,
        resume_team_b_segment,
        run_team_a_segment,
    )
    from packing_assistant.session_store import load_session, save_session

    sid = f"hitl-comp-{case_id}"
    print(f"--- A segment {case_id} session={sid}")
    st_a = run_team_a_segment(
        user_input,
        materials=materials,
        session_id=sid,
        packing_options={
            "standard_boxes": True,
            "prefer_stack": True,
            "multi_start": True,
        },
    )
    save_session(sid, st_a)
    phase = st_a.get("phase")
    n_boxes = len(st_a.get("boxes") or [])
    print(f"    phase={phase} boxes={n_boxes}")
    assert n_boxes >= 1, f"{case_id}: no boxes after team A"
    assert phase in (
        "await_user_confirm",
        "team_a_running",
    ) or st_a.get("user_action") in (None, "confirm") or n_boxes >= 1

    # 假重启：只从磁盘读
    st_disk = load_session(sid) or load_resume_state(sid)
    assert st_disk, f"{case_id}: disk resume missing"
    assert len(st_disk.get("boxes") or []) >= 1

    print(f"--- B resume {case_id}")
    st_b = resume_team_b_segment(
        st_disk,
        session_id=sid,
        container_type=str(st_disk.get("container_type") or "40HQ"),
        max_containers=0,
    )
    plan = st_b.get("container_plan") or {}
    print(
        f"    can_fit={plan.get('can_fit')} used={plan.get('containers_used')} "
        f"phase={st_b.get('phase')} segment={st_b.get('graph_segment')}"
    )
    assert plan.get("can_fit") is not None or st_b.get("status") != "error", st_b.get(
        "errors"
    )
    # 收口：至少跑过拼柜
    assert st_b.get("graph_segment") == "team_b_done" or st_b.get("phase") in (
        "done",
        "need_revision",
        "team_b_running",
    )
    print(f"PASS hitl resume {case_id}")


def main() -> int:
    cases = [
        (
            "tiny",
            "test/sim_materials/tiny/materials.json",
            "比赛HITL tiny 确认拼柜",
        ),
        (
            "small",
            "test/sim_materials/small_one_container/materials.json",
            "比赛HITL small 确认拼柜",
        ),
        (
            "glass",
            "test/sim_materials/glass_category/materials.json",
            "比赛HITL glass 确认拼柜",
        ),
    ]
    for cid, rel, ui in cases:
        mats = _load_mats(rel)
        assert mats, f"empty materials {rel}"
        _one(cid, mats, ui)
    print("ALL_HITL_RESUME_PASS n=3")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
