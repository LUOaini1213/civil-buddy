"""Bounded planar NURBS conversion using rational Bezier convex hulls.

Positive rational weights keep each span inside its control hull. Subdivision
stops only when the entire hull lies in a tolerance capsule around the chord;
testing a midpoint alone would miss inflections and loops.
"""
from __future__ import annotations

import math


def read_spline(entity, transform):
    from .geometry import CAD3DError, MAX_ENTITY_VERTICES, _checkpoint, _finite, _transform_point, _xy
    if len(entity.control_points) > MAX_ENTITY_VERTICES:
        raise CAD3DError("SPLINE 控制点数量超过预算。")
    controls = list(entity.control_points)
    if not controls:
        raise CAD3DError("SPLINE 仅含拟合点，没有可验证的控制点与节点定义；请在 CAD 中转换为明确的 NURBS 控制点曲线。")
    degree = entity.dxf.degree
    if not isinstance(degree, int) or not 1 <= degree <= 5:
        raise CAD3DError("SPLINE 仅支持 1–5 次控制点曲线。")
    if len(controls) > MAX_ENTITY_VERTICES or len(controls) <= degree:
        raise CAD3DError("SPLINE 控制点数量无效或超过预算。")
    if (any(len(point) != 3 or _finite(float(point[2]), "SPLINE Z") != 0 for point in controls)
            or tuple(entity.dxf.get("extrusion", (0, 0, 1))) != (0, 0, 1)):
        raise CAD3DError("SPLINE 必须完全位于世界坐标 XY 平面 Z=0；未自动投影。")
    points = [_transform_point(_xy(point), transform) for point in controls]
    if len(entity.weights) not in (0, len(points)):
        raise CAD3DError("SPLINE 权重数量与控制点不符。")
    weights = list(entity.weights) or [1.0] * len(points)
    if len(weights) != len(points):
        raise CAD3DError("SPLINE 权重数量与控制点不符。")
    weights = [_finite(float(value), "SPLINE 权重", positive=True) for value in weights]
    largest = max(weights)
    weights = [value / largest for value in weights]
    if min(weights) < 1e-6:
        raise CAD3DError("SPLINE 权重动态范围过大，无法可靠验证离散误差。")
    if len(entity.knots) != len(points) + degree + 1:
        raise CAD3DError("SPLINE 节点数量与控制点及次数不符。")
    knots = [_finite(float(value), "SPLINE 节点") for value in entity.knots]
    if (len(knots) != len(points) + degree + 1 or any(a > b for a, b in zip(knots, knots[1:]))
            or knots[-1] <= knots[0]):
        raise CAD3DError("SPLINE 节点数量、顺序或参数范围无效。")
    if knots[:degree + 1] != [knots[0]] * (degree + 1) or knots[-degree - 1:] != [knots[-1]] * (degree + 1):
        raise CAD3DError("暂不支持未夹持的周期 SPLINE；请转换为端点夹持的等价 NURBS 曲线。")
    span = knots[-1] - knots[0]
    if not math.isfinite(span):
        raise CAD3DError("SPLINE 节点范围超出数值精度。")
    normalized_knots = [(value - knots[0]) / span for value in knots]
    if any(a != b and x == y for a, b, x, y in zip(knots, knots[1:], normalized_knots, normalized_knots[1:])):
        raise CAD3DError("SPLINE 节点间距小于可可靠表示的数值精度。")
    knots = normalized_knots
    interior = sorted(set(knots[degree + 1:-degree - 1]))
    if any(knots.count(value) > degree or value <= 0 or value >= 1 for value in interior):
        raise CAD3DError("SPLINE 内部节点重复导致曲线不连续。")
    # Insert each interior knot up to degree multiplicity in homogeneous space.
    # This preserves the NURBS, including positive rational weights.
    homogeneous = [[x * w, y * w, w] for (x, y), w in zip(points, weights)]
    for value in interior:
        for _ in range(degree - knots.count(value)):
            _checkpoint()
            if len(homogeneous) >= MAX_ENTITY_VERTICES:
                raise CAD3DError("SPLINE 节点细化超过控制点预算。")
            last = len(homogeneous) - 1
            index = max(i for i in range(last + 1) if knots[i] <= value)
            multiplicity = knots.count(value)
            updated = [None] * (len(homogeneous) + 1)
            for i in range(index - degree + 1):
                updated[i] = homogeneous[i]
            for i in range(index - multiplicity, last + 1):
                updated[i + 1] = homogeneous[i]
            for i in range(index - degree + 1, index - multiplicity + 1):
                alpha = (value - knots[i]) / (knots[i + degree] - knots[i])
                updated[i] = [(1 - alpha) * a + alpha * b
                              for a, b in zip(homogeneous[i - 1], homogeneous[i])]
            homogeneous = updated
            knots.insert(index + 1, value)
    if (len(homogeneous) - 1) % degree:
        raise CAD3DError("SPLINE 无法精确分解为连续 Bezier 段。")
    spans = []
    for index in range(0, len(homogeneous) - 1, degree):
        controls = [[value[0] / value[2], value[1] / value[2], value[2]]
                    for value in homogeneous[index:index + degree + 1]]
        spans.append(controls)
    first, last = points[0], points[-1]
    if entity.closed and first != last:
        raise CAD3DError("SPLINE 声明闭合但端点不重合；未自动补线。")
    return {"kind": "spline", "start": first, "end": last, "bezier_spans": spans,
            "error_method": "positive-weight rational Bezier convex-hull bound"}


def sample_spline(segment, tolerance, *, return_hulls=False):
    from .geometry import CAD3DError, MAX_ENTITY_VERTICES, _checkpoint, _xy
    output, maximum = [], 0.0
    hulls = []
    for span in segment["bezier_spans"]:
        # Reserve roundoff for knot refinement, de Casteljau and projection.
        magnitude = max(1.0, *(abs(value) for p in span for value in p[:2]))
        numerical = 512 * len(span) * math.ulp(magnitude) / min(p[2] for p in span)
        if numerical >= tolerance:
            raise CAD3DError("SPLINE 坐标或权重精度不足以保证所选弦高误差；请移近原点或放宽误差。")
        pending = [([[x * w, y * w, w] for x, y, w in span], 0)]
        while pending:
            _checkpoint()
            controls, depth = pending.pop()
            projected = [_xy([p[0] / p[2], p[1] / p[2]]) for p in controls]
            first, last = projected[0], projected[-1]
            dx, dy = last[0] - first[0], last[1] - first[1]
            length2 = dx * dx + dy * dy
            def distance(point):
                t = max(0.0, min(1.0, ((point[0] - first[0]) * dx + (point[1] - first[1]) * dy) / length2)) if length2 else 0
                return math.hypot(point[0] - first[0] - t * dx, point[1] - first[1] - t * dy)
            error = max(map(distance, projected)) + numerical
            projections = [(point[0] - first[0]) * dx + (point[1] - first[1]) * dy for point in projected]
            monotone = length2 > 0 and all(a <= b for a, b in zip(projections, projections[1:]))
            if error <= tolerance and monotone:
                if not output:
                    output.append(first)
                output.append(last)
                hulls.append((projected, numerical))
                maximum = max(maximum, error)
                if len(output) > MAX_ENTITY_VERTICES:
                    raise CAD3DError("SPLINE 在指定误差下超过轮廓顶点预算。")
                continue
            if depth >= 32 or len(output) + len(pending) >= MAX_ENTITY_VERTICES:
                raise CAD3DError("SPLINE 在指定误差下超过细分深度或顶点预算。")
            levels, left, right = controls, [controls[0]], [controls[-1]]
            while len(levels) > 1:
                levels = [[(a + b) / 2 for a, b in zip(p, q)] for p, q in zip(levels, levels[1:])]
                left.append(levels[0])
                right.append(levels[-1])
            pending.extend([(list(reversed(right)), depth + 1), (left, depth + 1)])
    if output:
        output[0], output[-1] = segment["start"], segment["end"]
    _check_adjacent_hulls(hulls, segment["start"] == segment["end"])
    return (output, maximum, hulls) if return_hulls else (output, maximum)


def _check_adjacent_hulls(spans, closed):
    """Adjacent chords meet by design; their actual curve hulls may still cross."""
    from .geometry import CAD3DError, _checkpoint, _dependency
    geometry = _dependency("shapely.geometry")
    if len(spans) < 2:
        return
    origin = spans[0][0][0]
    hulls = [geometry.MultiPoint([(p[0] - origin[0], p[1] - origin[1]) for p in points]).convex_hull
             for points, _ in spans]
    pairs = [(i - 1, i) for i in range(1, len(spans))]
    if closed:
        pairs.append((len(spans) - 1, 0))
    for left, right in pairs:
        _checkpoint()
        overlap = hulls[left].intersection(hulls[right])
        shared = spans[right][0][0]
        roundoff = max(spans[left][1], spans[right][1]) * 2
        endpoint = geometry.Point(shared[0] - origin[0], shared[1] - origin[1]).buffer(roundoff)
        if not overlap.difference(endpoint).is_empty:
            raise CAD3DError("SPLINE 相邻曲线段的控制凸包在共同端点之外重叠，无法排除细小自交；请减小弦高误差。")


def check_topology(points, error):
    """Reject non-neighbour chords whose error capsules can change topology."""
    from .geometry import CAD3DError, _checkpoint, _dependency
    geometry = _dependency("shapely.geometry")
    tree_module = _dependency("shapely.strtree")
    origin = points[0]
    local = [[p[0] - origin[0], p[1] - origin[1]] for p in points]
    chords = [geometry.LineString([a, b]) for a, b in zip(local, [*local[1:], local[0]])]
    tree = tree_module.STRtree(chords)
    for i, chord in enumerate(chords):
        _checkpoint()
        low_x, low_y, high_x, high_y = chord.bounds
        query = geometry.box(low_x - error * 2, low_y - error * 2, high_x + error * 2, high_y + error * 2)
        for raw_index in tree.query(query):
            j = int(raw_index)
            if j <= i or j == i + 1 or (i == 0 and j == len(chords) - 1):
                continue
            if chord.distance(chords[j]) <= error * 2:
                raise CAD3DError("SPLINE 非相邻轮廓段的距离小于离散误差范围，无法排除自交或细小孔槽塌缩；请减小弦高误差。")
