"""演示物料预设：避免默认小票导致利用率「看起来太低」。

- default / steel_light：少料钢件（结构叙事，利用率偏低属正常）
- high_util：密实模块，重量/体积都压满 40HQ（答辩观感）
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


def materials_high_util() -> List[Dict[str, Any]]:
    """30× 密实模块 ≈ 24t 净重，dense 合箱，单柜高利用率。"""
    out: List[Dict[str, Any]] = []
    for i in range(1, 31):
        out.append(
            {
                "id": f"HU{i:03d}",
                "name": f"密实模块-{i}",
                "spec": "整包模块",
                "quantity": 1,
                "weight_kg": 800.0,
                "total_weight_kg": 800.0,
                "length_mm": 1200,
                "width_mm": 1000,
                "height_mm": 1100,
                "category": "重件",
            }
        )
    return out


def materials_steel_light() -> List[Dict[str, Any]]:
    """旧演示：少量钢件（利用率低，适合讲结构/标准箱）。"""
    from packing_assistant.adapters import material_internal_to_api

    raw = [
        {
            "名称": "H型钢柱",
            "规格": "H400×200",
            "数量": 4,
            "单重_kg": 85,
            "外尺寸_mm": {"长": 3800, "宽": 400, "高": 200},
        },
        {
            "名称": "钢梁",
            "规格": "H350×175",
            "数量": 6,
            "单重_kg": 55,
            "外尺寸_mm": {"长": 4200, "宽": 350, "高": 175},
        },
        {
            "名称": "连接板组件",
            "规格": "套件",
            "数量": 20,
            "单重_kg": 12,
            "外尺寸_mm": {"长": 800, "宽": 600, "高": 400},
        },
    ]
    return [material_internal_to_api(m, i) for i, m in enumerate(raw, 1)]


def packing_options_high_util() -> Dict[str, Any]:
    return {
        "standard_boxes": False,
        "dense_mode": True,
        "max_box_net_kg": 2000,
        "mix_mode": False,
        # 满载演示也要 CTU 中段质量，避免 CoG=block
        "cog_rebalance": True,
        "r4_repair": True,
        "r4_target_mid50": 0.60,
        "multi_start": True,
    }


def packing_options_standard() -> Dict[str, Any]:
    return {
        "standard_boxes": True,
        "mix_mode": True,
        "dense_mode": False,
        "max_box_net_kg": 2000,
    }


def materials_five_boxes() -> List[Dict[str, Any]]:
    """5 个成箱量级的货，配合 one_box_per_container → 5 集装箱。"""
    out: List[Dict[str, Any]] = []
    for i in range(1, 6):
        out.append(
            {
                "id": f"B5-{i}",
                "name": f"出运箱货-{i}",
                "spec": "整箱货",
                "quantity": 1,
                "weight_kg": 2200.0,
                "total_weight_kg": 2200.0,
                "length_mm": 2200,
                "width_mm": 1100,
                "height_mm": 1100,
                "category": "重件",
            }
        )
    return out


def packing_options_one_box_per_container() -> Dict[str, Any]:
    return {
        "standard_boxes": False,
        "dense_mode": True,
        "crate_passthrough": True,
        "one_box_per_container": True,
        "max_box_net_kg": 3000,
    }


PRESETS = {
    "high_util": {
        "label": "高利用率满载（推荐演示）",
        "materials": materials_high_util,
        "packing_options": packing_options_high_util,
        "user_input": "高利用率演示：30×密实模块≈24t，dense 合箱压满 40HQ",
    },
    "five_containers": {
        "label": "5箱→5柜（一箱一柜）",
        "materials": materials_five_boxes,
        "packing_options": packing_options_one_box_per_container,
        "user_input": "一箱一柜：5 箱货各占一集装箱",
    },
    "steel_light": {
        "label": "轻量钢件（结构叙事）",
        "materials": materials_steel_light,
        "packing_options": packing_options_standard,
        "user_input": "演示材料清单（钢柱/钢梁/连接板）",
    },
    "default": {
        "label": "默认=高利用率",
        "materials": materials_high_util,
        "packing_options": packing_options_high_util,
        "user_input": "高利用率演示物料",
    },
}


def resolve_preset(
    preset: Optional[str] = None,
    *,
    user_input: str = "",
) -> Tuple[Optional[List[Dict[str, Any]]], Optional[Dict[str, Any]], str]:
    """返回 (materials, packing_options, resolved_name)。

    materials/options 为 None 表示调用方不要覆盖。
    """
    key = (preset or "").strip().lower()
    text = (user_input or "").strip()
    if not key:
        if any(k in text for k in ("高利用率", "满载", "high_util", "dense demo")):
            key = "high_util"
        elif any(
            k in text
            for k in (
                "一箱一柜",
                "5箱",
                "五箱",
                "5柜",
                "五柜",
                "five_containers",
                "分柜出运",
            )
        ):
            key = "five_containers"
        elif any(k in text for k in ("钢件轻量", "steel_light", "结构叙事")):
            key = "steel_light"
        elif not text or text in (
            "演示材料清单",
            "Agent pipeline",
            "一键演示",
            "demo",
        ):
            key = "default"
        else:
            return None, None, ""
    if key not in PRESETS:
        key = "default"
    p = PRESETS[key]
    return p["materials"](), p["packing_options"](), key


def list_presets() -> List[Dict[str, str]]:
    return [
        {"id": k, "label": v["label"], "user_input": v["user_input"]}
        for k, v in PRESETS.items()
        if k != "default"
    ]
