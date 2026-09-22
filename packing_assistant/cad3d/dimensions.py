"""Read-only drawing dimensions and explicit, source-checked parameter bindings.

Dimension text is evidence, never a command. No drawing geometry is resized.
The caller must explicitly choose a source dimension, its value and its purpose.
"""
from __future__ import annotations

from copy import deepcopy
import math
import re

FACTORS = {"mm": .001, "cm": .01, "m": 1., "in": .0254, "ft": .3048}
_UNITS = {"毫米": "mm", "厘米": "cm", "米": "m", "英寸": "in", "英尺": "ft"}
_NUMBER = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"
_LABEL = re.compile(rf"\s*({_NUMBER})\s*(mm|cm|m|in|ft|毫米|厘米|米|英寸|英尺)?\s*", re.I)
MAX_DIMENSIONS = 2000


def _finite(value):
    return type(value) in (int, float) and abs(value) <= 1e12 and math.isfinite(value)


def extract_dimensions(drawing, entities=None) -> list[dict]:
    """Extract native modelspace DIMENSION evidence without guessing text labels.

    Text, angular dimensions, non-planar dimensions and block-local dimensions
    are not automatically bound. Display overrides remain distinct from measured
    geometry; a literal override is not proof of the measured distance.
    """
    rows = []
    for entity in drawing.modelspace() if entities is None else entities:
        if entity.dxftype() != "DIMENSION":
            continue
        if len(rows) >= MAX_DIMENSIONS:
            break
        from packing_assistant.runtime import cancel
        cancel.check()
        dtype = int(entity.dxf.get("dimtype", 0)) & 7
        text = str(entity.dxf.get("text", "<>") or "<>")[:500]
        from ezdxf.tools.text import plain_mtext
        plain_text = plain_mtext(text)
        match = _LABEL.fullmatch(plain_text)
        annotation = float(match[1]) if match else None
        unit = (match[2] or "").lower() if match else ""
        unit = _UNITS.get(unit, unit) or None
        if annotation is not None and not _finite(annotation):
            annotation = None
        try:
            measured = float(entity.get_measurement())
        except (ValueError, TypeError, AttributeError, ArithmeticError):
            measured = None
        if not _finite(measured):
            measured = None
        points = []
        planar = True
        for key in ("defpoint2", "defpoint3", "defpoint", "text_midpoint"):
            point = entity.dxf.get(key)
            if point is None:
                continue
            coordinates = [float(v) for v in point]
            if len(coordinates) != 3 or not all(_finite(v) for v in coordinates):
                planar = False
                continue
            planar = planar and coordinates[2] == 0
            points.append(coordinates[:2])
        planar = planar and tuple(entity.dxf.get("extrusion", (0, 0, 1))) == (0, 0, 1)
        linear = dtype in (0, 1) and planar
        angle = float(entity.dxf.get("angle", 0)) if dtype == 0 else None
        axis = ("X" if abs(angle % 180) < 1e-8 else "Y" if abs(angle % 180 - 90) < 1e-8 else "oblique") if angle is not None and math.isfinite(angle) else "aligned" if dtype == 1 else None
        rows.append({"id": str(entity.dxf.handle), "layer": str(entity.dxf.layer), "kind": "DIMENSION",
                     "text": plain_text, "raw_text": text, "measurement": measured, "measurement_unit": "drawing",
                     "annotation_value": annotation, "annotation_unit": unit, "points": points,
                     "axis": axis, "linear": linear, "reference_only": True,
                     "bindable": linear and (measured is not None or annotation is not None),
                     "note": "原图标注与几何测量分开保留；建模用途须由用户明确指定。"})
    return rows


def _binding(document: dict, config: dict, binding: dict) -> tuple[str, str, str, float]:
    if not isinstance(binding, dict) or set(binding) - {"dimension_id", "role", "target_id", "parameter", "value_source"}:
        raise ValueError("尺寸绑定包含未知字段；数值必须从原图取得。")
    if ("role" in binding) == ("target_id" in binding):
        raise ValueError("尺寸绑定必须指定一个角色或一个构件。")
    dimension_id = binding.get("dimension_id")
    dimensions = document.get("dimensions", [])
    matches = [d for d in dimensions if d.get("id") == dimension_id]
    if not isinstance(dimension_id, str) or len(matches) != 1 or not matches[0].get("bindable"):
        raise ValueError("尺寸编号不存在，或不是可绑定的平面线性尺寸。")
    row = matches[0]
    source = binding.get("value_source")
    if source == "annotation":
        value, unit = row.get("annotation_value"), row.get("annotation_unit") or config.get("unit")
    elif source == "measurement":
        value, unit = row.get("measurement"), config.get("unit")
    else:
        raise ValueError("请选择原图标注值或几何测量值。")
    if not _finite(value) or unit not in FACTORS:
        raise ValueError("所选尺寸没有明确数值或单位，请先确认。")
    value = value * FACTORS[unit]
    parameter = binding.get("parameter")
    if parameter not in ("height_m", "base_m") or abs(value) > 1e6 or (parameter == "height_m" and value <= 0):
        raise ValueError("尺寸不能用于所选参数；高度或长度必须为正。")
    roles = {"section"} if config.get("mode") == "section" else {"wall", "column", "slab"}
    if "role" in binding:
        target = binding["role"]
        if not isinstance(target, str) or target not in roles or target not in config.get("layers", {}).values():
            raise ValueError("尺寸绑定的角色尚未对应建模图层。")
        return "role", target, parameter, value
    target = binding["target_id"]
    matches = [e for e in document.get("entities", []) if e.get("id") == target]
    if not isinstance(target, str) or len(matches) != 1 or matches[0].get("status") != "ready":
        raise ValueError("尺寸绑定必须引用已有可建模构件。")
    if config.get("layers", {}).get(matches[0]["layer"]) not in roles:
        raise ValueError("所选构件图层尚未用于建模。")
    selection = config.get("selection") or {}
    include = selection.get("include_ids")
    if target in selection.get("exclude_ids", []) or (include is not None and target not in include):
        raise ValueError("所选构件已被排除，不能绑定尺寸。")
    return "entity", target, parameter, value


def validate_bindings(document: dict, config: dict) -> None:
    bindings = config.get("dimension_bindings", [])
    if not isinstance(bindings, list) or len(bindings) > MAX_DIMENSIONS:
        raise ValueError("尺寸绑定必须是有界列表。")
    seen = set()
    for binding in bindings:
        kind, target, parameter, value = _binding(document, config, binding)
        key = kind, target, parameter
        if key in seen:
            raise ValueError("同一参数不能重复绑定尺寸。")
        seen.add(key)
        actual = config.get("parameters" if kind == "role" else "overrides", {}).get(target, {}).get(parameter)
        if not _finite(actual) or not math.isclose(actual, value, rel_tol=1e-12, abs_tol=1e-12):
            raise ValueError("参数与已绑定的图纸尺寸不一致；请重新绑定，或解除来源绑定后明确输入。")


def bind_dimension(document: dict, config: dict, binding: dict) -> dict:
    """Apply one explicitly requested binding; never accept client-supplied values."""
    kind, target, parameter, value = _binding(document, config, binding)
    updated = deepcopy(config)
    section = "parameters" if kind == "role" else "overrides"
    before = updated.setdefault(section, {}).setdefault(target, {}).get(parameter)
    updated[section][target][parameter] = value
    key = "role" if kind == "role" else "target_id"
    existing = updated.get("dimension_bindings", [])
    if not isinstance(existing, list):
        raise ValueError("尺寸绑定必须是列表。")
    updated["dimension_bindings"] = [row for row in existing if not (isinstance(row, dict) and row.get(key) == target and row.get("parameter") == parameter)] + [deepcopy(binding)]
    validate_bindings(document, updated)
    return {"config": updated, "changes": [{"parameter": f"{section}.{target}.{parameter}", "before": before, "after": value}],
            "message": "已绑定原图尺寸；平面几何保持不变，生成前仍需确认实体区域。"}


def detach_changed_bindings(before: dict, after: dict) -> None:
    """Manual/command edits replace evidence links instead of falsely retaining them."""
    if "dimension_bindings" not in after:
        return
    kept = []
    for binding in after["dimension_bindings"]:
        section, key = ("parameters", "role") if "role" in binding else ("overrides", "target_id")
        target, parameter = binding.get(key), binding.get("parameter")
        selection = after.get("selection") or {}
        included = selection.get("include_ids")
        if key == "target_id" and (target in selection.get("exclude_ids", []) or (included is not None and target not in included)):
            continue
        if (before.get("unit") == after.get("unit") and before.get("mode") == after.get("mode")
                and before.get("layers") == after.get("layers")
                and before.get(section, {}).get(target, {}).get(parameter) == after.get(section, {}).get(target, {}).get(parameter)):
            kept.append(binding)
    after["dimension_bindings"] = kept
