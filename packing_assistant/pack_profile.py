"""demo / quality pack profiles — policy only, not a new team graph.

Gateway and demo_one_shot default to demo. Explicit packing_options win
over profile defaults (setdefault-style merge).
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

DEMO = "demo"
QUALITY = "quality"
DEFAULT_PROFILE = DEMO

REPAIR_KEYS = ("lns_worst", "r4_repair", "lateral_repair")
REPAIR_MID50_THRESHOLD = 0.55

_PROFILE_ALIASES = {
    "demo": DEMO,
    "fast": DEMO,
    "iss": DEMO,
    "quality": QUALITY,
    "full": QUALITY,
    "site": QUALITY,
}


def normalize_pack_profile(name: Any) -> str:
    raw = str(name or "").strip().lower()
    if not raw:
        return DEFAULT_PROFILE
    return _PROFILE_ALIASES.get(raw, DEFAULT_PROFILE if raw not in (DEMO, QUALITY) else raw)


def resolve_pack_profile(
    explicit: Any = None,
    packing_options: Optional[Mapping[str, Any]] = None,
) -> str:
    """No explicit profile → demo."""
    opts = dict(packing_options or {})
    if explicit not in (None, ""):
        return normalize_pack_profile(explicit)
    if opts.get("pack_profile") not in (None, ""):
        return normalize_pack_profile(opts.get("pack_profile"))
    return DEFAULT_PROFILE


def profile_defaults(profile: str) -> Dict[str, Any]:
    p = normalize_pack_profile(profile)
    if p == QUALITY:
        return {
            "pack_profile": QUALITY,
            "prefer_stack": True,
            "multi_start": True,
            "multi_start_limit": 4,
            "cog_aware": True,
            "cog_rebalance": True,
            "r0_r1": True,
            "r2_slab": True,
            "r4_repair": False,
            "lns_worst": False,
            "lateral_repair": False,
            "r4_target_mid50": 0.60,
            "corner_support": True,
            "forbid_mid50_extra_n": True,
            "n_search_extra": 8,
            "wall_clock_s": 120.0,
            "skip_structure_if_complete_lwh": False,
        }
    return {
        "pack_profile": DEMO,
        "prefer_stack": True,
        "multi_start": True,
        "multi_start_limit": 2,
        "cog_aware": True,
        "cog_rebalance": False,
        "r0_r1": True,
        "r2_slab": False,
        "r4_repair": False,
        "lns_worst": False,
        "lateral_repair": False,
        "r4_target_mid50": 0.60,
        "corner_support": True,
        "forbid_mid50_extra_n": True,
        "n_search_extra": 1,
        "wall_clock_s": 20.0,
        "skip_structure_if_complete_lwh": True,
    }


def apply_pack_profile(
    packing_options: Optional[Mapping[str, Any]] = None,
    *,
    profile: Any = None,
) -> Dict[str, Any]:
    """Profile defaults first; caller-set keys keep precedence."""
    incoming = dict(packing_options or {})
    p = resolve_pack_profile(profile, incoming)
    merged = {**profile_defaults(p), **incoming}
    merged["pack_profile"] = p
    # demo: never inherit high_util / leaked repair flags
    if p == DEMO:
        for k in REPAIR_KEYS:
            merged[k] = False
        merged["force_cog_repair"] = False
        merged["forbid_mid50_extra_n"] = True
    return merged


def n_search_candidates(n0: int, profile: str, *, n_max: int = 40) -> List[int]:
    """demo: {N0, N0+1}; quality: N0 .. min(n_max, N0+extra)."""
    n0 = max(1, int(n0 or 1))
    cap = max(n0, int(n_max or n0))
    p = normalize_pack_profile(profile)
    extra = 1 if p == DEMO else int(profile_defaults(p).get("n_search_extra") or 8)
    end = min(cap, n0 + extra)
    return list(range(n0, end + 1))


def mid50_driven_extra_n_allowed(profile: str) -> bool:
    """Neither profile adds a container only to lift mid50."""
    return False


def wall_clock_budget_s(profile: str) -> float:
    return float(profile_defaults(profile).get("wall_clock_s") or 20.0)


def decide_next_n(
    *,
    profile: str,
    n0: int,
    tried: Sequence[int],
    last_can_fit: bool,
    elapsed_s: float,
    n_max: int = 40,
    for_mid50: bool = False,
) -> Dict[str, Any]:
    """Pure search policy used by booking/loader (and tests)."""
    p = normalize_pack_profile(profile)
    budget = wall_clock_budget_s(p)
    if float(elapsed_s or 0) >= budget:
        return {
            "next_n": None,
            "stop": "wall_clock",
            "mid50_extra": False,
            "warn": True,
        }
    if for_mid50 and not mid50_driven_extra_n_allowed(p):
        return {
            "next_n": None,
            "stop": "mid50_extra_forbidden",
            "mid50_extra": False,
            "warn": False,
        }
    if last_can_fit and not for_mid50:
        return {
            "next_n": None,
            "stop": "can_fit",
            "mid50_extra": False,
            "warn": False,
        }
    remaining = [n for n in n_search_candidates(n0, p, n_max=n_max) if n not in set(tried)]
    if not remaining:
        return {
            "next_n": None,
            "stop": "exhausted",
            "mid50_extra": False,
            "warn": False,
        }
    return {
        "next_n": int(remaining[0]),
        "stop": None,
        "mid50_extra": False,
        "warn": False,
    }


def annotate_wall_clock_stop(plan: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    out = dict(plan or {})
    out["search_stopped"] = "wall_clock"
    out["pack_search_warn"] = "wall_clock_budget"
    warns = [str(w) for w in (out.get("warnings") or [])]
    if "pack_search_wall_clock" not in warns:
        warns.append("pack_search_wall_clock")
    out["warnings"] = warns
    return out


def repairs_for_worst_mid50(
    profile: str, worst_mid50: Optional[float]
) -> Dict[str, bool]:
    """quality: the three named repairs turn on only when worst_mid50 < 0.55.

    demo: stay off.
    """
    p = normalize_pack_profile(profile)
    off = {k: False for k in REPAIR_KEYS}
    if p != QUALITY:
        return off
    if worst_mid50 is None:
        return off
    try:
        mid = float(worst_mid50)
    except (TypeError, ValueError):
        return off
    on = mid < REPAIR_MID50_THRESHOLD
    return {k: on for k in REPAIR_KEYS}


def _dim_triple(row: Mapping[str, Any]) -> Tuple[float, float, float]:
    if not isinstance(row, Mapping):
        return (0.0, 0.0, 0.0)
    outer = row.get("outer_size_mm") or row.get("外尺寸_mm") or {}
    if isinstance(outer, Mapping):
        L = float(outer.get("length") or outer.get("长") or 0 or 0)
        W = float(outer.get("width") or outer.get("宽") or 0 or 0)
        H = float(outer.get("height") or outer.get("高") or 0 or 0)
        if L > 0 and W > 0 and H > 0:
            return (L, W, H)
    L = float(
        row.get("length_mm")
        or row.get("L")
        or row.get("长")
        or row.get("length")
        or 0
        or 0
    )
    W = float(
        row.get("width_mm")
        or row.get("W")
        or row.get("宽")
        or row.get("width")
        or 0
        or 0
    )
    H = float(
        row.get("height_mm")
        or row.get("H")
        or row.get("高")
        or row.get("height")
        or 0
        or 0
    )
    return (L, W, H)


def _complete_lwh(row: Mapping[str, Any]) -> bool:
    L, W, H = _dim_triple(row)
    return L > 0 and W > 0 and H > 0


def _looks_steel(
    materials: Sequence[Any],
    packing_options: Optional[Mapping[str, Any]] = None,
) -> bool:
    opts = dict(packing_options or {})
    pid = str(opts.get("profile_id") or opts.get("cargo_mode") or "").lower()
    if any(k in pid for k in ("steel", "iron", "fst", "vmu", "钢")):
        return True
    if str(opts.get("material_family") or "").lower() in ("steel", "iron"):
        return True
    for m in materials or []:
        if not isinstance(m, Mapping):
            continue
        blob = " ".join(
            str(m.get(k) or "")
            for k in (
                "category",
                "part_no",
                "name",
                "品名",
                "material",
                "cargo_mode",
                "family",
            )
        ).lower()
        if any(
            tok in blob
            for tok in ("steel", "fst", "vmu", "钢", "铁架", "铁件", "角钢", "槽钢")
        ):
            return True
    return False


def _missing_dims(rows: Sequence[Any]) -> bool:
    rows = [r for r in (rows or []) if isinstance(r, Mapping)]
    if not rows:
        return False
    return any(not _complete_lwh(r) for r in rows)


def _nonstandard_fixture(
    materials: Sequence[Any],
    packing_options: Optional[Mapping[str, Any]] = None,
) -> bool:
    opts = dict(packing_options or {})
    if opts.get("nonstandard") or opts.get("ns_required") or opts.get("require_ns_checklist"):
        return True
    if str(opts.get("profile_id") or "").lower().startswith("ns"):
        return True
    for m in materials or []:
        if not isinstance(m, Mapping):
            continue
        if m.get("nonstandard") or m.get("fixture") or m.get("ns_kind"):
            return True
        cat = str(m.get("category") or m.get("kind") or "").lower()
        if "nonstandard" in cat or "非标" in cat or "夹具" in cat:
            return True
    return False


def _generic_table(packing_options: Optional[Mapping[str, Any]]) -> bool:
    opts = dict(packing_options or {})
    pid = str(opts.get("profile_id") or "").lower()
    return pid in ("generic_table", "generic", "furniture", "ecommerce") or bool(
        opts.get("crate_passthrough")
    )


def should_skip_structure(
    *,
    materials: Optional[Sequence[Any]] = None,
    boxes: Optional[Sequence[Any]] = None,
    packing_options: Optional[Mapping[str, Any]] = None,
) -> Tuple[bool, str]:
    """Skip structure for complete LWH / generic tables.

    Steel, missing dims, and nonstandard fixtures keep the existing path.
    """
    opts = dict(packing_options or {})
    if opts.get("force_structure"):
        return False, ""
    mats = [m for m in (materials or []) if isinstance(m, Mapping)]
    bxs = [b for b in (boxes or []) if isinstance(b, Mapping)]
    if _looks_steel(mats or bxs, opts):
        return False, ""
    if _nonstandard_fixture(mats, opts):
        return False, ""
    if mats and _missing_dims(mats):
        return False, ""
    if bxs and all(_complete_lwh(b) for b in bxs):
        return True, "input_already_boxes_with_lwh"
    if _generic_table(opts) and mats and not _missing_dims(mats):
        return True, "generic_table_complete_lwh"
    if mats and not _missing_dims(mats) and bool(opts.get("skip_structure_if_complete_lwh", True)):
        if not _looks_steel(mats, opts):
            return True, "complete_lwh_generic_cargo"
    return False, ""


# What-if allowlist for the demo surface (three already-used phrases).
DEMO_WHATIF_ALLOWLIST: Tuple[Tuple[str, str], ...] = (
    ("force_40hq", "改 40HQ"),
    ("no_stack", "这票不能叠"),
    ("minus_one_container", "少一柜试试"),
)


def demo_whatif_ids() -> List[str]:
    return [i for i, _ in DEMO_WHATIF_ALLOWLIST]


def cog_pipeline_flags(
    packing_options: Optional[Mapping[str, Any]],
    worst_mid50: Optional[float],
) -> Dict[str, Any]:
    """Flags for bin3d _finish. Named repairs never OR cog_rebalance."""
    opts = apply_pack_profile(packing_options)
    p = str(opts.get("pack_profile") or DEFAULT_PROFILE)
    gates = repairs_for_worst_mid50(p, worst_mid50)
    force_cog = bool(opts.get("cog_rebalance") or opts.get("r1_force"))
    return {
        "pack_profile": p,
        "force_cog": force_cog,
        "do_r01": bool(opts.get("r0_r1", True) or opts.get("r1_shift", True)),
        "do_r2": bool(opts.get("r2_slab", False)),
        "do_r3": bool(opts.get("r3_repack", False)),
        "do_r4": bool(gates.get("r4_repair")),
        "do_lns": bool(gates.get("lns_worst")),
        "do_lat": bool(gates.get("lateral_repair")),
        "gates": gates,
    }
