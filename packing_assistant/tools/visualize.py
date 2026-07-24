"""
2D 布局出图：基于 container_plan.布局 用 matplotlib 绘制侧视示意。
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, Optional

from packing_assistant.tools.consolidation import CONTAINER_SPECS


def draw_layout(
    container_plan: Dict[str, Any],
    output_dir: str = "output",
    filename: Optional[str] = None,
) -> str:
    """
    生成 2D 布局图，返回图片路径。

    无 matplotlib 时回退写一个文本占位路径说明。
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
        from matplotlib import font_manager
        from matplotlib.patches import FancyBboxPatch, Rectangle
    except ImportError:
        # 无绘图库时写说明文件
        txt_path = path.replace(".png", ".txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(f"柜型: {ctype}\n结论: {container_plan.get('结论')}\n布局:\n")
            for item in layout:
                f.write(f"  {item}\n")
        return txt_path

    # Windows 中文字体回退，避免 CJK 缺字警告
    for font_name in ("Microsoft YaHei", "SimHei", "SimSun", "Arial Unicode MS"):
        try:
            plt.rcParams["font.sans-serif"] = [font_name, "DejaVu Sans"]
            plt.rcParams["axes.unicode_minus"] = False
            # 探测字体是否可用
            font_manager.findfont(font_name, fallback_to_default=False)
            break
        except Exception:
            continue

    fig, ax = plt.subplots(figsize=(12, 3.5))

    # 柜体轮廓
    ax.add_patch(
        Rectangle(
            (0, 0),
            max_len,
            1.0,
            fill=False,
            edgecolor="black",
            linewidth=2,
            linestyle="-",
        )
    )

    color_map = {
        "blue": "#4C78A8",
        "green": "#54A24B",
        "orange": "#F58518",
        "purple": "#B279A2",
        "teal": "#72B7B2",
        "brown": "#9D755D",
        "pink": "#E45756",
        "gray": "#BAB0AC",
    }

    for item in layout:
        start = float(item.get("起始位置_m") or 0)
        length = float(item.get("长度_m") or 0.5)
        color_name = item.get("颜色") or "blue"
        face = color_map.get(color_name, "#4C78A8")
        box_id = item.get("箱号") or ""

        patch = FancyBboxPatch(
            (start, 0.15),
            length,
            0.7,
            boxstyle="round,pad=0.02,rounding_size=0.05",
            facecolor=face,
            edgecolor="white",
            linewidth=1.2,
            alpha=0.9,
        )
        ax.add_patch(patch)
        ax.text(
            start + length / 2,
            0.5,
            box_id,
            ha="center",
            va="center",
            fontsize=9,
            color="white",
            fontweight="bold",
        )

    ax.set_xlim(-0.2, max_len + 0.5)
    ax.set_ylim(-0.2, 1.4)
    ax.set_xlabel("柜长方向 (m)")
    ax.set_yticks([])
    title = (
        f"{ctype} 拼柜布局 | {container_plan.get('结论', '')} | "
        f"空间 {container_plan.get('空间利用率', '-')} / "
        f"重量 {container_plan.get('重量利用率', '-')}"
    )
    ax.set_title(title, fontsize=11)
    ax.set_aspect("equal", adjustable="box")
    ax.grid(axis="x", linestyle="--", alpha=0.4)

    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path
