"""Canonical built-in catalog and progressively loaded professional contracts.

workbench/seed.json is authoritative. Python/Rust catalogs, tool ownership and
generated skills consume it; yibiao-map.json is a generated compatibility view.
No model calls, credentials, custom-catalog writes or business output occur here.
"""
from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
from pathlib import Path
import json
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SEED_PATH = ROOT / "workbench" / "seed.json"
SCHEMA = "civil.expert.capability.v1"


def _strings(value: Any, label: str, *, minimum: int = 1) -> None:
    if (not isinstance(value, list) or len(value) < minimum
            or any(not isinstance(v, str) or not v.strip() for v in value)):
        raise ValueError(f"岗位契约 {label} 必须是完整文本列表")


def validate_seed(seed: dict) -> None:
    """Fail on missing contracts or ambiguous ownership instead of generic fallbacks."""
    if not isinstance(seed, dict) or seed.get("schema") != "civil.expert.catalog.v1":
        raise ValueError("岗位目录 schema 无效")
    categories = seed.get("categories")
    experts = seed.get("experts")
    if not isinstance(categories, list) or not isinstance(experts, list):
        raise ValueError("岗位目录必须包含类别和岗位列表")
    category_ids = [c["id"] for c in categories]
    ids = [e["id"] for e in experts]
    if len(category_ids) != len(set(category_ids)) or len(ids) != len(set(ids)):
        raise ValueError("岗位或类别 ID 重复")
    owned = set()
    for expert in experts:
        eid = expert["id"]
        if expert.get("category") not in category_ids or expert.get("risk") not in {"low", "high"}:
            raise ValueError(f"{eid} 类别或风险无效")
        _strings(expert.get("exclusive"), f"{eid}.exclusive")
        if any(name in owned for name in expert["exclusive"]):
            raise ValueError(f"{eid} 专属工具归属重复")
        owned.update(expert["exclusive"])
        capability = expert.get("capability")
        if not isinstance(capability, dict):
            raise ValueError(f"{eid} 缺少专业能力契约")
        for field, minimum in (("inputs", 4), ("output_sections", 4), ("acceptance", 2),
                               ("limitations", 1), ("reference_paths", 1), ("runtime_tools", 1)):
            _strings(capability.get(field), f"{eid}.{field}", minimum=minimum)
        steps = capability.get("steps")
        if not isinstance(steps, list) or len(steps) < 3:
            raise ValueError(f"{eid} 缺少专业步骤")
        used = set()
        for step in steps:
            if not isinstance(step, dict) or not isinstance(step.get("action"), str) or not step["action"].strip():
                raise ValueError(f"{eid} 步骤无效")
            _strings(step.get("tools"), f"{eid}.steps.tools", minimum=0)
            if any(name not in expert["exclusive"] for name in step["tools"]):
                raise ValueError(f"{eid} 步骤引用非本岗专属工具")
            used.update(step["tools"])
        if used != set(expert["exclusive"]):
            raise ValueError(f"{eid} 有工具未纳入专业步骤")
        if expert.get("pipeline") != " → ".join(step["action"] for step in steps):
            raise ValueError(f"{eid} pipeline 与专业步骤不一致")
        tables = capability.get("output_tables")
        if not isinstance(tables, list) or not tables:
            raise ValueError(f"{eid} 缺少专业输出表")
        for table in tables:
            if not isinstance(table, dict) or not isinstance(table.get("name"), str) or not table["name"]:
                raise ValueError(f"{eid} 输出表名称无效")
            _strings(table.get("columns"), f"{eid}.output_tables.columns", minimum=3)
        for value in capability["reference_paths"]:
            path = (ROOT / value).resolve()
            if not path.is_relative_to(ROOT) or not path.is_file():
                raise ValueError(f"{eid} 知识参考路径无效")
        if capability.get("implementation") not in {
            "solver_snapshot_projection", "tender_extraction", "dedicated_document_draft",
        }:
            raise ValueError(f"{eid} 实际实现类型无效")


@lru_cache(maxsize=1)
def _seed() -> dict:
    seed = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    validate_seed(seed)
    return seed


def load_seed() -> dict:
    """Return an independent copy so callers cannot mutate the global catalog."""
    return deepcopy(_seed())


def list_capabilities() -> list[dict]:
    """Cheap discovery metadata only; full procedures are retrieved by expert ID."""
    return [
        {"expert_id": e["id"], "name": e["name"], "category": e["category"],
         "risk": e["risk"], "delivers": e["delivers"], "pipeline": e["pipeline"],
         "implementation": e["capability"]["implementation"],
         "tool_names": list(e["exclusive"]), "has_contract": True}
        for e in _seed()["experts"]
    ]


_PACK_LABELS = {
    "pack-ship__list": "发现装箱工具",
    "pack-ship__health": "检查 solver 快照",
    "pack-ship__plan": "投影装柜计划证据",
    "pack-ship__export": "导出同源装柜证据",
    "construction__fill_scheme_docx": "填充专项方案 Word",
}


def get_capability(expert_id: str) -> dict | None:
    """Read one built-in contract, including actual runtime registration status.

    Custom experts intentionally return None: user-authored catalogs and SOPs are
    handled by demo.store and must not pretend to have a built-in execution tool.
    Tool availability means registered callable behavior, not connected solvers.
    """
    expert = next((e for e in _seed()["experts"] if e["id"] == expert_id), None)
    if expert is None:
        return None
    from packing_assistant.runtime.tool_engine import get_engine

    registered = get_engine().tools
    cap = deepcopy(expert["capability"])
    return {
        "schema": SCHEMA, "expert_id": expert["id"], "name": expert["name"],
        "category": expert["category"], "category_name": expert["category_name"],
        "risk": expert["risk"], "delivers": expert["delivers"], "pipeline": expert["pipeline"],
        **cap,
        "tools": [
            {"name": name, "label": _PACK_LABELS.get(name, expert["delivers"]),
             "available": name in registered,
             "input_schema": deepcopy(getattr(registered.get(name), "input_schema", None)),
             "output_schema": deepcopy(getattr(registered.get(name), "output_schema", None))}
            for name in expert["exclusive"]
        ],
        "formats": ["markdown", "docx", "xlsx_when_tables"],
        "calculator_connected": False,
        "submit_blocked": True,
    }


def tier_map() -> dict:
    """Generate the legacy Rust tier-map view from the same catalog snapshot."""
    seed = _seed()
    return {
        **deepcopy(seed["tool_map"]),
        "generated_from": "workbench/seed.json",
        "experts": [
            {"id": e["id"], "yibiao": list(e["yibiao"]), "exclusive": list(e["exclusive"]),
             "aligned": e["aligned"], "note": e["tool_note"]}
            for e in seed["experts"]
        ],
    }
