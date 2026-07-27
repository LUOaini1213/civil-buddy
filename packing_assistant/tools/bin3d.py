"""
纯 Python 3D 装箱引擎（无需 Java / skjolber）。

策略：Largest Area Fit First 风格的简化实现
- 按底面积/体积排序
- Extreme Point 启发式放置
- 支持不旋转（超长件）或 6 向旋转
- 输出与 api-spec container_plan / skjolber 服务一致

说明：不是 skjolber 源码，但 I/O 对齐，便于本机无 JDK 时完整联调。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple


def _container_inner() -> Dict[str, Dict[str, float]]:
    try:
        from packing_assistant.knowledge import container_inner_mm

        data = container_inner_mm()
        if data:
            return data
    except Exception:
        pass
    return {
        "20GP": {"L": 5898, "W": 2352, "H": 2385, "max_load_kg": 21000},
        "40GP": {"L": 12032, "W": 2352, "H": 2385, "max_load_kg": 26680},
        "40HQ": {"L": 12032, "W": 2352, "H": 2698, "max_load_kg": 28610},  # COSCO 铭牌 PAYLOAD
        "45HQ": {"L": 13556, "W": 2352, "H": 2698, "max_load_kg": 27700},
    }


CONTAINER_INNER: Dict[str, Dict[str, float]] = _container_inner()


@dataclass
class Item3D:
    box_id: str
    dx: int
    dy: int
    dz: int
    weight_kg: float
    allow_rotate: bool = True
    no_tip: bool = False  # 铁架等：禁止竖放（高度维不可转到水平外）
    stackable: bool = True  # 可否作为二层货
    prefer_bottom: bool = False  # 必须底层


@dataclass
class Placement3D:
    box_id: str
    x: int
    y: int
    z: int
    dx: int
    dy: int
    dz: int
    container_no: int = 1
    layer: int = 1


@dataclass
class Bin3D:
    L: int
    W: int
    H: int
    max_load_kg: float
    container_no: int = 1
    placements: List[Placement3D] = field(default_factory=list)
    # extreme points (x,y,z)
    points: List[Tuple[int, int, int]] = field(default_factory=lambda: [(0, 0, 0)])

    @property
    def used_weight(self) -> float:
        # weight stored externally via map; sum from optional attr
        return float(getattr(self, "_used_weight", 0.0))

    def add_weight(self, w: float) -> None:
        self._used_weight = float(getattr(self, "_used_weight", 0.0)) + w


def _orientations(item: Item3D) -> List[Tuple[int, int, int]]:
    d = (item.dx, item.dy, item.dz)
    if not item.allow_rotate:
        return [d]
    seen = set()
    out = []
    if item.no_tip:
        # 仅水平面旋转：高度维保持为 z
        cands = (
            (d[0], d[1], d[2]),
            (d[1], d[0], d[2]),
        )
    else:
        cands = (
            (d[0], d[1], d[2]),
            (d[0], d[2], d[1]),
            (d[1], d[0], d[2]),
            (d[1], d[2], d[0]),
            (d[2], d[0], d[1]),
            (d[2], d[1], d[0]),
        )
    for dims in cands:
        if dims not in seen:
            seen.add(dims)
            out.append(dims)
    return out


def _overlaps(a: Placement3D, x: int, y: int, z: int, dx: int, dy: int, dz: int) -> bool:
    return not (
        x + dx <= a.x
        or a.x + a.dx <= x
        or y + dy <= a.y
        or a.y + a.dy <= y
        or z + dz <= a.z
        or a.z + a.dz <= z
    )


def _fits(bin: Bin3D, x: int, y: int, z: int, dx: int, dy: int, dz: int) -> bool:
    if x < 0 or y < 0 or z < 0:
        return False
    if x + dx > bin.L or y + dy > bin.W or z + dz > bin.H:
        return False
    for p in bin.placements:
        if _overlaps(p, x, y, z, dx, dy, dz):
            return False
    return True


def _supported(bin: Bin3D, x: int, y: int, z: int, dx: int, dy: int) -> bool:
    """底部支撑：z==0 或下方有足够接触面积（激进堆叠：≥2 点即可）。"""
    if z == 0:
        return True
    samples = [
        (x + dx // 2, y + dy // 2),
        (x + max(dx // 4, 1), y + max(dy // 4, 1)),
        (x + dx - max(dx // 4, 1), y + max(dy // 4, 1)),
        (x + max(dx // 4, 1), y + dy - max(dy // 4, 1)),
        (x + dx - max(dx // 4, 1), y + dy - max(dy // 4, 1)),
        (x + 1, y + 1),
        (x + dx - 1, y + dy - 1),
    ]
    hits = 0
    for sx, sy in samples:
        for p in bin.placements:
            if p.z + p.dz == z and p.x <= sx < p.x + p.dx and p.y <= sy < p.y + p.dy:
                hits += 1
                break
    # 激进：中心+一角，或任意 2 点
    return hits >= 2


def _add_points(bin: Bin3D, x: int, y: int, z: int, dx: int, dy: int, dz: int) -> None:
    # 更完整的 Extreme Point 集合，利于堆叠与填缝
    candidates = [
        (x + dx, y, z),
        (x, y + dy, z),
        (x, y, z + dz),
        (x + dx, y + dy, z),
        (x + dx, y, z + dz),
        (x, y + dy, z + dz),
    ]
    for c in candidates:
        if 0 <= c[0] <= bin.L and 0 <= c[1] <= bin.W and 0 <= c[2] <= bin.H:
            if c not in bin.points:
                bin.points.append(c)
    # 清理被占满的点；候选过多时截断（保序）
    cleaned = []
    for pt in bin.points:
        inside = any(
            p.x <= pt[0] < p.x + p.dx
            and p.y <= pt[1] < p.y + p.dy
            and p.z <= pt[2] < p.z + p.dz
            for p in bin.placements
        )
        if not inside:
            cleaned.append(pt)
    # 按 z,y,x 排序，优先底层
    cleaned.sort(key=lambda t: (t[2], t[1], t[0]))
    bin.points = cleaned[:400] if len(cleaned) > 400 else cleaned
    if not bin.points:
        bin.points = [(0, 0, 0)]


def try_place(bin: Bin3D, item: Item3D) -> Optional[Placement3D]:
    """
    Extreme-point 放置。

    关键：贴端墙紧装（优先 x=0 / y=0），**禁止**沿柜长居中。
    居中会把 4m 铁架放在 x≈4000，前后都剩不足 4.3m 空隙，导致明明装得下却开第二柜。
    """
    if bin.used_weight + item.weight_kg > bin.max_load_kg + 1e-6:
        return None

    # 候选点：extreme points + 地面双列条带 + 已放箱邻接 + 顶面堆叠
    pts = list(bin.points)
    pts.append((0, 0, 0))
    for dx0, dy0, _ in _orientations(item):
        # 贴两侧壁与并排第二列（不用柜宽居中当主候选）
        pts.append((0, 0, 0))
        if dy0 <= bin.W:
            pts.append((0, max(bin.W - dy0, 0), 0))
        if dy0 * 2 <= bin.W:
            pts.append((0, dy0, 0))
            pts.append((0, max(bin.W - 2 * dy0, 0), 0))
        # 沿柜长条带：步长用箱长，避免跳过可拼缝
        step = max(min(dx0, 250), 100)
        x = 0
        while x + dx0 <= bin.L:
            pts.append((x, 0, 0))
            if dy0 <= bin.W:
                pts.append((x, max(bin.W - dy0, 0), 0))
            if dy0 * 2 <= bin.W:
                pts.append((x, dy0, 0))
            x += step
    # 已放箱：前方/侧方邻接（紧拼）与顶面堆叠
    gap = 0  # mm，铁架可贴放；需要间隙时可调
    for p in bin.placements:
        pts.append((p.x + p.dx + gap, p.y, p.z))
        pts.append((p.x, p.y + p.dy + gap, p.z))
        pts.append((p.x + p.dx + gap, 0, 0))
        pts.append((p.x + p.dx + gap, max(bin.W - p.dy, 0), 0))
        top_z = p.z + p.dz
        if top_z + 100 <= bin.H:
            pts.append((p.x, p.y, top_z))
            pts.append((p.x + max(p.dx // 2, 0), p.y, top_z))
            pts.append((p.x, p.y + max(p.dy // 2, 0), top_z))
            pts.append((p.x + p.dx, p.y, top_z))
            pts.append((p.x, p.y + p.dy, top_z))
    pts = list({p for p in pts})
    # 底层、小 x、小 y 优先尝试
    pts.sort(key=lambda t: (t[2], t[0], t[1]))

    best: Optional[Tuple] = None
    # 左右配平仅作次级目标，不主导前后位置
    mid_y = bin.W / 2.0
    w = max(float(item.weight_kg), 1.0)
    moment = 0.0
    for p in bin.placements:
        pw = float(getattr(p, "weight_kg", 0) or (p.dx * p.dy * p.dz / 1e8))
        moment += pw * ((p.y + p.dy / 2.0) - mid_y)

    for dx, dy, dz in _orientations(item):
        for px, py, pz in pts:
            if not _fits(bin, px, py, pz, dx, dy, dz):
                continue
            if not _supported(bin, px, py, pz, dx, dy):
                continue
            # 二层策略：prefer_bottom 禁止上二层；非 stackable 不上二层
            if pz > 0:
                if item.prefer_bottom or not item.stackable:
                    continue
                if pz + dz > bin.H:
                    continue
            center_y = py + dy / 2.0
            new_moment = abs(moment + w * (center_y - mid_y))
            # y：优先贴侧壁并排（y=0 或 y=dy 列），避免漂在中间
            y_to_wall = min(py, max(bin.W - (py + dy), 0))
            # 可堆叠矮箱略鼓励二层
            z_weight = 0.15 if (item.stackable and not item.prefer_bottom) else 1.0
            residual_h = bin.H - (pz + dz)
            residual_x = bin.L - (px + dx)
            # 词典序越小越好：底层 → 贴端墙(x小) → 贴侧壁并排 → 左右平衡 → 剩余高度
            cand = (
                float(pz) * z_weight,
                float(px),  # 禁止居中：不再用 abs(center_x-mid_x)
                float(y_to_wall),
                new_moment * 0.01,
                residual_h * 0.001,
                -float(residual_x) * 0.0001,  # 略偏好后方仍留长条空位
                float(dx),
                float(dy),
                float(dz),
                float(px),
                float(py),
                float(pz),
            )
            if best is None or cand < best:
                best = cand

    if best is None:
        return None
    # cand 尾部存 dx,dy,dz,x,y,z
    dx, dy, dz, x, y, z = best[6], best[7], best[8], best[9], best[10], best[11]
    dx, dy, dz, x, y, z = int(dx), int(dy), int(dz), int(x), int(y), int(z)
    pl = Placement3D(
        box_id=item.box_id,
        x=x,
        y=y,
        z=z,
        dx=dx,
        dy=dy,
        dz=dz,
        container_no=bin.container_no,
        layer=1 if z == 0 else 2,
    )
    setattr(pl, "weight_kg", float(item.weight_kg or 0))
    bin.placements.append(pl)
    bin.add_weight(item.weight_kg)
    _add_points(bin, x, y, z, dx, dy, dz)
    return pl


def _strip_pack_floor(
    items: List[Item3D],
    *,
    L: int,
    W: int,
    H: int,
    max_load_kg: float,
    container_no: int,
) -> Tuple[List[Placement3D], List[Item3D], float]:
    """
    底层条带装填：长铁架/准同宽箱沿柜长两列并排向前推。
    EP 失败时的兜底，专治「明明 4 个 4m 架能进 1 个 40HQ」。
    """
    if not items:
        return [], [], 0.0
    # 仅处理可卧放的底层件；过高的跳过
    work = [it for it in items if min(it.dx, it.dy, it.dz) <= H]
    if not work:
        return [], list(items), 0.0

    placements: List[Placement3D] = []
    used_w = 0.0
    # 每列当前 x 前沿
    # 两列：y=0 与 y=col_w（若 2*min_width <= W）
    # 先按最长边作长度、次边作宽度
    def orient_floor(it: Item3D) -> Tuple[int, int, int]:
        # 高度尽量用原高（no_tip 时 dz 固定）
        oris = _orientations(it)
        # 选能进柜且底面积大、高度合法的
        best_o = None
        for dx, dy, dz in oris:
            if dx <= L and dy <= W and dz <= H:
                score = (dz <= H, -dx * dy, dz)  # 底层大底面积
                if best_o is None or score < best_o[0]:
                    best_o = (score, dx, dy, dz)
        if best_o is None:
            return it.dx, it.dy, it.dz
        return best_o[1], best_o[2], best_o[3]

    # 估列宽：取众数宽度
    widths = []
    for it in work:
        _, dy, _ = orient_floor(it)
        widths.append(dy)
    col_w = max(widths) if widths else W
    n_cols = 2 if col_w * 2 <= W else 1
    col_front = [0] * n_cols  # 各列已占用长度
    col_y = [0, col_w] if n_cols == 2 else [0]
    left: List[Item3D] = []
    # 长件优先
    ordered = sorted(work, key=lambda it: (-max(it.dx, it.dy, it.dz), -it.weight_kg))
    placed_ids = set()

    for it in ordered:
        if used_w + it.weight_kg > max_load_kg + 1e-6:
            left.append(it)
            continue
        dx, dy, dz = orient_floor(it)
        if dz > H or dy > W or dx > L:
            left.append(it)
            continue
        # 找能放下的列（前沿 + dx <= L，且该列宽够）
        best_c = None
        for c in range(n_cols):
            if dy > (W - col_y[c]) and c == n_cols - 1:
                # 最后一列用靠壁
                y = max(0, W - dy)
            else:
                y = col_y[c]
            x = col_front[c]
            if x + dx <= L and y + dy <= W:
                # 优先前沿更小的列（齐头并进可改：优先前沿更小使两侧齐）
                key = (col_front[c], c)
                if best_c is None or key < best_c[0]:
                    best_c = (key, c, x, y, dx, dy, dz)
        if best_c is None:
            left.append(it)
            continue
        _, c, x, y, dx, dy, dz = best_c
        pl = Placement3D(
            box_id=it.box_id,
            x=x,
            y=y,
            z=0,
            dx=dx,
            dy=dy,
            dz=dz,
            container_no=container_no,
            layer=1,
        )
        setattr(pl, "weight_kg", float(it.weight_kg or 0))
        placements.append(pl)
        used_w += it.weight_kg
        col_front[c] = x + dx
        placed_ids.add(it.box_id)

    left.extend([it for it in items if it.box_id not in placed_ids and it not in left])
    # 去重 left
    seen = set()
    uniq_left = []
    for it in left:
        if it.box_id in placed_ids or it.box_id in seen:
            continue
        seen.add(it.box_id)
        uniq_left.append(it)
    return placements, uniq_left, used_w


def _grid_pack_uniform(
    items: List[Item3D],
    *,
    L: int,
    W: int,
    H: int,
    max_load_kg: float,
    container_no: int,
) -> Tuple[List[Placement3D], List[str], float]:
    """
    同尺寸/准同尺寸纸箱：层状网格装填（贴近网上「层数×每层件数」估算法）。
    返回 placements, unpacked_ids, used_weight。
    """
    if not items:
        return [], [], 0.0
    # 选体积最大朝向下的最优网格
    sample = items[0]
    best_cfg = None  # (nx, ny, nz, dx, dy, dz, per_layer, layers)
    for dx, dy, dz in _orientations(sample):
        if dx > L or dy > W or dz > H:
            continue
        nx = L // dx
        ny = W // dy
        nz = H // dz
        if nx < 1 or ny < 1 or nz < 1:
            continue
        score = (nx * ny * nz, nx * ny, -dz)  # 容量优先
        if best_cfg is None or score > best_cfg[0]:
            best_cfg = (score, nx, ny, nz, dx, dy, dz)
    if best_cfg is None:
        return [], [it.box_id for it in items], 0.0

    _, nx, ny, nz, dx, dy, dz = best_cfg
    placements: List[Placement3D] = []
    used_w = 0.0
    unpacked: List[str] = []
    idx = 0
    n = len(items)
    for iz in range(nz):
        for iy in range(ny):
            for ix in range(nx):
                if idx >= n:
                    return placements, unpacked, used_w
                it = items[idx]
                if used_w + it.weight_kg > max_load_kg + 1e-6:
                    # 剩余超重
                    unpacked.extend(x.box_id for x in items[idx:])
                    return placements, unpacked, used_w
                pl = Placement3D(
                    box_id=it.box_id,
                    x=ix * dx,
                    y=iy * dy,
                    z=iz * dz,
                    dx=dx,
                    dy=dy,
                    dz=dz,
                    container_no=container_no,
                    layer=iz + 1,
                )
                placements.append(pl)
                used_w += it.weight_kg
                idx += 1
    if idx < n:
        unpacked.extend(x.box_id for x in items[idx:])
    return placements, unpacked, used_w


def _is_near_uniform(items: List[Item3D], tol: float = 0.08) -> bool:
    if len(items) < 8:
        return False
    vols = [it.dx * it.dy * it.dz for it in items]
    base = max(vols[0], 1)
    return all(abs(v - base) / base <= tol for v in vols)


def pack_items(
    items: List[Item3D],
    container_type: str = "40HQ",
    max_containers: int = 1,
) -> Dict[str, Any]:
    ctype = container_type if container_type in CONTAINER_INNER else "40HQ"
    spec = CONTAINER_INNER[ctype]
    max_c = max(1, int(max_containers or 1))

    bins: List[Bin3D] = []
    unpacked: List[str] = []
    layout: List[Dict[str, Any]] = []

    def new_bin(no: int) -> Bin3D:
        b = Bin3D(
            L=int(spec["L"]),
            W=int(spec["W"]),
            H=int(spec["H"]),
            max_load_kg=float(spec["max_load_kg"]),
            container_no=no,
        )
        b._used_weight = 0.0
        return b

    remaining = list(items)

    def _append_pls(b: Bin3D, pls: List[Placement3D]) -> None:
        for pl in pls:
            layout.append(
                {
                    "box_id": pl.box_id,
                    "container_no": pl.container_no,
                    "position": {"x": pl.x, "y": pl.y, "z": pl.z},
                    "size": {"dx": pl.dx, "dy": pl.dy, "dz": pl.dz},
                    "rotation": "LWH",
                    "layer": pl.layer,
                }
            )

    # 大量同尺寸纸箱：整柜网格装填（对齐网上 50×40×35cm 类案例）
    if _is_near_uniform(remaining) and len(remaining) >= 12:
        left = list(remaining)
        while left and len(bins) < max_c:
            b = new_bin(len(bins) + 1)
            pls, _unp, used_w = _grid_pack_uniform(
                left,
                L=b.L,
                W=b.W,
                H=b.H,
                max_load_kg=b.max_load_kg,
                container_no=b.container_no,
            )
            if not pls:
                break
            b.placements = pls
            b._used_weight = used_w
            bins.append(b)
            _append_pls(b, pls)
            packed_ids = {p.box_id for p in pls}
            left = [it for it in left if it.box_id not in packed_ids]
        remaining = left
        if remaining and len(bins) >= max_c:
            unpacked.extend(it.box_id for it in remaining)
            remaining = []

    # 混 SKU：按尺寸分组后，尽量用「层状网格占用剩余空间」；不足再 EP
    if remaining and not _is_near_uniform(remaining) and len(remaining) >= 20:
        from collections import defaultdict

        groups: Dict[Tuple[int, int, int], List[Item3D]] = defaultdict(list)
        for it in remaining:
            key = tuple(sorted((it.dx, it.dy, it.dz)))
            groups[key].append(it)
        # 大体积组优先
        group_list = sorted(groups.values(), key=lambda g: -(g[0].dx * g[0].dy * g[0].dz * len(g)))
        still: List[Item3D] = []
        if not bins and max_c >= 1:
            bins.append(new_bin(1))
        for g in group_list:
            # 尝试在已有柜用 EP 快速塞；组很大时对空柜做网格
            if len(g) >= 24 and len(bins) < max_c and all(len(b.placements) == 0 for b in bins[-1:]):
                b = bins[-1] if bins and not bins[-1].placements else new_bin(len(bins) + 1)
                if b not in bins:
                    bins.append(b)
                pls, unp_ids, used_w = _grid_pack_uniform(
                    g,
                    L=b.L,
                    W=b.W,
                    H=b.H,
                    max_load_kg=b.max_load_kg - float(getattr(b, "_used_weight", 0)),
                    container_no=b.container_no,
                )
                if pls and not b.placements:
                    b.placements = pls
                    b._used_weight = used_w
                    _append_pls(b, pls)
                    packed = {p.box_id for p in pls}
                    still.extend([it for it in g if it.box_id not in packed])
                    continue
            still.extend(g)
        remaining = still

    # 底层件优先，再重货，再可上二层的轻箱；同层内长件优先（利于条带齐头）
    ordered = sorted(
        remaining,
        key=lambda it: (
            0 if it.prefer_bottom else 1,
            0 if not it.stackable else 1,
            -max(it.dx, it.dy, it.dz),
            -it.weight_kg,
            -(it.dx * it.dy),
        ),
    )

    def _is_long_frame_set(its: List[Item3D]) -> bool:
        if not its or len(its) > 40:
            return False
        long_n = sum(1 for it in its if max(it.dx, it.dy, it.dz) >= 3000)
        return long_n >= max(2, int(0.6 * len(its)))

    def _commit_bin_placements(b: Bin3D, pls: List[Placement3D]) -> None:
        b.placements = list(pls)
        b.points = [(0, 0, 0)]
        for pl in pls:
            _add_points(b, pl.x, pl.y, pl.z, pl.dx, pl.dy, pl.dz)
            layout.append(
                {
                    "box_id": pl.box_id,
                    "container_no": pl.container_no,
                    "position": {"x": pl.x, "y": pl.y, "z": pl.z},
                    "size": {"dx": pl.dx, "dy": pl.dy, "dz": pl.dz},
                    "rotation": "LWH",
                    "layer": pl.layer,
                }
            )

    # 阶段 A：长铁架主导时，整柜条带贴端墙并排（避免 EP 居中碎片）
    to_ep: List[Item3D] = list(ordered)
    if _is_long_frame_set(ordered) and max_c >= 1:
        left_strip = list(ordered)
        strip_packed_ids: set = set()
        while left_strip and len(bins) < max_c:
            b = new_bin(len(bins) + 1)
            pls, left_strip, used_w = _strip_pack_floor(
                left_strip,
                L=b.L,
                W=b.W,
                H=b.H,
                max_load_kg=b.max_load_kg,
                container_no=b.container_no,
            )
            if not pls:
                break
            b._used_weight = used_w
            bins.append(b)
            _commit_bin_placements(b, pls)
            strip_packed_ids.update(p.box_id for p in pls)
            # 若本柜一条都没推进（防御）则跳出
            if used_w <= 0:
                break
        to_ep = [it for it in ordered if it.box_id not in strip_packed_ids]
        # 若条带一柜都没开成，回退全量 EP
        if not bins:
            to_ep = list(ordered)

    # 阶段 B：EP 填缝 / 非长架货 / 条带剩余
    for item in to_ep:
        placed = None
        for b in bins:
            placed = try_place(b, item)
            if placed:
                break
        if not placed and len(bins) < max_c:
            bins.append(new_bin(len(bins) + 1))
            placed = try_place(bins[-1], item)
        if not placed:
            unpacked.append(item.box_id)
        else:
            layout.append(
                {
                    "box_id": placed.box_id,
                    "container_no": placed.container_no,
                    "position": {"x": placed.x, "y": placed.y, "z": placed.z},
                    "size": {"dx": placed.dx, "dy": placed.dy, "dz": placed.dz},
                    "rotation": "LWH",
                    "layer": placed.layer,
                }
            )

    # 容积：每个铁箱/木箱/铁笼按外廓「实心长方体」体积 = dx×dy×dz（mm³）
    # 不是零件净体积，也不是镂空骨架体积
    used_vol = sum(
        float(p["size"]["dx"]) * float(p["size"]["dy"]) * float(p["size"]["dz"]) for p in layout
    )
    cont_vol = float(spec["L"]) * float(spec["W"]) * float(spec["H"])
    total_w = sum(it.weight_kg for it in items if it.box_id not in unpacked)
    used_bins = len(bins) if bins else 0
    denom_vol = cont_vol * max(used_bins, 1)
    space_util = min(used_vol / denom_vol, 1.0) if denom_vol else 0.0
    weight_util = min(total_w / (spec["max_load_kg"] * max(used_bins, 1)), 9.99)

    # 分柜指标 + 底面积利用率（更贴近“好不好放”）
    per_container = []
    for b in bins:
        bvol = sum(float(p.dx) * float(p.dy) * float(p.dz) for p in b.placements)
        floor = sum(float(p.dx) * float(p.dy) for p in b.placements if p.z == 0)
        per_container.append(
            {
                "container_no": b.container_no,
                "volume_utilization": round(min(bvol / cont_vol, 1.0), 4) if cont_vol else 0,
                "floor_utilization": round(
                    min(floor / (spec["L"] * spec["W"]), 1.0), 4
                )
                if spec["L"] and spec["W"]
                else 0,
                "boxes": len(b.placements),
                "load_kg": round(float(getattr(b, "_used_weight", 0)), 1),
                "solid_volume_m3": round(bvol / 1e9, 4),
            }
        )
    # 主指标：若只有一柜装不下才开多柜，展示「最满一柜」与「平均」
    best_vol = max((c["volume_utilization"] for c in per_container), default=space_util)
    avg_floor = (
        sum(c["floor_utilization"] for c in per_container) / len(per_container)
        if per_container
        else 0
    )

    can_fit = len(unpacked) == 0 and len(layout) > 0
    message = "可以顺利装下" if can_fit else f"未完全装入: {', '.join(unpacked[:20])}" + (
        f"…共{len(unpacked)}件" if len(unpacked) > 20 else ""
    )
    cargo_m3 = used_vol / 1e9
    cont_m3 = cont_vol / 1e9
    note = (
        f"摆柜几何容积率=Σ(箱外廓AABB)÷柜内几何容积"
        f"（已装 {cargo_m3:.3f} m³ / 单柜 {cont_m3:.3f} m³ ×{max(used_bins,1)}）；"
        f"最满柜 {best_vol:.0%}，底面积均 {avg_floor:.0%}。"
        f"此指标用于已成箱3D摆位，不等于材料估柜体积；"
        f"估柜请用 volume_estimate.pack_effective（件体积×货种膨胀≤1.8）。"
        f"钢结构常重量先满、此外廓容积率偏低属正常。"
    )

    return {
        "container_type": ctype,
        "containers_used": used_bins,
        "space_utilization": round(space_util, 4),
        "weight_utilization": round(weight_util, 4),
        "space_utilization_best_container": round(best_vol, 4),
        "floor_utilization_avg": round(avg_floor, 4),
        "per_container": per_container,
        "metrics_note": note,
        "volume_basis": "solid_outer_aabb",
        "volume_basis_note": "摆柜几何用外廓；材料估柜用 pack_effective，勿混用",
        "cargo_solid_volume_mm3": round(used_vol, 1),
        "cargo_solid_volume_m3": round(cargo_m3, 4),
        "container_inner_volume_m3": round(cont_m3, 4),
        "can_fit": can_fit,
        "layout": layout,
        "unpacked_box_ids": unpacked,
        "message": message,
        "engine": "python-laff-3d",
    }


def pack_boxes_api(
    boxes: Sequence[Dict[str, Any]],
    *,
    container_type: str = "40HQ",
    max_containers: int = 1,
    priority_order: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """从 api-spec boxes[] 装载。"""
    items: List[Item3D] = []
    for b in boxes:
        outer = b.get("outer_size_mm") or {}
        special = b.get("special_attributes") or []
        L = int(round(float(outer.get("length") or 1)))
        W = int(round(float(outer.get("width") or 1)))
        H = int(round(float(outer.get("height") or 1)))
        btype = str(b.get("box_type") or "")
        # 超长/内容物超长：不任意 6 向转；铁架/笼默认禁止竖放
        longish = (
            "超长" in special
            or "内容物超长" in special
            or L >= 4000
            or float(b.get("content_max_length_mm") or 0) >= 4000
        )
        frameish = any(k in btype for k in ("铁架", "铁笼", "框", "木箱"))
        if b.get("allowRotate") is False:
            allow_rotate = False
            no_tip = True
        else:
            no_tip = frameish or longish or L >= 2000
            allow_rotate = True
        stackable = bool(b.get("stackable"))
        if "stackable" not in b:
            stackable = H <= 1300 and not longish
        prefer_bottom = bool(b.get("prefer_bottom")) or longish or float(b.get("gross_weight_kg") or 0) >= 800
        items.append(
            Item3D(
                box_id=str(b.get("box_id") or ""),
                dx=max(L, 1),
                dy=max(W, 1),
                dz=max(H, 1),
                weight_kg=float(b.get("gross_weight_kg") or 0),
                allow_rotate=allow_rotate,
                no_tip=no_tip,
                stackable=stackable and not prefer_bottom,
                prefer_bottom=prefer_bottom,
            )
        )

    if priority_order:
        order = {bid: i for i, bid in enumerate(priority_order)}
        items.sort(key=lambda it: order.get(it.box_id, 999))

    return pack_items(items, container_type=container_type, max_containers=max_containers)
