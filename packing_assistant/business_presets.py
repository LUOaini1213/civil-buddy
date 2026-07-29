"""场景示例预设（非产品固定业务）。

「龙申 1 柜」「工厂第一批 2 柜」只是会议/演示里的样例：
把「物料表 + 柜数预算 + 装载偏好」填成 IntentSpec / packing_options 的捷径。

产品主路径应是通用能力：
  任意物料 → 解析约束（柜数/锁柜/密装/直通架…）→ 单 Team 闭环求解
不要把某一条线路写成唯一业务模型。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


# 仅作 UI/API 可点的示例模板；id 稳定便于 demo 脚本引用。
PRESETS: Dict[str, Dict[str, Any]] = {
    "longshen_1c": {
        "label": "示例·锁 1 柜（工地拼柜风格）",
        "description": "演示：预算 1×40HQ + 当量直通 + CoG。非固定线路。",
        "example_only": True,
        "max_containers": 1,
        "user_input": "预算1柜 拼柜 铁件小件满柜",
        "packing_options": {
            "crate_passthrough": True,
            "standard_boxes": False,
            "prefer_stack": True,
            "multi_start": True,
            "cog_aware": True,
            "cog_rebalance": True,
            "lock_max_containers": True,
            "meeting_cap": True,
            "container_budget": 1,
            "lns_worst": True,
            "lateral_repair": True,
            "r4_target_mid50": 0.55,
            "profile_id": "crate_passthrough",
            "scenario_example": "lock_1c_passthrough",
        },
        "material_hint": "任意：工地铁件/小件当量等",
        "generalizes_to": "container_budget=1 + crate_passthrough + cog",
    },
    "factory_first_2c": {
        "label": "示例·锁 2 柜（工厂批次风格）",
        "description": "演示：预算 2×40HQ + 密装 + 锁柜。非固定线路。",
        "example_only": True,
        "max_containers": 2,
        "user_input": "预算2柜 密装 铝板铝料小料",
        "packing_options": {
            "dense_mode": True,
            "prefer_stack": True,
            "multi_start": True,
            "cog_aware": True,
            "cog_rebalance": True,
            "lock_max_containers": True,
            "meeting_cap": True,
            "container_budget": 2,
            "lns_worst": True,
            "lateral_repair": True,
            "profile_id": "min_cabin",
            "scenario_example": "lock_2c_dense",
        },
        "material_hint": "任意：工厂铝料/板材子集等",
        "generalizes_to": "container_budget=2 + dense_mode + cog",
    },
    "high_util_demo": {
        "label": "示例·满载偏好（不锁柜）",
        "description": "演示：自主定柜 + 密装叠高。通用模板。",
        "example_only": True,
        "max_containers": 0,
        "user_input": "满载 自主定柜",
        "packing_options": {
            "prefer_stack": True,
            "multi_start": True,
            "cog_aware": True,
            "cog_rebalance": True,
            "dense_mode": True,
            "profile_id": "balanced",
            "scenario_example": "high_util_auto_cabin",
        },
        "generalizes_to": "dense + stack + cog，无柜数硬锁",
    },
}


def list_business_presets() -> List[Dict[str, Any]]:
    return [
        {
            "id": k,
            "label": v.get("label"),
            "description": v.get("description"),
            "example_only": bool(v.get("example_only", True)),
            "max_containers": v.get("max_containers"),
            "material_hint": v.get("material_hint"),
            "generalizes_to": v.get("generalizes_to"),
        }
        for k, v in PRESETS.items()
    ]


def get_business_preset(preset_id: str) -> Optional[Dict[str, Any]]:
    return PRESETS.get(preset_id)
