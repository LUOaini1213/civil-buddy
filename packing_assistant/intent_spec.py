"""IntentSpec：NL 通用 Agent 的结构化意图契约。

用户自然语言 + 可选物料 → 统一 IntentSpec → packing_options / max_containers。
场景名（龙申/工厂等）只是例子，不进入产品业务模型。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Sequence


@dataclass
class IntentSpec:
    """大 Team 可执行的意图对象。"""

    raw_nl: str = ""
    goal: str = "deliver_valid_pack_plan"  # deliver_valid_pack_plan | minimize_containers | safe_to_ship
    container_type: str = ""  # 空=由主控推荐
    container_budget: Optional[int] = None  # 锁 N 柜；None=自主定柜
    lock_containers: bool = False
    cargo_mode: str = "mixed"  # heavy_steel | long_aluminum | thin_plate | ...
    prefer_dense: bool = False
    prefer_stack: bool = True
    prefer_min_cabin: bool = False
    prefer_strict_cog: bool = False
    prefer_export: bool = False
    crate_passthrough: Optional[bool] = None
    standard_boxes: Optional[bool] = None
    drop_long: bool = False
    long_threshold_mm: float = 6000.0
    keep_families: List[str] = field(default_factory=list)
    drop_families: List[str] = field(default_factory=list)
    packing_options: Dict[str, Any] = field(default_factory=dict)
    material_profile: Dict[str, Any] = field(default_factory=dict)
    scheme_id: str = ""
    confidence: float = 0.5
    notes: List[str] = field(default_factory=list)
    source: str = "nl"  # nl | form | example_preset | api

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def max_containers(self) -> int:
        if self.lock_containers and self.container_budget:
            return int(self.container_budget)
        if self.container_budget:
            return int(self.container_budget)
        return 0


def interpret_nl(
    text: str,
    *,
    materials: Optional[Sequence[Dict[str, Any]]] = None,
    base_options: Optional[Dict[str, Any]] = None,
    goal: str = "deliver_valid_pack_plan",
    container_type: str = "",
    source: str = "nl",
) -> IntentSpec:
    """
    通用 Agent 意图层：NL → IntentSpec。

    复用 material-aware nl_whatif 解析；输出为大 Team 唯一契约。
    """
    from packing_assistant.nl_whatif import analyze_materials, parse_nl_whatif

    raw = (text or "").strip()
    parsed = parse_nl_whatif(raw, materials=materials)
    intents = parsed.get("intents") or {}
    profile = parsed.get("material_profile") or analyze_materials(materials)
    opts = dict(parsed.get("packing_options") or {})
    if base_options:
        # 显式 API options 覆盖 NL 推导（调用方优先）
        merged = {**opts, **dict(base_options)}
        opts = merged

    lock_n = parsed.get("max_containers")
    if lock_n is None and intents.get("lock_n"):
        lock_n = intents.get("lock_n")

    # goal 启发
    g = goal or "deliver_valid_pack_plan"
    if re_search_min_cabin(raw) or intents.get("prefer_min_cabin"):
        if g == "deliver_valid_pack_plan":
            g = "minimize_containers"
    if intents.get("prefer_export") or re_search_safe(raw):
        if g == "deliver_valid_pack_plan":
            g = "safe_to_ship"

    notes = list(parsed.get("notes") or [])
    notes.insert(
        0,
        "IntentSpec: NL 通用入口 → 物料画像 + 约束 → packing_options（非线路写死）",
    )

    spec = IntentSpec(
        raw_nl=raw,
        goal=g,
        container_type=(container_type or "").strip(),
        container_budget=int(lock_n) if lock_n else None,
        lock_containers=bool(lock_n) or bool(opts.get("lock_max_containers")),
        cargo_mode=str(profile.get("cargo_mode") or "mixed"),
        prefer_dense=bool(intents.get("prefer_dense") or opts.get("dense_mode")),
        prefer_stack=bool(opts.get("prefer_stack", True)),
        prefer_min_cabin=bool(intents.get("prefer_min_cabin")),
        prefer_strict_cog=bool(intents.get("prefer_strict_cog")),
        prefer_export=bool(intents.get("prefer_export")),
        crate_passthrough=opts.get("crate_passthrough"),
        standard_boxes=opts.get("standard_boxes"),
        drop_long=bool(intents.get("drop_long")),
        long_threshold_mm=float(intents.get("long_threshold_mm") or 6000),
        keep_families=list(intents.get("keep_families") or []),
        drop_families=list(intents.get("drop_families") or []),
        packing_options=opts,
        material_profile=dict(profile),
        scheme_id=str(parsed.get("scheme_id") or ""),
        confidence=float(parsed.get("confidence") or 0.5),
        notes=notes,
        source=source,
    )
    # 标注架构
    opts.setdefault("architecture", "big_team_a_b")
    opts.setdefault("intent_driven", True)
    spec.packing_options = opts
    return spec


def apply_intent_to_state(
    state: Dict[str, Any],
    spec: IntentSpec,
    *,
    materials: Optional[Sequence[Dict[str, Any]]] = None,
    filter_materials: bool = True,
) -> Dict[str, Any]:
    """把 IntentSpec 写入 PackingState（大 Team 开局）。"""
    s = dict(state)
    s["intent_spec"] = spec.to_dict()
    s["user_input"] = spec.raw_nl or s.get("user_input") or ""
    s["goal"] = spec.goal or s.get("goal") or "deliver_valid_pack_plan"
    if spec.container_type:
        s["container_type"] = spec.container_type
    mc = spec.max_containers()
    if mc > 0:
        s["max_containers"] = mc
    base = dict(s.get("packing_options") or {})
    base.update(spec.packing_options or {})
    s["packing_options"] = base
    s["material_profile"] = spec.material_profile

    mats = list(materials if materials is not None else (s.get("materials") or []))
    if filter_materials and mats and (
        spec.drop_long or spec.keep_families or spec.drop_families
    ):
        from packing_assistant.nl_whatif import apply_material_selection

        selected, sel_notes = apply_material_selection(mats, {
            "intents": {
                "drop_long": spec.drop_long,
                "long_threshold_mm": spec.long_threshold_mm,
                "keep_families": spec.keep_families,
                "drop_families": spec.drop_families,
            },
            "material_profile": spec.material_profile,
            "raw": spec.raw_nl,
        })
        s["materials"] = selected
        notes = list(spec.notes) + list(sel_notes)
        s["intent_spec"] = {**spec.to_dict(), "notes": notes}
    elif materials is not None:
        s["materials"] = list(materials)

    s["team_architecture"] = {
        "mode": "big_team_wraps_a_b",
        "big_team": "orchestrate + hitl + critic + finalize",
        "team_a": "box_specialists",
        "team_b": "load_specialists",
        "agent_style": "nl_general_agent_with_tools",
    }
    s["team_mode"] = "big_team_a_b"
    return s


def intent_from_api(
    *,
    user_input: str = "",
    materials: Optional[Sequence[Dict[str, Any]]] = None,
    packing_options: Optional[Dict[str, Any]] = None,
    max_containers: int = 0,
    goal: str = "deliver_valid_pack_plan",
    container_type: str = "",
    source: str = "api",
) -> IntentSpec:
    """表单/API 入口：有 NL 则解析，否则仅用显式参数。"""
    spec = interpret_nl(
        user_input,
        materials=materials,
        base_options=packing_options,
        goal=goal,
        container_type=container_type,
        source=source,
    )
    if max_containers and max_containers > 0 and not spec.container_budget:
        spec.container_budget = int(max_containers)
        spec.lock_containers = True
        opts = dict(spec.packing_options)
        opts["lock_max_containers"] = True
        opts["container_budget"] = int(max_containers)
        opts["meeting_cap"] = True
        opts["fixed_container_budget"] = True
        spec.packing_options = opts
    return spec


def re_search_min_cabin(text: str) -> bool:
    import re

    return bool(re.search(r"最少柜|少柜|压柜|minimize", text or "", re.I))


def re_search_safe(text: str) -> bool:
    import re

    return bool(re.search(r"安全出运|出运严格|safe.?to.?ship|严格合规", text or "", re.I))
