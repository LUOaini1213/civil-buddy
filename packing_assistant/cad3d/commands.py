"""Small, atomic CAD parameter commands; no model, code execution or geometry edits.

The accepted language is deliberately finite. A successful parse returns a new
configuration; the caller validates/builds it and owns its undo history. Source
coordinates, source units and the user's solid-region confirmation are never
changed here. All distances in commands require an explicit unit.
"""
from __future__ import annotations

from copy import deepcopy
import math
import re
from typing import Any


_ROLE_NAMES = {"wall": "墙", "column": "柱", "slab": "楼板", "section": "截面"}
_ZH_ROLES = {
    "墙体": "wall", "墙": "wall", "柱子": "column", "柱体": "column", "柱": "column",
    "楼板": "slab", "板": "slab", "截面": "section", "构件": "section",
}
_EN_ROLES = {
    "wall": "wall", "walls": "wall", "column": "column", "columns": "column",
    "slab": "slab", "slabs": "slab", "section": "section", "sections": "section",
}
_FACTORS = {
    "mm": 0.001, "毫米": 0.001, "millimeter": 0.001, "millimeters": 0.001,
    "millimetre": 0.001, "millimetres": 0.001,
    "cm": 0.01, "厘米": 0.01, "centimeter": 0.01, "centimeters": 0.01,
    "centimetre": 0.01, "centimetres": 0.01,
    "m": 1.0, "米": 1.0, "meter": 1.0, "meters": 1.0, "metre": 1.0, "metres": 1.0,
    "in": 0.0254, "英寸": 0.0254, "inch": 0.0254, "inches": 0.0254,
    "ft": 0.3048, "英尺": 0.3048, "foot": 0.3048, "feet": 0.3048,
}
_NUMBER = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"
_UNIT = "(?:" + "|".join(sorted(_FACTORS, key=len, reverse=True)) + ")"
_DISTANCE = rf"(?P<value>{_NUMBER})\s*(?P<unit>{_UNIT})"
_ZH_ALIAS = "(?:" + "|".join(sorted(_ZH_ROLES, key=len, reverse=True)) + ")"
_EN_ALIAS = "(?:" + "|".join(sorted(_EN_ROLES, key=len, reverse=True)) + ")"
_ZH_TARGETS = rf"{_ZH_ALIAS}(?:\s*(?:和|与|及|以及|、)\s*{_ZH_ALIAS})*"
_EN_TARGETS = rf"{_EN_ALIAS}(?:\s+and\s+{_EN_ALIAS})*"
_ZH_SELECTED = r"选中(?:的)?(?:构件|对象|实体)"
_ZH_FIELD = r"底部标高|底标高|标高|拉伸长度|高度|厚度|长度|高|厚|长"
_EN_FIELD = r"extrusion length|base elevation|elevation|thickness|height|length"
_ZH_SETTING = re.compile(
    rf"(?:请\s*)?(?:把|将)?\s*(?:所有(?:的)?|全部(?:的)?)?\s*"
    rf"(?P<target>{_ZH_SELECTED}|{_ZH_TARGETS})\s*(?:的)?\s*"
    rf"(?P<field>{_ZH_FIELD})\s*"
    rf"(?:改成|改为|设成|设为|设置为|调整为|调整到|变为|变成|为|是|=|：|:)?\s*{_DISTANCE}",
    re.IGNORECASE,
)
_ZH_EXTRUSION = re.compile(
    rf"(?:请\s*)?(?:把|将)?\s*(?P<field>拉伸长度|长度)\s*"
    rf"(?:改成|改为|设成|设为|设置为|调整为|调整到|变为|变成|为|=|：|:)?\s*{_DISTANCE}",
    re.IGNORECASE,
)
_EN_SETTING = re.compile(
    rf"(?:please\s+)?(?:set|change|update)\s+(?:all\s+)?"
    rf"(?P<target>selected(?:\s+(?:object|entity|component))?|{_EN_TARGETS})\s+"
    rf"(?P<field>{_EN_FIELD})\s+(?:to\s+)?{_DISTANCE}", re.IGNORECASE,
)
_EN_EXTRUSION = re.compile(
    rf"(?:please\s+)?(?:set|change|update)\s+(?P<field>extrusion length|length)\s+"
    rf"(?:to\s+)?{_DISTANCE}", re.IGNORECASE,
)


def _roles(value: str, *, english: bool = False) -> list[str]:
    aliases = _EN_ROLES if english else _ZH_ROLES
    parts = re.split(r"\s+and\s+" if english else r"\s*(?:以及|和|与|及|、)\s*", value.lower())
    return list(dict.fromkeys(aliases[part.strip()] for part in parts))


def _parse(clause: str) -> dict[str, Any]:
    for pattern, english in ((_ZH_SETTING, False), (_EN_SETTING, True)):
        match = pattern.fullmatch(clause)
        if match:
            target = match["target"]
            selected = target.startswith("选中") or target.lower().startswith("selected")
            return {
                "kind": "set", "selected": selected,
                "roles": [] if selected else _roles(target, english=english),
                "field": match["field"].lower(), "value": match["value"], "unit": match["unit"].lower(),
            }
    for pattern in (_ZH_EXTRUSION, _EN_EXTRUSION):
        match = pattern.fullmatch(clause)
        if match:
            return {"kind": "set", "selected": False, "roles": ["section"],
                    "field": match["field"].lower(), "value": match["value"], "unit": match["unit"].lower()}
    match = re.fullmatch(rf"(?:请\s*)?只(?:建|建模|生成|保留)\s*(?P<roles>{_ZH_TARGETS})", clause)
    if match:
        return {"kind": "only", "roles": _roles(match["roles"])}
    match = re.fullmatch(rf"(?:please\s+)?only\s+(?:(?:build|keep)\s+)?(?P<roles>{_EN_TARGETS})",
                         clause, flags=re.IGNORECASE)
    if match:
        return {"kind": "only", "roles": _roles(match["roles"], english=True)}
    match = re.fullmatch(r"(?:请\s*)?忽略\s*(?:图层\s*)?(?P<layer>.+?)(?:\s*图层)?", clause)
    if not match:
        match = re.fullmatch(r"(?:please\s+)?ignore\s+(?:layer\s+)?(?P<layer>.+?)(?:\s+layer)?",
                             clause, flags=re.IGNORECASE)
    if match:
        layer = match["layer"].strip()
        if len(layer) >= 2 and (layer[0], layer[-1]) in (("\"", "\""), ("'", "'"), ("“", "”")):
            layer = layer[1:-1]
        return {"kind": "ignore", "layer": layer}
    raise ValueError("无法识别完整指令；请使用明确的对象、参数、数值和单位，例如：把墙高改成3.6米。")


def _document_layers(document: dict[str, Any], entities: list[dict[str, Any]]) -> set[str]:
    names = {entity["layer"] for entity in entities if isinstance(entity.get("layer"), str)}
    layers = document.get("layers", [])
    if isinstance(layers, dict):
        names.update(name for name in layers if isinstance(name, str))
    elif isinstance(layers, list):
        for layer in layers:
            if isinstance(layer, str):
                names.add(layer)
            elif isinstance(layer, dict) and isinstance(layer.get("name"), str):
                names.add(layer["name"])
    return names


def _validate_inputs(document: dict, config: dict) -> tuple[list[dict[str, Any]], set[str]]:
    if not isinstance(document, dict) or not isinstance(config, dict):
        raise ValueError("图纸和参数必须是对象。")
    entities = document.get("entities")
    if not isinstance(entities, list) or any(not isinstance(entity, dict) for entity in entities):
        raise ValueError("图纸没有有效的实体列表。")
    if any(not isinstance(entity.get("id"), str) or not isinstance(entity.get("layer"), str)
           for entity in entities):
        raise ValueError("图纸实体缺少有效的原图编号或图层名。")
    if config.get("mode") not in ("building", "section"):
        raise ValueError("请先选择建筑平面或构件截面模式。")
    if config.get("unit") not in ("mm", "cm", "m", "in", "ft"):
        raise ValueError("请先在参数面板确认图纸单位。")
    layers = config.get("layers")
    if not isinstance(layers, dict) or any(
        not isinstance(name, str) or not isinstance(role, str) or role not in {*_ROLE_NAMES, "ignore"}
        for name, role in layers.items()
    ):
        raise ValueError("请先在参数面板确认图层用途。")
    for key in ("parameters", "overrides"):
        values = config.get(key, {})
        if not isinstance(values, dict) or any(not isinstance(value, dict) for value in values.values()):
            raise ValueError(f"{key} 参数无效。")
    return entities, _document_layers(document, entities)


def _role_layers(config: dict, roles: list[str], known_layers: set[str]) -> None:
    available = {role for layer, role in config["layers"].items() if layer in known_layers}
    allowed = {"wall", "column", "slab"} if config["mode"] == "building" else {"section"}
    if any(role not in allowed for role in roles):
        raise ValueError("该对象不属于当前建模模式，请在参数面板切换模式并确认图层用途。")
    if any(role not in available for role in roles):
        raise ValueError("指令中的对象尚未对应到现有图层，请先在参数面板确认图层用途。")


def _field(field: str, roles: list[str]) -> str:
    if field in ("标高", "底标高", "底部标高", "elevation", "base elevation"):
        return "base_m"
    if field in ("厚", "厚度", "thickness") and any(role != "slab" for role in roles):
        raise ValueError("厚度指令仅用于楼板；墙体和截面的平面轮廓不能用参数指令改写。")
    if field in ("长", "长度", "拉伸长度", "length", "extrusion length") and any(role != "section" for role in roles):
        raise ValueError("拉伸长度仅用于构件截面模式。")
    return "height_m"


def _record(assignments: dict[tuple[str, str, str], float], key: tuple[str, str, str], value: float) -> None:
    if key in assignments and assignments[key] != value:
        raise ValueError("同一条消息对同一参数给出了不同数值；请每次提供一个确定的值。")
    assignments[key] = value


def apply_command(document: dict, config: dict, message: str, selected_id: str | None = None) -> dict:
    """Return ``{config, changes, message}`` or raise ``ValueError`` without mutation.

    Only already mapped roles or the selected, ready source entity can be edited.
    Multiple clauses separated by Chinese/ASCII commas or semicolons are atomic.
    Role edits update same-field entity overrides too, so "all walls" means all
    walls while leaving their individual elevations/other parameters intact.
    "Only" filters existing mappings; it never guesses a previously ignored role.
    "Ignore" requires an existing exact layer name (case-insensitive if unique).
    "Undo" is intentionally owned by the UI rather than inferred from this input.
    """
    entities, known_layers = _validate_inputs(document, config)
    if not isinstance(message, str) or not message.strip() or len(message) > 2000:
        raise ValueError("请输入不超过2000字的参数指令。")
    if any(mark in message for mark in ("?", "？", "\n", "\r")):
        raise ValueError("这里只接受明确的单行修改指令；问题不会修改模型。")
    text = message.strip().removesuffix("。").removesuffix(".").strip()
    clauses = [clause.strip() for clause in re.split(r"[,，;；]", text)]
    if not clauses or len(clauses) > 20 or any(not clause for clause in clauses):
        raise ValueError("请使用完整指令，多个修改之间用逗号或分号分隔。")
    operations = [_parse(clause) for clause in clauses]
    updated = deepcopy(config)
    changes: list[str] = []
    assignments: dict[tuple[str, str, str], float] = {}
    for operation in operations:
        if operation["kind"] == "ignore":
            requested = operation["layer"]
            matches = [name for name in known_layers if name.casefold() == requested.casefold()]
            if requested in known_layers:
                layer = requested
            elif len(matches) == 1:
                layer = matches[0]
            else:
                raise ValueError(f"没有找到唯一的图层“{requested}”；请使用图纸中的完整图层名。")
            updated["layers"][layer] = "ignore"
            changes.append(f"忽略图层 {layer}")
            continue
        roles = operation["roles"]
        if operation["kind"] == "only":
            _role_layers(updated, roles, known_layers)
            for layer in updated["layers"]:
                if updated["layers"][layer] not in roles:
                    updated["layers"][layer] = "ignore"
            changes.append("只保留已确认的" + "、".join(_ROLE_NAMES[role] for role in roles) + "图层")
            continue
        selected = None
        if operation["selected"]:
            matches = [entity for entity in entities if entity.get("id") == selected_id]
            if not isinstance(selected_id, str) or not selected_id or len(matches) != 1 or matches[0].get("status") != "ready":
                raise ValueError("请先选择一个可建模的原图实体。")
            selected = matches[0]
            role = updated["layers"].get(selected.get("layer"))
            if role not in _ROLE_NAMES:
                raise ValueError("选中实体所在图层尚未指定建模用途，或已经被忽略。")
            roles = [role]
        _role_layers(updated, roles, known_layers)
        field = _field(operation["field"], roles)
        value = float(operation["value"]) * _FACTORS[operation["unit"]]
        if not math.isfinite(value) or (field == "height_m" and value <= 0):
            raise ValueError("高度、厚度和拉伸长度必须为有限的正数，标高必须为有限数值。")
        label = "标高" if field == "base_m" else "拉伸高度/长度"
        if selected is not None:
            entity_id = selected["id"]
            _record(assignments, ("entity", entity_id, field), value)
            updated.setdefault("overrides", {}).setdefault(entity_id, {})[field] = value
            changes.append(f"实体 {entity_id} 的{label}改为 {value:g} m")
            continue
        for role in roles:
            _record(assignments, ("role", role, field), value)
            for entity in entities:
                entity_id = entity.get("id")
                if isinstance(entity_id, str) and updated["layers"].get(entity.get("layer")) == role:
                    _record(assignments, ("entity", entity_id, field), value)
                    override = updated.get("overrides", {}).get(entity_id)
                    if override is not None and field in override:
                        override[field] = value
            updated.setdefault("parameters", {}).setdefault(role, {})[field] = value
            changes.append(f"{_ROLE_NAMES[role]}的{label}改为 {value:g} m")
    from .dimensions import detach_changed_bindings
    detach_changed_bindings(config, updated)
    return {"config": updated, "changes": changes, "message": "；".join(changes)}
