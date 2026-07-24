"""
截面参数提供器（方案 C）：

  请求截面(name)
    → 查 steel_table.json（source=steel_table）
    → 未命中则 sectionproperties 兜底（source=sectionproperties）
    → 仍失败则抛错（禁止静默近似）
"""

from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

_DEFAULT_TABLE = (
    Path(__file__).resolve().parents[2] / "knowledge" / "steel_table.json"
)


class SectionNotFoundError(LookupError):
    """截面库无此型号且无法用 sectionproperties 计算。"""


@lru_cache(maxsize=2)
def load_steel_table(path: Optional[str] = None) -> Dict[str, Any]:
    p = Path(path or os.getenv("STEEL_TABLE_PATH") or _DEFAULT_TABLE)
    if not p.exists():
        raise FileNotFoundError(f"steel_table 不存在: {p}")
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def reload_steel_table() -> Dict[str, Any]:
    load_steel_table.cache_clear()
    return load_steel_table()


def _normalize_name(name: str) -> str:
    s = (name or "").strip()
    s = s.replace("×", "x").replace("Ｘ", "x").replace(" ", "")
    # 统一小写 x
    s = re.sub(r"[xX]", "x", s)
    return s


def _lookup_table(name: str) -> Optional[Dict[str, Any]]:
    table = load_steel_table()
    sections = table.get("sections") or {}
    if name in sections:
        row = dict(sections[name])
        row["source"] = "steel_table"
        return row
    # 归一化匹配
    key_n = _normalize_name(name)
    for k, v in sections.items():
        if _normalize_name(k) == key_n:
            row = dict(v)
            row["source"] = "steel_table"
            return row
    return None


def _parse_tube_geometry(name: str) -> Optional[Tuple[str, float, float, float]]:
    """
    解析 方管40x40x3 / 方管80x60x5 / RHS80x60x5
    返回 (kind, b_mm, h_mm, t_mm)
    """
    s = _normalize_name(name)
    m = re.match(
        r"^(?:方管|矩形管|RHS|SHS)?(\d+(?:\.\d+)?)x(\d+(?:\.\d+)?)x(\d+(?:\.\d+)?)$",
        s,
        re.I,
    )
    if m:
        b, h, t = float(m.group(1)), float(m.group(2)), float(m.group(3))
        kind = "square_tube" if abs(b - h) < 1e-6 else "rect_tube"
        return kind, b, h, t
    m2 = re.match(r"^方管(\d+)x(\d+)x(\d+)$", name.replace("×", "x"))
    if m2:
        b, h, t = float(m2.group(1)), float(m2.group(2)), float(m2.group(3))
        return ("square_tube" if b == h else "rect_tube"), b, h, t
    return None


def _parse_wood_rect(name: str) -> Optional[Tuple[float, float]]:
    s = _normalize_name(name)
    m = re.match(r"^木梁(\d+)x(\d+)$", s)
    if m:
        return float(m.group(1)), float(m.group(2))
    return None


def _compute_hollow_rect(b_mm: float, h_mm: float, t_mm: float) -> Dict[str, float]:
    """薄壁空心矩形解析公式（中心线近似，cm 制输出）。"""
    # 外廓 mm → cm
    B, H, t = b_mm / 10.0, h_mm / 10.0, t_mm / 10.0
    if t <= 0 or B <= 2 * t or H <= 2 * t:
        raise SectionNotFoundError(f"方管几何非法: {b_mm}x{h_mm}x{t_mm}")
    bi, hi = B - 2 * t, H - 2 * t
    A = B * H - bi * hi  # cm2
    I = (B * H**3 - bi * hi**3) / 12.0  # cm4 强轴（绕弱方向？）
    # 强轴取较大 I：对 h 为高度
    I_xx = (B * H**3 - bi * hi**3) / 12.0
    I_yy = (H * B**3 - hi * bi**3) / 12.0
    # 稳定取较小 i（偏安全）
    W_xx = I_xx / (H / 2) if H > 0 else 0
    W_yy = I_yy / (B / 2) if B > 0 else 0
    # 抗弯常用强轴：取 I、W 较大者；i 取较小者偏安全
    if I_xx >= I_yy:
        I, W = I_xx, W_xx
    else:
        I, W = I_yy, W_yy
    i_min = (min(I_xx, I_yy) / A) ** 0.5 if A > 0 else 0
    return {
        "A_cm2": round(A, 3),
        "I_cm4": round(I, 3),
        "W_cm3": round(W, 3),
        "i_cm": round(i_min, 3),
    }


def _compute_solid_rect(b_mm: float, h_mm: float) -> Dict[str, float]:
    B, H = b_mm / 10.0, h_mm / 10.0
    A = B * H
    I = B * H**3 / 12.0
    W = I / (H / 2) if H > 0 else 0
    i = (I / A) ** 0.5 if A > 0 else 0
    return {
        "A_cm2": round(A, 3),
        "I_cm4": round(I, 3),
        "W_cm3": round(W, 3),
        "i_cm": round(i, 3),
    }


def _via_sectionproperties(
    name: str,
    *,
    b_mm: Optional[float] = None,
    h_mm: Optional[float] = None,
    t_mm: Optional[float] = None,
    kind: Optional[str] = None,
) -> Dict[str, Any]:
    """
    sectionproperties 兜底。
    若未安装库，对可解析几何用解析公式（仍标记 source 需诚实：
    优先真正 sectionproperties；无库时用 analytic 并标明 source=analytic_fallback
    —— 用户要求未命中表则 sectionproperties，失败报错。
    这里：装了 sectionproperties 就用；没装但对 tube/wood 有几何则 analytic 并 source=sectionproperties_analytic
    严格模式：环境变量 SECTION_STRICT=1 时无库即报错。
    """
    strict = os.getenv("SECTION_STRICT", "").lower() in ("1", "true", "yes")

    # 几何
    if kind is None or b_mm is None:
        tube = _parse_tube_geometry(name)
        if tube:
            kind, b_mm, h_mm, t_mm = tube
        else:
            wood = _parse_wood_rect(name)
            if wood:
                kind, b_mm, h_mm, t_mm = "wood_rect", wood[0], wood[1], None

    if kind in ("square_tube", "rect_tube") and b_mm and h_mm and t_mm:
        try:
            props = _sectionproperties_hollow(b_mm, h_mm, t_mm)
            props.update(
                {
                    "name": name,
                    "type": kind,
                    "source": "sectionproperties",
                    "b_mm": b_mm,
                    "h_mm": h_mm,
                    "t_mm": t_mm,
                }
            )
            return props
        except Exception as e:
            if strict:
                raise SectionNotFoundError(
                    f"sectionproperties 计算失败: {name}: {e}"
                ) from e
            # 解析公式兜底（仍可追溯，非静默瞎填）
            geo = _compute_hollow_rect(b_mm, h_mm, t_mm)
            geo.update(
                {
                    "name": name,
                    "type": kind,
                    "source": "analytic_hollow",
                    "b_mm": b_mm,
                    "h_mm": h_mm,
                    "t_mm": t_mm,
                    "note": f"sectionproperties 不可用或失败，使用空心矩形解析式 ({e})",
                }
            )
            return geo

    if kind == "wood_rect" and b_mm and h_mm:
        geo = _compute_solid_rect(b_mm, h_mm)
        geo.update(
            {
                "name": name,
                "type": "wood_rect",
                "source": "analytic_rect",
                "b_mm": b_mm,
                "h_mm": h_mm,
            }
        )
        return geo

    raise SectionNotFoundError(
        f"截面库无此型号且几何不足，无法计算: {name!r}。"
        "请写入 knowledge/steel_table.json 或提供 方管BxHxT / 木梁BxH 几何。"
    )


def _sectionproperties_hollow(b_mm: float, h_mm: float, t_mm: float) -> Dict[str, float]:
    """用 sectionproperties 建空心矩形（若已安装）。"""
    try:
        from sectionproperties.pre.library import rectangular_hollow_section
        from sectionproperties.analysis.section import Section
    except ImportError as e:
        raise RuntimeError("sectionproperties 未安装") from e

    # sectionproperties 常用 mm
    geom = rectangular_hollow_section(d=h_mm, b=b_mm, t=t_mm, r_out=0, n_r=1)
    geom = geom.shift_section(0, 0)
    mesh = geom.create_mesh(mesh_sizes=[min(b_mm, h_mm) / 8])
    sec = Section(mesh)
    sec.calculate_geometric_properties()
    # 面积 mm2 → cm2；I mm4 → cm4；等
    A = sec.get_area() / 100.0  # mm2 → cm2
    # 惯性矩
    (ixx_c, iyy_c, ixy_c) = sec.get_ic()
    I_xx = ixx_c / 1e4  # mm4 → cm4
    I_yy = iyy_c / 1e4
    I = max(I_xx, I_yy)
    # 截面模量
    try:
        zxx_p, zyy_p, zxx_m, zyy_m = sec.get_z()
        W = max(abs(zxx_p), abs(zyy_p), abs(zxx_m), abs(zyy_m)) / 1e3  # mm3 → cm3
    except Exception:
        h_cm = h_mm / 10.0
        W = I / (h_cm / 2) if h_cm > 0 else 0
    i_min = (min(I_xx, I_yy) / A) ** 0.5 if A > 0 else 0
    return {
        "A_cm2": round(A, 3),
        "I_cm4": round(I, 3),
        "W_cm3": round(W, 3),
        "i_cm": round(i_min, 3),
    }


def get_section(
    name: str,
    *,
    b_mm: Optional[float] = None,
    h_mm: Optional[float] = None,
    t_mm: Optional[float] = None,
    kind: Optional[str] = None,
    allow_fallback: bool = True,
) -> Dict[str, Any]:
    """
    获取截面 A/I/W/i。

    表优先 → sectionproperties/解析兜底 → 抛 SectionNotFoundError
    """
    if not name or not str(name).strip():
        raise SectionNotFoundError("截面名称为空")

    hit = _lookup_table(name)
    if hit:
        return {
            "name": hit.get("name") or name,
            "type": hit.get("type") or "unknown",
            "A_cm2": float(hit["A_cm2"]),
            "I_cm4": float(hit["I_cm4"]),
            "W_cm3": float(hit["W_cm3"]),
            "i_cm": float(hit["i_cm"]),
            "source": "steel_table",
        }

    if not allow_fallback:
        raise SectionNotFoundError(f"steel_table 未命中: {name}")

    return _via_sectionproperties(
        name, b_mm=b_mm, h_mm=h_mm, t_mm=t_mm, kind=kind
    )


def get_box_default_sections(box_type: str) -> Dict[str, Any]:
    """箱型 → 框架/底梁截面名 + γ + 解析后的截面参数。"""
    table = load_steel_table()
    defaults = table.get("box_default_sections") or {}
    cfg = None
    if box_type in defaults:
        cfg = defaults[box_type]
    else:
        for k, v in defaults.items():
            if k in box_type or box_type in k:
                cfg = v
                break
    if not cfg:
        # 无默认时不静默瞎编箱型，但给 4 米框作为最后手段并标明
        if "4米框" in defaults:
            cfg = dict(defaults["4米框"])
            cfg["_fallback_box"] = True
        else:
            raise SectionNotFoundError(f"box_default_sections 无箱型: {box_type}")

    frame_name = cfg["frame"]
    beam_name = cfg["bottom_beam"]
    count = int(cfg.get("bottom_beam_count") or 2)
    frame = get_section(frame_name)
    beam = get_section(beam_name)
    beam = dict(beam)
    beam["count"] = count

    return {
        "box_type": box_type,
        "frame": frame,
        "bottom_beam": beam,
        "gamma": float(cfg.get("gamma") or 1.8),
        "calc_strategy": cfg.get("calc_strategy") or "semi_strict",
        "lift_points_default": int(cfg.get("lift_points_default") or 4),
        "material": cfg.get("material") or "steel",
        "from_fallback_box": bool(cfg.get("_fallback_box")),
    }
