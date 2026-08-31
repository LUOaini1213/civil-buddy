"""
2D 布局出图：基于 container_plan 用 matplotlib 绘制侧视示意。

多柜时：每柜一张图 + 可选总览网格图。
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

# uvicorn 工作线程禁止弹 GUI；必须在 import pyplot 前设 Agg
os.environ.setdefault("MPLBACKEND", "Agg")
try:
    import matplotlib

    matplotlib.use("Agg")
except Exception:
    pass

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


def _fit_label(
    ax,
    cx: float,
    cy: float,
    text: str,
    box_w: float,
    box_h: float,
    *,
    base_size: float = 8.0,
    min_size: float = 4.5,
    color: str = "white",
):
    """把箱号塞进箱子里，塞不下宁可不画，也不要糊成一团。

    真实缺陷：原先每个箱子固定 ``fontsize=8`` 居中写箱号，窄箱上文字宽度远超箱宽，
    直接溢出压到相邻箱号上，多个标签叠成一坨（见 output/side_*.png 右半段
    BOX-14/15、BOX-06/16、BOX-10/09）。多柜网格图每柜只有 6 inch，更糊。

    策略三级降级：
      1. 按可用宽度等比缩字号（不低于 ``min_size``）；
      2. 仍放不下就竖排——箱高方向比箱宽方向富余得多；
      3. 竖排也放不下才放弃该标签（箱体颜色仍在，箱号可在装箱方案表里查）。

    必须在 ``set_xlim`` / ``set_ylim`` / ``set_aspect`` **之后**调用：
    坐标变换在那之前还不是最终值，量出来的像素宽度是错的。
    """
    if not text:
        return None
    t = ax.text(
        cx, cy, str(text),
        ha="center", va="center",
        fontsize=base_size, color=color, fontweight="bold", zorder=5,
    )
    try:
        ax.apply_aspect()  # aspect="equal" 会改轴框，先落定再量
        renderer = ax.figure.canvas.get_renderer()
    except Exception:
        renderer = None
    if renderer is None:
        # 拿不到 renderer（非 Agg 等）：退化为按字符数的保守估计，宁可小也不要溢出
        est = max(1, len(str(text)))
        if box_w < 0.16 * est:
            t.set_fontsize(min_size)
            t.set_rotation(90)
        return t

    def _span_px(w: float, h: float):
        x0, y0 = ax.transData.transform((0.0, 0.0))
        x1, y1 = ax.transData.transform((w, h))
        return abs(x1 - x0), abs(y1 - y0)

    box_px_w, box_px_h = _span_px(box_w, box_h)
    avail_w = box_px_w * 0.88

    bb = t.get_window_extent(renderer)
    if bb.width <= avail_w:
        return t

    # 1) 等比缩字号
    scaled = base_size * avail_w / max(bb.width, 1e-6)
    if scaled >= min_size:
        t.set_fontsize(scaled)
        return t

    # 2) 竖排：比的是「文字高度 vs 箱宽」和「文字长度 vs 箱高」
    t.set_rotation(90)
    for size in (base_size, base_size * 0.85, min_size):
        t.set_fontsize(size)
        bb = t.get_window_extent(renderer)
        if bb.width <= avail_w and bb.height <= box_px_h * 0.92:
            return t

    # 3) 放弃：不画比糊成一团强
    t.remove()
    return None


def _draw_one_ax(
    ax,
    items: List[Dict[str, Any]],
    max_len: float,
    title: str,
    *,
    annotations: Optional[List[Dict[str, Any]]] = None,
) -> None:
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
    pad_ids = set()
    for a in annotations or []:
        if a.get("type") == "pad_beam" and a.get("box_id"):
            pad_ids.add(str(a.get("box_id")))

    _pending_labels: List[Tuple[float, float, Any, Optional[float]]] = []
    for i, item in enumerate(items):
        start = float(item.get("起始位置_m") or item.get("x_m") or 0)
        length = float(item.get("长度_m") or item.get("dx_m") or 0.5)
        box_id = item.get("箱号") or item.get("box_id") or ""
        face = _COLOR_CYCLE[i % len(_COLOR_CYCLE)]
        is_pad = str(box_id) in pad_ids
        ax.add_patch(
            FancyBboxPatch(
                (start, 0.15),
                length,
                0.7,
                boxstyle="round,pad=0.02,rounding_size=0.05",
                facecolor=face,
                edgecolor="#c0392b" if is_pad else "white",
                linewidth=2.2 if is_pad else 1.2,
                alpha=0.9,
            )
        )
        # 箱号推迟到轴范围/aspect 落定后再画：那时坐标变换才是最终值，才量得准。
        # 同时记下 x 区间与宽度方向坐标，供下面的「同段柜长多箱」分层排布使用。
        _y_hint = item.get("y_m")
        if _y_hint is None and item.get("y_mm") is not None:
            _y_hint = float(item.get("y_mm")) / 1000.0
        _pending_labels.append((start, length, box_id, _y_hint))
        if is_pad:
            ax.text(
                start + length / 2,
                0.95,
                "垫梁",
                ha="center",
                va="bottom",
                fontsize=7,
                color="#c0392b",
                fontweight="bold",
            )

    # 空隙：在柜底画橙色竖线/区间
    for a in annotations or []:
        if a.get("type") != "void_fill":
            continue
        gap_mm = float(a.get("gap_mm") or 0)
        if gap_mm <= 0:
            continue
        # 优先用 layout 算出的真实 x_m
        if a.get("x_m") is not None:
            x0 = float(a.get("x_m"))
        elif a.get("x_mm") is not None:
            x0 = float(a.get("x_mm")) / 1000.0
        else:
            x0 = max_len * 0.35
        w = min(max_len * 0.25, max(0.12, gap_mm / 1000.0))
        ax.axvspan(x0, min(max_len, x0 + w), ymin=0.05, ymax=0.12, color="#e67e22", alpha=0.85)
        ax.text(
            x0 + w / 2,
            0.02,
            f"空隙{gap_mm:.0f}mm",
            ha="center",
            va="bottom",
            fontsize=6,
            color="#d35400",
        )

    ax.set_xlim(-0.2, max_len + 0.5)
    ax.set_ylim(-0.15, 1.35)
    ax.set_xlabel("柜长方向 (m)")
    ax.set_yticks([])
    ax.set_title(title, fontsize=10)
    ax.set_aspect("equal", adjustable="box")
    ax.grid(axis="x", linestyle="--", alpha=0.4)

    # 箱号最后画：此时 xlim/ylim/aspect 已定，_fit_label 量到的像素宽度才是真的。
    #
    # 关键缺陷（实测 output/side_20260831_112518.png）：侧视图是沿**柜宽方向**的投影，
    # 并排两列的箱子 x 完全相同（BOX-04 y=0 与 BOX-03 y=1150 同为 x=3750..5000mm），
    # 两个箱号会**精确压在同一点**上糊成一团——不是窄箱溢出，缩字号根本救不了。
    # 解法：按 x 区间分组，同组在箱高方向分层排布；既不重叠，又如实表达
    # 「这一段柜长上并排放了几箱」。
    _groups: List[List[Tuple[float, float, Any, Optional[float]]]] = []
    for _lab in sorted(
        _pending_labels,
        key=lambda r: (r[0], r[3] if r[3] is not None else 0.0),
    ):
        _hit = None
        for _g in _groups:
            _gs = min(x for x, _w, _b, _y in _g)
            _ge = max(x + _w for x, _w, _b, _y in _g)
            if _lab[0] < _ge - 1e-6 and _lab[0] + _lab[1] > _gs + 1e-6:
                _hit = _g
                break
        if _hit is not None:
            _hit.append(_lab)
        else:
            _groups.append([_lab])
    for _g in _groups:
        _n = len(_g)
        _base = 8.0 if _n == 1 else max(5.0, 8.0 - 1.5 * (_n - 1))
        for _i, (_start, _len, _bid, _y) in enumerate(_g):
            _cy = 0.15 + 0.7 * ((_i + 0.5) / _n)
            _fit_label(
                ax, _start + _len / 2.0, _cy, _bid, _len, 0.7 / _n,
                base_size=_base,
            )


def _annotations_for_container(
    plan: Dict[str, Any], cno: int
) -> List[Dict[str, Any]]:
    """从 secure_work_order / layout 提取本柜标注。"""
    swo = plan.get("secure_work_order") or {}
    items = list(swo.get("items") or [])
    if not items:
        for key in ("void_fills", "pad_beams"):
            for row in swo.get(key) or []:
                items.append(row)
    out: List[Dict[str, Any]] = []
    layout = plan.get("layout") or []
    pos_by_id: Dict[str, float] = {}
    for it in layout:
        if int(it.get("container_no") or 1) != cno:
            continue
        bid = str(it.get("box_id") or "")
        pos = it.get("position") or {}
        if bid:
            pos_by_id[bid] = float(pos.get("x") or 0) / 1000.0
    for row in items:
        rc = row.get("container_no")
        if rc is not None and int(rc) != cno:
            continue
        r = dict(row)
        bid = str(r.get("box_id") or "")
        if bid and bid in pos_by_id:
            r["x_m"] = pos_by_id[bid]
        # void 无柜号时各柜都淡标一次
        if r.get("type") == "void_fill" or r.get("type") == "pad_beam" or r.get("type") in (
            "void_fill",
            "pad_beam",
            "strapping",
        ):
            if rc is None and r.get("type") == "void_fill" and cno != 1:
                continue
            out.append(r)
    return out


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
    outer_label = (
        container_plan.get("外廓摆柜率")
        or container_plan.get("空间利用率")
        or "-"
    )
    book_label = container_plan.get("订柜有效体积率") or "-"
    title = (
        f"{ctype} 拼柜布局 | {container_plan.get('结论', '')} | "
        f"外廓摆柜 {outer_label} / 订柜有效体积 {book_label} / "
        f"重量 {container_plan.get('重量利用率', '-')} "
        f"（外廓≠订柜）"
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
    outer_u = float(
        plan.get("outer_space_utilization") or plan.get("space_utilization") or 0
    )
    book_u = float(plan.get("booking_volume_utilization") or 0)
    weight = float(plan.get("weight_utilization") or 0)
    can = plan.get("can_fit")
    msg = plan.get("message") or ("可装下" if can else "未完全装下")
    dual = (
        f"订柜有效体积{book_u*100:.0f}%｜外廓摆柜{outer_u*100:.0f}%｜重量{weight*100:.0f}%"
        f"（外廓≠订柜）"
    )
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
            # per-container volume_utilization 是外廓几何，禁止写成订柜
            sub += f" | 外廓{float(vol)*100:.0f}%"
        if load is not None:
            sub += f" | {float(load):.0f}kg"
        anns = _annotations_for_container(plan, cno)
        n_ann = len(anns)
        if n_ann:
            sub += f" | 工单标{n_ann}"
        title = f"{ctype} {sub} | {dual}"
        path = os.path.join(output_dir, f"{prefix}_c{cno:02d}.png")
        fig, ax = plt.subplots(figsize=(12, 2.8))
        _draw_one_ax(ax, items, max_len, title, annotations=anns)
        fig.tight_layout()
        fig.savefig(path, dpi=140, bbox_inches="tight")
        plt.close(fig)
        per_out.append(
            {
                "container_no": cno,
                "path": path,
                "boxes": len(items),
                "annotations": n_ann,
            }
        )
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
        f"{ctype} 共{n}柜侧视总览 | {msg} | {dual}",
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
