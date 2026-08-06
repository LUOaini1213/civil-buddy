"""装载偏好档位：写入 packing_options，供 pipeline / what-if 一键切换。"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Optional

PROFILES: Dict[str, Dict[str, Any]] = {
    "balanced": {
        "label": "均衡（默认）",
        "description": "叠高+CoG 再平衡，目标 mid50≥55%，可 WARN 出运",
        "options": {
            "prefer_stack": True,
            "multi_start": True,
            "cog_aware": True,
            "cog_rebalance": True,
            "r4_target_mid50": 0.55,
            "lns_worst": True,
            "lateral_repair": True,
            "lat_threshold": 0.08,
            "export_strict": False,
            "clearance_mm": 30,
        },
    },
    "strict_mid50": {
        "label": "严格中段（CTU）",
        "description": "强化 mid50/LNS/横偏，偏合规",
        "options": {
            "prefer_stack": True,
            "multi_start": True,
            "cog_aware": True,
            "cog_rebalance": True,
            "r4_target_mid50": 0.60,
            "lns_worst": True,
            "lateral_repair": True,
            "lat_threshold": 0.05,
            "export_strict": False,
            "clearance_mm": 25,
            "r2_slab": True,
            "r4_repair": True,
        },
    },
    "min_cabin": {
        "label": "最少柜",
        "description": "优先叠高、密装，少开柜（仍尊重锁柜）",
        "options": {
            "prefer_stack": True,
            "multi_start": True,
            "dense_mode": True,
            "cog_aware": True,
            "cog_rebalance": True,
            "max_stack_layers": 3,
            "clearance_mm": 20,
            "lns_worst": True,
        },
    },
    "export_careful": {
        "label": "出运谨慎",
        "description": "export_strict 抬门禁，重心更严",
        "options": {
            "prefer_stack": True,
            "multi_start": True,
            "cog_aware": True,
            "cog_rebalance": True,
            "export_strict": True,
            "r4_target_mid50": 0.60,
            "lat_threshold": 0.05,
            "lns_worst": True,
            "lateral_repair": True,
            "clearance_mm": 30,
        },
    },
    "crate_passthrough": {
        "label": "当量直通",
        "description": "材料行=箱外廓，禁标准箱撑大（仿真/工地当量）",
        "options": {
            "crate_passthrough": True,
            "standard_boxes": False,
            "dense_mode": True,
            "prefer_stack": True,
            "multi_start": True,
            "cog_aware": True,
            "cog_rebalance": True,
        },
    },
    "generic_table": {
        "label": "通用材料表",
        "description": "非钢默认：当量直通成箱，多起点，CoG；不强制结构半严格",
        "options": {
            "crate_passthrough": True,
            "standard_boxes": False,
            "dense_mode": True,
            "prefer_stack": True,
            "multi_start": True,
            "cog_aware": True,
            "cog_rebalance": True,
            "structure_calc": False,
        },
    },
}


def list_profiles() -> List[Dict[str, Any]]:
    return [
        {
            "id": k,
            "label": v.get("label") or k,
            "description": v.get("description") or "",
        }
        for k, v in PROFILES.items()
    ]


def apply_profile(
    base: Optional[Dict[str, Any]],
    profile_id: str,
) -> Dict[str, Any]:
    """合并档位 options 到 base packing_options。"""
    opts = dict(base or {})
    prof = PROFILES.get(profile_id)
    if not prof:
        return opts
    for k, v in (prof.get("options") or {}).items():
        opts[k] = deepcopy(v)
    opts["profile_id"] = profile_id
    opts["single_team_loop"] = True
    return opts


def profile_generic_table() -> dict:
    """Non-steel default: passthrough crates, multi_start, cog."""
    return {
        "profile_id": "generic_table",
        "crate_passthrough": True,
        "multi_start": True,
        "cog_aware": True,
        "structure_calc": False,
    }
