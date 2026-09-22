"""Validated selections refer only to stable identities from the inspected DXF."""
from __future__ import annotations

MAX_GROUPS = 64
MAX_GROUP_NAME = 100


def checked_selection(document, value=None):
    from .geometry import CAD3DError, MAX_ENTITIES
    if value is None:
        value = {}
    if not isinstance(value, dict) or set(value) - {"include_ids", "exclude_ids", "groups"}:
        raise CAD3DError("selection 仅支持 include_ids、exclude_ids、groups。")
    ordered = [e["id"] for e in document["entities"]]
    available = set(ordered)
    def ids(items, label, nullable=False):
        if nullable and items is None:
            return None
        if not isinstance(items, list) or len(items) > MAX_ENTITIES:
            raise CAD3DError(f"{label} 必须是最多 {MAX_ENTITIES} 项的实体编号列表。")
        if any(not isinstance(item, str) or item not in available for item in items):
            raise CAD3DError(f"{label} 包含未知实体编号或编号类型无效。")
        if len(set(items)) != len(items):
            raise CAD3DError(f"{label} 包含重复实体编号。")
        included = set(items)
        return [item for item in ordered if item in included]
    included = ids(value.get("include_ids"), "selection.include_ids", nullable=True)
    excluded = ids(value.get("exclude_ids", []), "selection.exclude_ids")
    groups = value.get("groups", [])
    if not isinstance(groups, list) or len(groups) > MAX_GROUPS:
        raise CAD3DError(f"selection.groups 必须是最多 {MAX_GROUPS} 组的列表。")
    names, normalized, total = set(), [], 0
    for group in groups:
        if not isinstance(group, dict) or set(group) != {"name", "entity_ids"}:
            raise CAD3DError("每个实体组必须且只能包含 name 和 entity_ids。")
        name = group["name"]
        if (not isinstance(name, str) or not name.strip() or len(name) > MAX_GROUP_NAME
                or any(ord(ch) < 32 for ch in name) or name.strip() in names):
            raise CAD3DError("实体组名称为空、重复、过长或含控制字符。")
        members = ids(group["entity_ids"], "group.entity_ids")
        if not members:
            raise CAD3DError("实体组必须包含至少一个已有实体。")
        total += len(members)
        if total > MAX_ENTITIES * 4:
            raise CAD3DError("实体组成员总数超出预算。")
        names.add(name.strip())
        normalized.append({"name": name.strip(), "entity_ids": members})
    return {"include_ids": included, "exclude_ids": excluded, "groups": normalized}


def selected_ids(entities, selection, layers):
    allowed = None if selection["include_ids"] is None else set(selection["include_ids"])
    excluded = set(selection["exclude_ids"])
    return [e["id"] for e in entities if layers.get(e["layer"], "ignore") != "ignore"
            and (allowed is None or e["id"] in allowed) and e["id"] not in excluded]


def validate_selection(document, config):
    from .geometry import CAD3DError
    if not isinstance(config, dict):
        raise CAD3DError("建模配置必须是对象。")
    if "selection" in config and not isinstance(config["selection"], dict):
        raise CAD3DError("selection 必须是对象。")
    return checked_selection(document, config.get("selection"))
