"""
2D 布局出图：基于 container_plan 用 matplotlib 绘制侧视示意。

多柜时：每柜一张图 + 可选总览网格图。
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from packing_assistant.tools.consolidation import CONTAINER_SPECS

_COLOR_CYCLE = [
    "#4C78A8",
    "#54A24B",
    "#F58518",
    "#B279A2",
    "#72B7B2",
    "#9D755D",
    "#E45756",
    "#BAB0AC",
]


def _setup_cjk_font() -> None:
    try:
        import matplotlib.pyplot as plt
        from matplotlib import font_manager
    except ImportError:
        return
    for font_name in ("Microsoft YaHei", "SimHei", "SimSun", "Arial Unicode MS"):
        try:
            plt.rcParams["font.sans-serif"] = [font_name, "DejaVu Sans"]
            plt.rcParams["axes.unicode_minus"] = False
            font_manager.findfont(font_name, fallback_to_default=False)
            break
        except Exception:
            continue


def _draw_one_ax(ax, items: List[Dict[str, Any]], max_len: float, title: str) -> None:
    from matplotlib.patches import FancyBboxPatch, Rectangle

    ax.add_patch(
        Rectangle(
            (0, 0),
            max_len,
            1.0,
            fill=False,
            edgecolor="black",
            linewidth=2,
        )
    )
    for i, item in enumerate(items):
        start = float(item.get("起始位置_m") or item.get("x_m") or 0)
        length = float(item.get("长度_m") or item.get("dx_m") or 0.5)
        box_id = item.get("箱号") or item.get("box_id") or ""
        face = _COLOR_CYCLE[i % len(_COLOR_CYCLE)]
        ax.add_patch(
            FancyBboxPatch(
                (start, 0.15),
                length,
                0.7,
                boxstyle="round,pad=0.02,rounding_size=0.05",
                facecolor=face,
                edgecolor="white",
                linewidth=1.2,
                alpha=0.9,
            )
        )
        ax.text(
            start + length / 2,
            0.5,
            box_id,
            ha="center",
            va="center",
            fontsize=8,
            color="white",
            fontweight="bold",
        )
    ax.set_xlim(-0.2, max_len + 0.5)
    ax.set_ylim(-0.15, 1.35)
    ax.set_xlabel("柜长方向 (m)")
    ax.set_yticks([])
    ax.set_title(title, fontsize=10)
    ax.set_aspect("equal", adjustable="box")
    ax.grid(axis="x", linestyle="--", alpha=0.4)


def draw_layout(
    container_plan: Dict[str, Any],
    output_dir: str = "output",
    filename: Optional[str] = None,
) -> str:
    """
    生成 2D 布局图，返回图片路径。

    若布局项含 柜号/container_no 且多于 1 柜，仍画「全部叠在一柜」的兼容图
    （旧行为）；推荐改用 draw_layout_multi。
    """
    os.makedirs(output_dir, exist_ok=True)
    if not filename:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"layout_{ts}.png"
    path = os.path.join(output_dir, filename)

    layout = container_plan.get("布局") or []
    ctype = container_plan.get("柜型") or "40HQ"
    spec = CONTAINER_SPECS.get(ctype, CONTAINER_SPECS["40HQ"])
    max_len = float(spec["长_m"])

    try:
        import matplotlib.pyplot as plt
    except ImportError:
        txt_path = path.replace(".png", ".txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(f"柜型: {ctype}\n结论: {container_plan.get('结论')}\n布局:\n")
            for item in layout:
                f.write(f"  {item}\n")
        return txt_path

    _setup_cjk_font()
    fig, ax = plt.subplots(figsize=(12, 3.5))
    title = (
        f"{ctype} 拼柜布局 | {container_plan.get('结论', '')} | "
        f"空间 {container_plan.get('空间利用率', '-')} / "
        f"重量 {container_plan.get('重量利用率', '-')}"
    )
    _draw_one_ax(ax, layout, max_len, title)
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def draw_layout_multi(
    plan: Dict[str, Any],
    *,
    container_type: str = "40HQ",
    output_dir: str = "output",
    prefix: Optional[str] = None,
) -> Dict[str, Any]:
    """
    按 container_no 为每柜出侧视图，并生成总览网格。

    返回:
      {
        "per_container": [{"container_no": 1, "path": "...", "boxes": n}, ...],
        "overview_path": "...",
        "primary_path": 第一柜或总览路径,
      }
    """
    os.makedirs(output_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix = prefix or f"side_{ts}"
    ctype = container_type or plan.get("container_type") or "40HQ"
    spec = CONTAINER_SPECS.get(ctype, CONTAINER_SPECS["40HQ"])
    max_len = float(spec["长_m"])

    layout = plan.get("layout") or plan.get("布局") or []
    # 归一化为分组
    groups: Dict[int, List[Dict[str, Any]]] = {}
    for it in layout:
        cno = int(it.get("container_no") or it.get("柜号") or 1)
        pos = it.get("position") or {}
        size = it.get("size") or {}
        if pos.get("x") is not None or size.get("dx") is not None:
            x_m = float(pos.get("x") or 0) / 1000.0
            dx_m = float(size.get("dx") or 0) / 1000.0
        else:
            x_m = float(it.get("起始位置_m") or 0)
            dx_m = float(it.get("长度_m") or 0.5)
        item = {
            "箱号": it.get("box_id") or it.get("箱号") or "",
            "起始位置_m": x_m,
            "长度_m": dx_m,
        }
        groups.setdefault(cno, []).append(item)

    if not groups:
        return {"per_container": [], "overview_path": None, "primary_path": None}

    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return {"per_container": [], "overview_path": None, "primary_path": None}

    _setup_cjk_font()
    space = float(plan.get("space_utilization") or 0)
    weight = float(plan.get("weight_utilization") or 0)
    can = plan.get("can_fit")
    msg = plan.get("message") or ("可装下" if can else "未完全装下")
    per_stats = {
        int(p.get("container_no") or 0): p for p in (plan.get("per_container") or [])
    }

    per_out: List[Dict[str, Any]] = []
    paths: List[str] = []
    for cno in sorted(groups.keys()):
        items = groups[cno]
        st = per_stats.get(cno) or {}
        vol = st.get("volume_utilization")
        load = st.get("load_kg")
        nbox = st.get("boxes") or len(items)
        sub = f"第{cno}柜/{len(groups)} | {nbox}箱"
        if vol is not None:
            sub += f" | 容积{float(vol)*100:.0f}%"
        if load is not None:
            sub += f" | {float(load):.0f}kg"
        title = f"{ctype} {sub} | {msg}"
        path = os.path.join(output_dir, f"{prefix}_c{cno:02d}.png")
        fig, ax = plt.subplots(figsize=(12, 2.8))
        _draw_one_ax(ax, items, max_len, title)
        fig.tight_layout()
        fig.savefig(path, dpi=140, bbox_inches="tight")
        plt.close(fig)
        per_out.append({"container_no": cno, "path": path, "boxes": len(items)})
        paths.append(path)

    # 总览：最多 16 柜一页网格
    n = len(groups)
    cols = 2 if n <= 4 else (3 if n <= 9 else 4)
    rows = (n + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(6 * cols, 2.6 * rows))
    if rows == 1 and cols == 1:
        axes_list = [axes]
    else:
        axes_list = list(axes.flatten()) if hasattr(axes, "flatten") else [axes]
    for idx, cno in enumerate(sorted(groups.keys())):
        ax = axes_list[idx]
        st = per_stats.get(cno) or {}
        nbox = st.get("boxes") or len(groups[cno])
        vol = st.get("volume_utilization")
        t = f"#{cno} · {nbox}箱"
        if vol is not None:
            t += f" · {float(vol)*100:.0f}%"
        _draw_one_ax(ax, groups[cno], max_len, t)
    for j in range(len(groups), len(axes_list)):
        axes_list[j].axis("off")
    fig.suptitle(
        f"{ctype} 共{n}柜侧视总览 | {msg} | 总空间{space*100:.0f}% 总重量{weight*100:.0f}%",
        fontsize=12,
        y=1.01,
    )
    fig.tight_layout()
    overview = os.path.join(output_dir, f"{prefix}_overview.png")
    fig.savefig(overview, dpi=130, bbox_inches="tight")
    plt.close(fig)

    return {
        "per_container": per_out,
        "overview_path": overview,
        "primary_path": overview or (paths[0] if paths else None),
        "all_paths": paths + ([overview] if overview else []),
    }
