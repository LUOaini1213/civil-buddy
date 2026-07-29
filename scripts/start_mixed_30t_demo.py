#!/usr/bin/env python3
"""启动混合 30t 全流程并写入 session，便于前端 ?session=mixed-30t 查看。"""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SID = "mixed-30t"
CASE = ROOT / "test" / "sim_materials" / "t30_mixed_short_s4" / "materials.json"
BASE = "http://127.0.0.1:8000"


def main() -> int:
    if not CASE.exists():
        print("missing", CASE, "— run: python scripts/gen_30t_materials.py")
        return 1
    data = json.loads(CASE.read_text(encoding="utf-8"))
    mats = data.get("materials") or []
    body = {
        "user_input": "混合30t短件堆量演示 t30_mixed_short_s4",
        "session_id": SID,
        "container_type": "40HQ",
        "enable_auto_confirm": True,
        "materials": mats,
        "preset": "",  # 已显式 materials，勿被 high_util 覆盖
        "packing_options": {
            "standard_boxes": False,
            "dense_mode": True,
            "max_box_net_kg": 2500,
            "prefer_stack": True,
            "clearance_mm": 30,
            "support_ratio_min": 0.55,
            "max_stack_layers": 3,
            "prefer_bottom_weight_kg": 2000,
            "multi_start": True,
        },
        "save_artifacts": True,
        "mode": "steps",
    }
    # 本地直接跑更稳（不依赖 HTTP 超时）
    from packing_assistant.harness import run_agent_pipeline, public_response
    from packing_assistant.session_store import save_session

    print(f"running mixed 30t: lines={len(mats)} net≈{data.get('net_t')}t …")
    st = run_agent_pipeline(
        body["user_input"],
        materials=mats,
        container_type="40HQ",
        enable_auto_confirm=True,
        session_id=SID,
        save_artifacts=True,
        packing_options=body["packing_options"],
    )
    save_session(SID, st)
    # 若网关在跑，再 POST 一次把 RAM 填满
    try:
        req = urllib.request.Request(
            BASE + "/api/pipeline",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=300) as r:
            j = json.loads(r.read().decode())
        pub = j.get("public") or j
        print("gateway session stored")
    except Exception as e:
        print("gateway push skipped:", e)
        pub = public_response(st)

    p = pub.get("container_plan") or st.get("container_plan") or {}
    vs = pub.get("volume_summary") or {}
    print("--- RESULT ---")
    print("session_id:", SID)
    print("boxes:", len(pub.get("boxes") or st.get("boxes") or []))
    print("used:", p.get("containers_used"), "n0:", p.get("n0") or vs.get("n0"))
    print(
        "booking:",
        vs.get("booking_volume_utilization") or p.get("booking_volume_utilization"),
        "outer:",
        vs.get("outer_space_utilization") or p.get("outer_space_utilization") or p.get("space_utilization"),
        "weight:",
        vs.get("weight_utilization") or p.get("weight_utilization"),
    )
    print("can_fit:", p.get("can_fit"), "engine:", p.get("engine"))
    print("open:", f"{BASE}/?session={SID}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
