"""Strict DXF solid boundaries -> parameterized meshes, without model-generated code.

Closed zero-width 2D polylines, circles and closed LINE/ARC/SPLINE chains on XY are
accepted, including bounded planar uniform INSERT instances. A selected layer
is atomic: an invalid/unsupported entity or touching
boundaries blocks that layer, so an unhandled inner boundary cannot become solid.
Nested rings use even/odd containment; no repair, snapping or boolean union occurs.
All public results are JSON serializable. This module never writes files.
"""

from __future__ import annotations

import copy
import hashlib
import importlib
import io
import math
from collections import defaultdict
from typing import Any

MAX_DXF_BYTES = 10 * 1024 * 1024
MAX_ENTITIES = 2000
MAX_DATABASE_ENTITIES = 20000
MAX_VERTICES = 30000
MAX_ENTITY_VERTICES = 4096
MAX_LAYER_RINGS = 512
MAX_MODEL_VERTICES = 120000
MAX_COORDINATE = 1e12
MAX_EXTENT_M = 1e6
DEFAULT_CURVE_TOLERANCE_MM = 0.1
MIN_CURVE_TOLERANCE_MM = 0.001
MAX_CURVE_TOLERANCE_MM = 10.0
MAX_INSERT_DEPTH = 8
MAX_JOIN_ROUNDOFF_M = 1e-9
FLOAT32_REL_TOL = 1e-5
FLOAT32_ABS_TOL_M = 1e-7

UNIT_FACTORS = {"mm": 0.001, "cm": 0.01, "m": 1.0, "in": 0.0254, "ft": 0.3048}
DXF_UNITS = {0: ("unitless", None), 1: ("in", 0.0254), 2: ("ft", 0.3048),
             4: ("mm", 0.001), 5: ("cm", 0.01), 6: ("m", 1.0)}
ROLE_COLORS = {"wall": [100, 151, 224, 255], "column": [246, 180, 86, 255],
               "slab": [142, 162, 180, 255], "section": [78, 192, 170, 255]}


class CAD3DError(ValueError):
    """An explainable input, dependency or geometry failure."""


class _ExpansionLimit(CAD3DError):
    """Abort the whole document so a truncated block cannot hide a hole."""


def _dependency(name: str):
    try:
        return importlib.import_module(name)
    except ImportError as exc:
        raise CAD3DError(
            f"CAD 三维建模依赖 {name!r} 不可用，请安装可选依赖："
            "pip install ezdxf shapely trimesh mapbox-earcut"
        ) from exc


def _finite(value: Any, label: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CAD3DError(f"{label} 必须是有限数值。")
    try:
        value = float(value)
    except OverflowError as exc:
        raise CAD3DError(f"{label} 超出有限数值范围。") from exc
    if not math.isfinite(value) or (positive and value <= 0):
        raise CAD3DError(f"{label} 必须是{'大于零的' if positive else ''}有限数值。")
    return value


def _bounds(points: list[list[float]], dimensions: int) -> dict | None:
    if not points:
        return None
    return {"min": [min(p[i] for p in points) for i in range(dimensions)],
            "max": [max(p[i] for p in points) for i in range(dimensions)]}


def _suggest_role(name: str) -> str:
    upper = name.upper()
    for role, words in (("wall", ("WALL", "墙")), ("column", ("COLUMN", "COL", "柱")),
                        ("slab", ("SLAB", "FLOOR", "板")),
                        ("section", ("SECTION", "PROFILE", "截面", "型材"))):
        if any(word in upper for word in words):
            return role
    return "ignore"


def _polygon(points: list[list[float]]):
    geometry = _dependency("shapely.geometry")
    validation = _dependency("shapely.validation")
    if len(points) < 3 or len({tuple(p) for p in points}) < 3:
        raise CAD3DError("实体边界至少需要三个不同的顶点。")
    polygon = geometry.Polygon(points)
    if not polygon.is_valid:
        raise CAD3DError("轮廓无效（可能自交）：" + validation.explain_validity(polygon))
    if polygon.is_empty or polygon.area <= 0:
        raise CAD3DError("轮廓面积必须大于零。")
    return polygon


def _checkpoint() -> None:
    from packing_assistant.runtime.cancel import check
    check()


def _xy(value: Any) -> list[float]:
    point = [float(value[0]), float(value[1])]
    if any(not math.isfinite(x) or abs(x) > MAX_COORDINATE for x in point):
        raise CAD3DError("坐标不是有限数值或超出支持范围。")
    return point


def _sincos(angle: float) -> tuple[float, float]:
    # Exact quadrant endpoints avoid creating artificial LINE/ARC gaps.
    quadrant = round(angle / (math.pi / 2))
    if abs(angle - quadrant * math.pi / 2) <= 1e-14:
        return ((1.0, 0.0), (0.0, 1.0), (-1.0, 0.0), (0.0, -1.0))[quadrant % 4]
    return math.cos(angle), math.sin(angle)


def _arc(center: list[float], radius: float, start: float, sweep: float,
         first: list[float] | None = None, last: list[float] | None = None) -> dict:
    radius = _finite(radius, "圆弧半径", positive=True)
    if radius > MAX_COORDINATE or not math.isfinite(start) or not math.isfinite(sweep) or sweep == 0:
        raise CAD3DError("圆弧角度或半径无效。")
    def point(angle):
        cosine, sine = _sincos(angle)
        return _xy([center[0] + radius * cosine, center[1] + radius * sine])
    return {"kind": "arc", "center": center, "radius": radius, "start_angle": start,
            "sweep_angle": sweep, "start": first or point(start), "end": last or point(start + sweep)}


def _line(first: list[float], last: list[float]) -> dict:
    if first == last:
        raise CAD3DError("零长度线段不能组成实体边界。")
    return {"kind": "line", "start": first, "end": last}


def _read_polyline(entity: Any) -> tuple[list[list[float]], str | None, list[dict]]:
    """Read unmodified XY vertices and analytic bulges; never repair open rings."""
    kind = entity.dxftype()
    if kind == "LWPOLYLINE":
        raw = list(entity.get_points("xyseb"))
        points = [_xy(p) for p in raw]
        bulges = [float(p[4]) for p in raw]
        closed = entity.closed
        fitted = False
        width = entity.dxf.get("const_width", 0) != 0 or any(p[2] != 0 or p[3] != 0 for p in raw)
        elevation = float(entity.dxf.get("elevation", 0))
        plane_bad = elevation != 0
    else:
        vertices = entity.vertices
        points = [_xy(v.dxf.location) for v in vertices]
        bulges = [float(v.dxf.get("bulge", 0)) for v in vertices]
        closed = entity.is_closed
        fitted = (bool(entity.dxf.get("flags", 0) & (2 | 4))
                  or entity.dxf.get("smooth_type", 0) != 0
                  or any(v.dxf.get("flags", 0) & (1 | 2 | 8 | 16)
                         for v in vertices))
        width = (entity.dxf.get("default_start_width", 0) != 0
                 or entity.dxf.get("default_end_width", 0) != 0
                 or any(v.dxf.get("start_width", 0) != 0 or v.dxf.get("end_width", 0) != 0
                        for v in vertices))
        plane_bad = (not entity.is_2d_polyline or entity.dxf.elevation.z != 0
                     or any(v.dxf.location.z != 0 for v in vertices))
    if len(points) > MAX_ENTITY_VERTICES:
        raise _ExpansionLimit(f"单个实体超过 {MAX_ENTITY_VERTICES} 个顶点限制。")
    if plane_bad or tuple(entity.dxf.get("extrusion", (0, 0, 1))) != (0, 0, 1):
        return points, "仅支持世界坐标 XY 平面上 Z=0 的二维轮廓；非共面、带原图标高或倾斜轮廓未自动投影。", []
    if entity.dxf.get("thickness", 0) != 0:
        return points, "暂不支持 DXF 自带 thickness，请移除后显式填写拉伸高度。", []
    if fitted:
        return points, "暂不支持拟合曲线，未用控制框或直线代替原曲线。", []
    if width:
        return points, "带宽多段线属于线条，尚非确认的实体边界；请提供明确的内外轮廓。", []
    if not closed:
        return points, "轮廓未闭合：DXF 未设置闭合标记，未自动补线。", []
    if len(points) > 1 and points[0] == points[-1]:
        if bulges[-1]:
            raise CAD3DError("重复闭合端点带零长度 bulge 弧段。")
        points, bulges = points[:-1], bulges[:-1]
    segments = []
    for index, first in enumerate(points):
        last, bulge = points[(index + 1) % len(points)], bulges[index]
        _finite(bulge, "bulge")
        if bulge == 0:
            segments.append(_line(first, last))
        else:
            dx, dy = last[0] - first[0], last[1] - first[1]
            chord = math.hypot(dx, dy)
            if chord == 0:
                raise CAD3DError("零长度 bulge 弧段无效。")
            offset = (1 / bulge - bulge) / 4
            center = _xy([(first[0] + last[0]) / 2 - dy * offset,
                          (first[1] + last[1]) / 2 + dx * offset])
            radius = chord * (abs(bulge) + 1 / abs(bulge)) / 4
            segments.append(_arc(center, radius, math.atan2(first[1] - center[1], first[0] - center[0]),
                                 4 * math.atan(bulge), first, last))
    return points, None, segments


def _transform_point(point: list[float], transform: tuple) -> list[float]:
    a, b, tx, ty = transform
    return _xy([a * point[0] - b * point[1] + tx, b * point[0] + a * point[1] + ty])


def _transform_segment(segment: dict, transform: tuple) -> dict:
    result = {**segment, "start": _transform_point(segment["start"], transform),
              "end": _transform_point(segment["end"], transform)}
    if segment["kind"] == "arc":
        a, b, _, _ = transform
        result.update(center=_transform_point(segment["center"], transform),
                      radius=segment["radius"] * math.hypot(a, b),
                      start_angle=segment["start_angle"] + math.atan2(b, a))
    elif segment["kind"] == "spline":
        result["bezier_spans"] = [[[*_transform_point(p[:2], transform), p[2]] for p in span]
                                  for span in segment["bezier_spans"]]
    return result


def _sample_segments(segments: list[dict], tolerance_units: float) -> tuple[list[list[float]], float]:
    points, max_error = [], 0.0
    has_spline = any(segment["kind"] == "spline" for segment in segments)
    topology_hulls = []
    for segment in segments:
        _checkpoint()
        if segment["kind"] == "line":
            sampled = [segment["start"], segment["end"]]
            if has_spline:
                numerical = 128 * max(math.ulp(max(abs(value), 1.0)) for point in sampled for value in point)
                topology_hulls.append((sampled, numerical))
        elif segment["kind"] == "spline":
            from .splines import sample_spline
            sampled, error, hulls = sample_spline(segment, tolerance_units, return_hulls=True)
            topology_hulls.extend(hulls)
            max_error = max(max_error, error)
        else:
            radius, sweep = segment["radius"], segment["sweep_angle"]
            # Stable for tiny tolerances: sagitta = 2r sin(step/4)^2.
            step = min(math.pi / 2, 4 * math.asin(math.sqrt(min(1, tolerance_units / (2 * radius)))))
            count = max(1, math.ceil(abs(sweep) / step)) if step else MAX_ENTITY_VERTICES + 1
            if abs(abs(sweep) - 2 * math.pi) < 1e-12:
                count = 4 * math.ceil(count / 4)
            if count + len(points) > MAX_ENTITY_VERTICES:
                raise CAD3DError(f"曲线在指定弦高误差下超过 {MAX_ENTITY_VERTICES} 个轮廓顶点；请显式调整误差或拆分图层。")
            sampled = [segment["start"]]
            for index in range(1, count):
                cosine, sine = _sincos(segment["start_angle"] + sweep * index / count)
                sampled.append(_xy([segment["center"][0] + radius * cosine,
                                    segment["center"][1] + radius * sine]))
            sampled.append(segment["end"])
            if has_spline:
                # Each <=90-degree arc has an exact positive rational quadratic
                # representation. Its middle control lies at the tangents'
                # intersection, so its hull also contains the entire arc.
                delta = sweep / count
                for index, (first, last) in enumerate(zip(sampled, sampled[1:])):
                    cosine, sine = _sincos(segment["start_angle"] + (index + .5) * delta)
                    middle_radius = radius / math.cos(delta / 2)
                    middle = _xy([segment["center"][0] + middle_radius * cosine,
                                  segment["center"][1] + middle_radius * sine])
                    controls = [first, middle, last]
                    numerical = 128 * max(math.ulp(max(abs(value), 1.0)) for point in controls for value in point)
                    topology_hulls.append((controls, numerical))
            max_error = max(max_error, 2 * radius * math.sin(abs(sweep) / count / 4) ** 2)
        points.extend(sampled[:-1])
        if len(points) > MAX_ENTITY_VERTICES:
            raise CAD3DError(f"单个轮廓超过 {MAX_ENTITY_VERTICES} 个顶点限制。")
    if has_spline:
        from .splines import _check_adjacent_hulls
        # Multiple source segments are only assembled after a closed graph or
        # closed-polyline check. Their endpoints may differ by accepted ULPs.
        closed = len(segments) > 1 or segments[0]["start"] == segments[-1]["end"]
        _check_adjacent_hulls(topology_hulls, closed)
    return points, max_error


def _refresh_entities(entities: list[dict], scale: float, tolerance_mm: float) -> list[dict]:
    result = copy.deepcopy(entities)
    total = 0
    for entity in result:
        _checkpoint()
        if entity.get("geometry_source"):
            try:
                join_gap = entity["geometry_source"].get("max_join_gap_units", 0) * scale
                if join_gap > MAX_JOIN_ROUNDOFF_M:
                    raise CAD3DError("确认单位后的端点偏差超过浮点舍入边界；未自动吸附或填补缺口，请核对图纸坐标精度。")
                points, error = _sample_segments(entity["geometry_source"]["segments"], tolerance_mm / 1000 / scale)
                _polygon(points)
                if error and any(segment["kind"] == "spline" for segment in entity["geometry_source"]["segments"]):
                    from .splines import check_topology
                    check_topology(points, error)
                entity.update(points=points, status="ready", reason="闭合轮廓；实体含义与单位仍需确认。",
                              curve_max_error_mm=error * scale * 1000)
            except CAD3DError as exc:
                entity.update(points=[], status="invalid", reason=str(exc))
        elif entity.get("edge_source"):
            try:
                points, error = _sample_segments([entity["edge_source"]], tolerance_mm / 1000 / scale)
                entity.update(points=[*points, entity["edge_source"]["end"]], curve_max_error_mm=error * scale * 1000)
            except CAD3DError as exc:
                entity.update(points=[], status="invalid", reason=str(exc))
        total += len(entity["points"])
        if total > MAX_VERTICES:
            raise CAD3DError(f"DXF 超过 {MAX_VERTICES} 个顶点限制。")
    return result


def _join_edges(items: list[dict], scale: float = 1.0) -> list[dict]:
    """Join only degree-two closed graphs; real LINE gaps are never snapped."""
    edges = [item for item in items if item.get("_edge")]
    if not edges:
        return items
    nodes, endpoints = [], []
    for item in edges:
        _checkpoint()
        segment = item["_edge"]
        pair = []
        for point in (segment["start"], segment["end"]):
            match = None
            for index, (other, curved) in enumerate(nodes):
                if index % 64 == 0:
                    _checkpoint()
                # A trigonometric endpoint can differ by a few ULPs. This is
                # numerical equality, independent of the user curve tolerance.
                tolerance = min(MAX_JOIN_ROUNDOFF_M / scale,
                                16 * max(math.ulp(max(abs(x), 1.0)) for x in (*point, *other)))
                if point == other or ((curved or segment["kind"] in {"arc", "spline"})
                                      and math.dist(point, other) <= tolerance):
                    match = index
                    break
            if match is None:
                match = len(nodes)
                nodes.append((point, segment["kind"] in {"arc", "spline"}))
            pair.append(match)
        endpoints.append(pair)
    adjacency: dict[int, list[int]] = defaultdict(list)
    for index, pair in enumerate(endpoints):
        for node in pair:
            adjacency[node].append(index)
    pending, assembled = set(range(len(edges))), []
    while pending:
        _checkpoint()
        seed, component, stack = min(pending), set(), [min(pending)]
        while stack:
            edge_index = stack.pop()
            if edge_index in component:
                continue
            component.add(edge_index)
            stack.extend(neighbor for node in endpoints[edge_index] for neighbor in adjacency[node]
                         if neighbor not in component)
        pending -= component
        if any(len(adjacency[node]) != 2 for edge_index in component for node in endpoints[edge_index]):
            bad_nodes = sorted({node for index in component for node in endpoints[index] if len(adjacency[node]) != 2})
            related = [edges[index]["id"] for index in sorted(component)]
            for index in sorted(component):
                item = edges[index]
                item.update(status="invalid", reason="LINE/ARC/SPLINE 轮廓未闭合或端点分支；未自动补线、吸附或选择分支。",
                            edge_source=copy.deepcopy(item["_edge"]), related_entity_ids=related,
                            diagnostic_points=[nodes[node][0] for node in bad_nodes])
                item.pop("_edge", None)
                assembled.append(item)
            continue
        current_node = endpoints[seed][0]
        remaining, ordered = set(component), []
        while remaining:
            index = min(i for i in adjacency[current_node] if i in remaining)
            remaining.remove(index)
            segment = copy.deepcopy(edges[index]["_edge"])
            if endpoints[index][0] != current_node:
                segment["start"], segment["end"] = segment["end"], segment["start"]
                if segment["kind"] == "arc":
                    segment["start_angle"] += segment["sweep_angle"]
                    segment["sweep_angle"] *= -1
                elif segment["kind"] == "spline":
                    segment["bezier_spans"] = [list(reversed(span)) for span in reversed(segment["bezier_spans"])]
                current_node = endpoints[index][0]
            else:
                current_node = endpoints[index][1]
            ordered.append(segment)
        # Keep the first original handle as stable contour identity; every
        # original edge remains available in provenance and the final report.
        sources = [edges[index] for index in sorted(component)]
        item = {key: copy.deepcopy(value) for key, value in sources[0].items() if key != "_edge"}
        join_gap = max(math.dist(first["end"], second["start"])
                       for first, second in zip(ordered, [*ordered[1:], ordered[0]]))
        item.update(type="LINE_ARC_LOOP", points=[], geometry_source={"segments": ordered, "max_join_gap_units": join_gap},
                    source_entity_ids=[source["id"] for source in sources],
                    source_entities=[metadata for source in sources for metadata in source["source_entities"]])
        assembled.append(item)
    by_id = {item["id"]: item for item in assembled}
    return [by_id[item["id"]] if item["id"] in by_id else item
            for item in items if not item.get("_edge") or item["id"] in by_id]


def inspect_dxf(data: bytes, filename: str, source_filter: dict | None = None) -> dict:
    """Read an ASCII DXF modelspace without altering geometry or inferring units."""
    if not isinstance(data, bytes) or not data:
        raise CAD3DError("请上传非空 DXF 文件。")
    byte_limit = MAX_DXF_BYTES
    if source_filter is not None:
        from .imports import MAX_SCAN_BYTES
        byte_limit = MAX_SCAN_BYTES
    if len(data) > byte_limit:
        raise CAD3DError(f"DXF 超过 {byte_limit // 1024 // 1024} MiB 大小限制。")
    if not isinstance(filename, str) or not filename.lower().endswith(".dxf"):
        raise CAD3DError("当前预览仅接受 DXF。请将 DWG 单独转换为 DXF 后上传。")
    if data.startswith(b"AutoCAD Binary DXF"):
        raise CAD3DError("暂不支持二进制 DXF，请另存为 ASCII DXF。")
    ezdxf = _dependency("ezdxf")
    _dependency("shapely.geometry")
    try:
        from .imports import _CheckedStream
        probe = _CheckedStream(data.decode("latin1"), newline=None)
        encoding = _dependency("ezdxf.filemanagement").dxf_stream_info(probe).encoding
        drawing = ezdxf.read(_CheckedStream(data.decode(encoding, errors="strict"), newline=None))
    except Exception as exc:
        from packing_assistant.runtime.cancel import RunCancelled
        if isinstance(exc, RunCancelled):
            raise
        raise CAD3DError(f"DXF 读取失败，未自动修复图纸：{type(exc).__name__}: {exc}") from exc
    space = drawing.modelspace()
    filter_audit, filtered_ids = None, None
    if source_filter is not None:
        from .imports import MAX_SCAN_DATABASE_ENTITIES, filter_modelspace
        if len(drawing.entitydb) > MAX_SCAN_DATABASE_ENTITIES:
            raise CAD3DError("DXF 数据库超过分阶段导入预算。")
        space, source_filter, filter_audit = filter_modelspace(drawing, source_filter)
        filtered_ids = set(filter_audit["selected_entity_ids"])
        if filter_audit.get("excluded_crossing", 0) > len(filter_audit.get("excluded", [])):
            raise CAD3DError("选择范围跨越过多实体，无法完整列出边界诊断；请收窄图层或扩大范围以包含完整轮廓。")
    if source_filter is None and len(drawing.entitydb) > MAX_DATABASE_ENTITIES:
        raise CAD3DError(f"DXF 数据库超过 {MAX_DATABASE_ENTITIES} 个实体限制（含块和布局）。")
    if len(space) > MAX_ENTITIES:
        raise CAD3DError(f"DXF 模型空间超过 {MAX_ENTITIES} 个实体限制。")
    units_code = int(drawing.header.get("$INSUNITS", 0))
    name, factor = DXF_UNITS.get(units_code, ("unsupported", None))
    entities = []
    counts: dict[str, int] = defaultdict(int)
    visited = 0

    def source_selected(logical_id):
        if filtered_ids is None:
            return True
        parts = logical_id.split("/")
        return any("/".join(parts[:end]) in filtered_ids for end in range(1, len(parts) + 1))

    def block_failures(entity, insert_path, inherited_layer, reason):
        """Expose every affected descendant layer even when its INSERT fails.

        An unhandled reference on layer 0 can contain a hole explicitly on a
        selected layer. Only reporting layer 0 would silently fill that hole.
        Walk block definitions without applying the unsupported transform;
        fail-fast bounds also apply to this provenance-only traversal.
        """
        nonlocal visited
        pending = [(entity, insert_path, inherited_layer)]
        seen = set()
        while pending:
            reference, ancestors, effective_layer = pending.pop()
            block_name = str(reference.dxf.name)
            key = (block_name, effective_layer)
            if key in seen:
                continue
            seen.add(key)
            block = drawing.blocks.get(block_name)
            if block is None:
                continue
            reference_row = {"handle": str(reference.dxf.handle), "block": block_name,
                             "layer": str(reference.dxf.get("layer", "0")), "unsupported_transform": True}
            path = (*ancestors, reference_row)
            for child in block:
                _checkpoint()
                handle = str(child.dxf.handle)
                logical_id = "/".join([*[row["handle"] for row in path], handle])
                if child.dxftype() != "INSERT" and not source_selected(logical_id):
                    continue
                visited += 1
                if visited > MAX_ENTITIES:
                    raise _ExpansionLimit(f"DXF 展开后超过 {MAX_ENTITIES} 个实体限制。")
                raw_layer = str(child.dxf.get("layer", "0"))
                layer = effective_layer if raw_layer == "0" else raw_layer
                metadata = {"id": logical_id, "handle": handle, "type": child.dxftype(),
                            "layer": raw_layer, "insert_path": list(path)}
                entities.append({"id": logical_id, "layer": layer, "type": child.dxftype(),
                                 "status": "unsupported", "reason": "所属块参照未处理：" + reason,
                                 "points": [], "source_entity_ids": [logical_id], "source_entities": [metadata]})
                counts[layer] += 1
                if child.dxftype() == "INSERT":
                    pending.append((child, path, layer))

    def read(entity, transform=(1.0, 0.0, 0.0, 0.0), insert_path=(), names=(), inherited_layer="0"):
        nonlocal visited
        _checkpoint()
        kind, raw_layer = entity.dxftype(), str(entity.dxf.get("layer", "0"))
        layer = inherited_layer if insert_path and raw_layer == "0" else raw_layer
        handle = str(entity.dxf.handle)
        logical_id = "/".join([*[row["handle"] for row in insert_path], handle])
        if kind != "INSERT" and not source_selected(logical_id):
            return
        visited += 1
        if visited > MAX_ENTITIES:
            raise _ExpansionLimit(f"DXF 展开后超过 {MAX_ENTITIES} 个实体限制。")
        metadata = {"id": logical_id, "handle": handle, "type": kind, "layer": raw_layer,
                    "insert_path": list(insert_path)}
        item = {"id": logical_id, "layer": layer, "type": kind, "status": "unsupported", "reason": "",
                "points": [], "source_entity_ids": [logical_id], "source_entities": [metadata]}
        try:
            if kind == "INSERT":
                scales = [float(entity.dxf.get(key, 1)) for key in ("xscale", "yscale", "zscale")]
                insertion = entity.dxf.insert
                angle = _finite(float(entity.dxf.get("rotation", 0)), "块旋转角")
                block_name = str(entity.dxf.name)
                block = drawing.blocks.get(block_name)
                if (not all(math.isfinite(value) and value > 0 for value in scales)
                        or scales[0] != scales[1] or scales[0] != scales[2]
                        or insertion.z != 0 or tuple(entity.dxf.get("extrusion", (0, 0, 1))) != (0, 0, 1)
                        or entity.dxf.get("row_count", 1) != 1 or entity.dxf.get("column_count", 1) != 1):
                    item["reason"] = "块参照仅支持 XY 平移、平面旋转与正数统一缩放；镜像、非统一缩放、倾斜和阵列暂未建模。"
                elif block is None or not len(block) or block.block.dxf.base_point.z != 0:
                    item["reason"] = "块参照缺少内容或块基点不在 XY 平面。"
                elif block_name in names or len(insert_path) >= MAX_INSERT_DEPTH:
                    item["reason"] = f"块参照循环或超过 {MAX_INSERT_DEPTH} 层嵌套限制。"
                else:
                    cosine, sine = _sincos(math.radians(angle))
                    local_a, local_b = scales[0] * cosine, scales[0] * sine
                    base = block.block.dxf.base_point
                    local_t = _xy([insertion.x - local_a * base.x + local_b * base.y,
                                   insertion.y - local_b * base.x - local_a * base.y])
                    a, b, _, _ = transform
                    tx, ty = _transform_point(local_t, transform)
                    composed = (a * local_a - b * local_b, b * local_a + a * local_b, tx, ty)
                    row = {"handle": handle, "block": block_name, "layer": raw_layer,
                           "transform_xy": list(composed)}
                    for child in block:
                        read(child, composed, (*insert_path, row), (*names, block_name), layer)
                    return
            elif kind in ("LWPOLYLINE", "POLYLINE"):
                points, reason, segments = _read_polyline(entity)
                item["points"] = [_transform_point(point, transform) for point in points]
                if reason:
                    item["reason"] = reason
                    if reason.startswith("轮廓未闭合"):
                        item["status"] = "invalid"
                elif any(segment["kind"] == "arc" for segment in segments):
                    item["geometry_source"] = {"segments": [_transform_segment(s, transform) for s in segments]}
                else:
                    _polygon(item["points"])
                    item.update(status="ready", reason="闭合直线轮廓；实体含义与单位仍需确认。")
            elif kind == "SPLINE":
                from .splines import read_spline
                segment = read_spline(entity, transform)
                if segment["start"] == segment["end"]:
                    item["geometry_source"] = {"segments": [segment]}
                else:
                    item.update(points=[segment["start"], segment["end"]], _edge=segment)
            elif kind in ("LINE", "ARC", "CIRCLE"):
                plane_values = (entity.dxf.start.z, entity.dxf.end.z) if kind == "LINE" else (entity.dxf.center.z,)
                if (any(value != 0 for value in plane_values)
                        or tuple(entity.dxf.get("extrusion", (0, 0, 1))) != (0, 0, 1)
                        or entity.dxf.get("thickness", 0) != 0):
                    item["reason"] = "仅支持 XY 平面 Z=0 且无 thickness 的 LINE/ARC/CIRCLE；未自动投影。"
                else:
                    if kind == "LINE":
                        segment = _line(_xy(entity.dxf.start), _xy(entity.dxf.end))
                    else:
                        start = float(entity.dxf.start_angle) if kind == "ARC" else 0
                        sweep = (float(entity.dxf.end_angle) - start) % 360 if kind == "ARC" else 360
                        segment = _arc(_xy(entity.dxf.center), float(entity.dxf.radius),
                                       math.radians(start), math.radians(sweep))
                    segment = _transform_segment(segment, transform)
                    if kind == "CIRCLE":
                        segment["end"] = segment["start"]
                        item["geometry_source"] = {"segments": [segment]}
                    else:
                        item.update(points=[segment["start"], segment["end"]], _edge=segment)
            else:
                item["reason"] = f"{kind} 不是支持的闭合实体边界，暂未建模。"
        except _ExpansionLimit:
            raise
        except (ValueError, TypeError, LookupError, OverflowError, ZeroDivisionError) as exc:
            item.update(status="invalid", reason=str(exc), points=[])
        counts[layer] += 1
        entities.append(item)
        if kind == "INSERT":
            # Include descendant failures before layer selection; the container
            # layer alone says nothing about explicit child layers.
            block_failures(entity, insert_path, layer, item["reason"])

    for entity in space:
        read(entity)
    if filter_audit:
        for excluded in filter_audit.get("excluded", []):
            _checkpoint()
            low, high = excluded["bounds"]["min"], excluded["bounds"]["max"]
            points = [low, [high[0], low[1]], high, [low[0], high[1]], low]
            identifier = excluded["id"]
            entities.append({"id": identifier, "layer": excluded["layer"], "type": excluded["type"],
                             "status": "invalid", "reason": "实体跨越导入选区边界，无法确认完整材料区；未自动裁切，请扩大范围或明确排除参考图框。",
                             "points": points, "display_only": True, "source_filter_excluded": True,
                             "source_entity_ids": [identifier],
                             "source_entities": [{"id": identifier, "handle": identifier.split("/")[-1],
                                                  "type": excluded["type"], "layer": excluded["layer"]}]})
            counts[excluded["layer"]] += 1
        if len(entities) > MAX_ENTITIES:
            raise CAD3DError("选中实体和跨界诊断总量超过严检预算，请缩小范围。")
    # Joining never crosses a layer. Block instances share effective layers,
    # but source identities retain the complete instance path.
    by_layer: dict[str, list[dict]] = defaultdict(list)
    for entity in entities:
        by_layer[entity["layer"]].append(entity)
    joined = {item["id"]: item for members in by_layer.values() for item in _join_edges(members, factor or 1.0)}
    entities = [joined[item["id"]] for item in entities if item["id"] in joined]
    entities = _refresh_entities(entities, factor or 0.001, DEFAULT_CURVE_TOLERANCE_MM)
    all_points = [point for item in entities for point in item["points"]]
    from .dimensions import extract_dimensions
    result = {"schema_version": 1, "filename": filename, "sha256": hashlib.sha256(data).hexdigest(),
            "units": {"code": units_code, "name": name, "meters_per_unit": factor},
            "layers": [{"name": name, "suggested_role": _suggest_role(name), "entity_count": count}
                       for name, count in sorted(counts.items())],
            "entities": entities, "bounds": _bounds(all_points, 2),
            "dimensions": extract_dimensions(drawing, space if source_filter is not None else None),
            "curve_tolerance_mm": DEFAULT_CURVE_TOLERANCE_MM,
            "preview_unit": name if factor else "mm",
            "warnings": ["仅检查模型空间，图纸空间布局暂未建模。",
                         "图层建议尚未确认；仅可拉伸用户确认的实体边界。",
                         "初次曲线预览按 DXF 单位提示离散；单位未知时临时按毫米显示，建模按用户确认单位重新离散。",
                         "选中实体若含不支持或无效边界，相关图层暂停建模，以免填实尚未处理的孔洞。"]}
    if source_filter is not None:
        result.update(source_filter=source_filter, source_filter_audit=filter_audit)
    return result


def _checked_config(document: dict, config: dict, *, preview: bool = False) -> dict:
    if not isinstance(config, dict):
        raise CAD3DError("建模配置必须是 JSON 对象。")
    cfg = copy.deepcopy(config)
    if set(cfg) - {"mode", "unit", "confirmed_solid", "layers", "parameters", "overrides", "curve_tolerance_mm", "selection", "dimension_bindings"}:
        raise CAD3DError("建模配置包含未知设置。")
    tolerance = _finite(cfg.setdefault("curve_tolerance_mm", DEFAULT_CURVE_TOLERANCE_MM), "弦高误差", positive=True)
    if not MIN_CURVE_TOLERANCE_MM <= tolerance <= MAX_CURVE_TOLERANCE_MM:
        raise CAD3DError(f"弦高误差必须在 {MIN_CURVE_TOLERANCE_MM:g}–{MAX_CURVE_TOLERANCE_MM:g} mm 之间。")
    if not isinstance(cfg.get("mode"), str) or cfg["mode"] not in ("building", "section"):
        raise CAD3DError("请选择建筑 building 或截面 section 模式。")
    if not isinstance(cfg.get("unit"), str) or cfg["unit"] not in UNIT_FACTORS:
        raise CAD3DError("请明确确认图纸单位：mm、cm、m、in 或 ft。")
    if not preview and cfg.get("confirmed_solid") is not True:
        raise CAD3DError("请确认所选轮廓代表实体材料区域；房间边界不能直接作为实体拉伸。")
    layers = cfg.get("layers")
    if not isinstance(layers, dict):
        raise CAD3DError("请确认各图层对应的建模角色。")
    available = {e["layer"] for e in document["entities"]}
    allowed = {"wall", "column", "slab", "ignore"} if cfg["mode"] == "building" else {"section", "ignore"}
    for layer, role in layers.items():
        if not isinstance(layer, str) or layer not in available:
            raise CAD3DError(f"未知图层：{layer}")
        if not isinstance(role, str) or role not in allowed:
            raise CAD3DError(f"{cfg['mode']} 模式不支持角色 {role!r}。")
    params = cfg.setdefault("parameters", {})
    if not isinstance(params, dict):
        raise CAD3DError("parameters 必须是以角色为键的对象。")
    if set(params) - {"wall", "column", "slab", "section"}:
        raise CAD3DError("parameters 包含未知角色。")
    for role, values in params.items():
        if not isinstance(values, dict) or set(values) - {"height_m", "base_m"}:
            raise CAD3DError(f"{role} 含未知参数；仅支持 height_m 和 base_m。")
        # The workbench retains unfilled inactive roles for mode switching and
        # undo. Their null placeholders are not modeling parameters; explicit
        # non-null values must still be finite and within the supported range.
        for name, value in values.items():
            if value is not None:
                number = _finite(value, f"{role}.{name}", positive=name == "height_m")
                if abs(number) > MAX_EXTENT_M:
                    raise CAD3DError(f"{role}.{name} 超过 {MAX_EXTENT_M:g} 米数值范围限制。")
        if values.get("height_m") is not None and values.get("base_m") is not None:
            _check_parameters(values, role)
    for role in (set(layers.values()) - {"ignore"}) if not preview else []:
        values = params.get(role)
        if not isinstance(values, dict):
            raise CAD3DError(f"请为 {role} 明确填写 height_m 与 base_m。")
        _check_parameters(values, role)
    overrides = cfg.setdefault("overrides", {})
    if not isinstance(overrides, dict):
        raise CAD3DError("overrides 必须是以原图实体编号为键的对象。")
    by_id = {e["id"]: e for e in document["entities"]}
    for entity_id, values in overrides.items():
        if entity_id not in by_id or not isinstance(values, dict):
            raise CAD3DError(f"无效的单体参数覆盖：{entity_id}")
        if set(values) - {"height_m", "base_m"}:
            raise CAD3DError("单体参数覆盖仅可修改 height_m 或 base_m。")
        entity = by_id[entity_id]
        role = layers.get(entity["layer"], "ignore")
        if role == "ignore" or entity["status"] != "ready":
            raise CAD3DError(f"实体 {entity_id} 尚未选中或轮廓无效，不能设置单体参数。")
        for name, value in values.items():
            _finite(value, f"{entity_id}.{name}", positive=name == "height_m")
        combined = {**params.get(role, {}), **values}
        if not preview or (combined.get("height_m") is not None and combined.get("base_m") is not None):
            _check_parameters(combined, entity_id)
    from .selection import validate_selection, selected_ids
    selection = validate_selection(document, cfg)
    if "selection" in cfg:
        cfg["selection"] = selection
    selected = set(selected_ids(document["entities"], selection, layers))
    if any(entity_id not in selected for entity_id in overrides):
        raise CAD3DError("未选中的实体不能保留单体参数覆盖；请先清除覆盖或恢复选中。")
    from .dimensions import validate_bindings
    validate_bindings(document, cfg)
    return cfg


def _check_parameters(values: dict, label: str) -> tuple[float, float]:
    height = _finite(values.get("height_m"), f"{label}.height_m", positive=True)
    base = _finite(values.get("base_m"), f"{label}.base_m")
    if height > MAX_EXTENT_M or abs(base) > MAX_EXTENT_M or abs(base + height) > MAX_EXTENT_M:
        raise CAD3DError(f"{label} 超过 {MAX_EXTENT_M:g} 米数值范围限制。")
    return height, base


def _checked_entities(document: dict) -> list[dict]:
    if not isinstance(document, dict) or not isinstance(document.get("entities"), list):
        raise CAD3DError("请先上传并检查 DXF 文档。")
    entities = document["entities"]
    if len(entities) > MAX_ENTITIES:
        raise CAD3DError(f"文档超过 {MAX_ENTITIES} 个实体限制。")
    ids, total = set(), 0
    for e in entities:
        if (not isinstance(e, dict) or not isinstance(e.get("id"), str)
                or e["id"] in ids or not isinstance(e.get("layer"), str)
                or e.get("status") not in {"ready", "unsupported", "invalid"}
                or not isinstance(e.get("points"), list)):
            raise CAD3DError("实体元数据无效或实体编号重复。")
        ids.add(e["id"])
        total += len(e["points"])
        if total > MAX_VERTICES or len(e["points"]) > MAX_ENTITY_VERTICES:
            raise CAD3DError("文档超过顶点限制。")
        for p in e["points"]:
            if not isinstance(p, (list, tuple)) or len(p) != 2:
                raise CAD3DError("轮廓坐标必须包含 x 和 y。")
            if any(abs(_finite(x, "coordinate")) > MAX_COORDINATE for x in p):
                raise CAD3DError("坐标超出支持范围。")
    return entities


def _check_float32_precision(mesh: Any) -> None:
    """Reject geometry that WebGL/glTF float32 coordinates cannot preserve.

    Validate the actual destination representation, not only the double-precision
    solver mesh. Topology alone is insufficient: collapsed triangles retain their
    original indices and can still be reported as watertight.
    """
    quantized = mesh.copy()
    quantized.vertices = mesh.vertices.astype("float32").astype("float64")
    for axis in range(3):
        tolerance = max(FLOAT32_ABS_TOL_M, float(mesh.extents[axis]) * FLOAT32_REL_TOL)
        if (float(abs(quantized.vertices[:, axis] - mesh.vertices[:, axis]).max()) > tolerance
                or abs(float(quantized.extents[axis] - mesh.extents[axis])) > tolerance):
            raise CAD3DError("当前构件间距或标高相对细部尺寸过大，超出三维预览与 GLB 的 float32 精度；请分别建模距离很远的构件或调整明确的建模标高。")
    if (not quantized.is_watertight or not quantized.is_winding_consistent
            or any(float(area) <= 0 for area in quantized.area_faces)
            or not math.isfinite(float(quantized.volume)) or quantized.volume <= 0
            or not math.isclose(float(quantized.volume), float(mesh.volume),
                                rel_tol=FLOAT32_REL_TOL, abs_tol=1e-15)):
        raise CAD3DError("当前细部在三维预览或 GLB 的 float32 坐标下会塌缩或改变体积，未生成失真模型；请分开建模相距很远的构件。")


def _prepare_geometry(document: dict, cfg: dict) -> dict:
    from .selection import checked_selection, selected_ids
    from .diagnostics import diagnose_layers
    scale = UNIT_FACTORS[cfg["unit"]]
    entities = _refresh_entities(_checked_entities(document), scale, cfg["curve_tolerance_mm"])
    selection = checked_selection(document, cfg.get("selection"))
    ids = selected_ids(entities, selection, cfg["layers"])
    chosen = set(ids)
    selected = defaultdict(list)
    for entity in entities:
        if entity["id"] in chosen:
            item = copy.deepcopy(entity)
            if item.get("edge_source"):
                item["_edge"] = item["edge_source"]
                item.pop("related_entity_ids", None)
                item.pop("diagnostic_points", None)
            selected[item["layer"]].append(item)
    # Explicit removal of a duplicate edge may make its old branched graph
    # close. Reassemble only the selected source edges, with no gap snapping.
    for layer, members in selected.items():
        selected[layer] = _refresh_entities(_join_edges(members, scale), scale, cfg["curve_tolerance_mm"])
    refreshed = {entity["id"]: entity for members in selected.values() for entity in members}
    effective = [refreshed[e["id"]] if e["id"] in refreshed else e for e in entities
                 if e["id"] not in chosen or e["id"] in refreshed]
    ready_points = [point for members in selected.values() if len(members) <= MAX_LAYER_RINGS
                    and all(e["status"] == "ready" for e in members) for e in members for point in e["points"]]
    bounds = _bounds(ready_points, 2)
    origin = bounds["min"] if bounds else [0.0, 0.0]
    layers, diagnostics, contours = diagnose_layers(entities, selected, scale, origin)
    return {"entities": effective, "selected": selected, "selected_ids": ids, "selection": selection,
            "origin": origin, "layers": layers, "diagnostics": diagnostics, "contours": contours}


def analyze_document(document: dict, config: dict) -> dict:
    """Inspect source-coordinate material regions without height or extrusion."""
    _checked_entities(document)
    cfg = _checked_config(document, config, preview=True)
    prepared = _prepare_geometry(document, cfg)
    chosen = {item["id"] for members in prepared["selected"].values() for item in members}
    report = []
    for item in prepared["entities"]:
        selected = item["id"] in chosen
        failure = prepared["layers"][item["layer"]]["failure"] if selected else None
        status = ("failed" if failure else "ready") if selected else "ignored"
        reason = (item["reason"] if item["status"] != "ready" else failure or "二维轮廓检查通过；尺寸及实体用途仍需确认。") if selected else "此图层或实体未选中。"
        report.extend({"id": source_id, "contour_id": item["id"], "layer": item["layer"], "status": status, "reason": reason}
                      for source_id in item.get("source_entity_ids", [item["id"]]))
    return {"contours": prepared["contours"], "diagnostics": prepared["diagnostics"],
            "report": report,
            "selected_ids": prepared["selected_ids"], "selection": prepared["selection"],
            "preview_entities": prepared["entities"],
            "buildable": bool(prepared["contours"]) and not prepared["diagnostics"],
            "requires_confirmation": cfg.get("confirmed_solid") is not True,
            "unit": cfg["unit"], "curve_tolerance_mm": cfg["curve_tolerance_mm"],
            "warnings": ["二维材料区预检不代表尺寸或实体用途已经确认；生成三维模型仍需明确高度/长度与实体确认。"]}


def build_model(document: dict, config: dict) -> dict:
    """Extrude user-confirmed contours into closed Z-up metre meshes."""
    _checked_entities(document)
    cfg = _checked_config(document, config)
    trimesh = _dependency("trimesh")
    _dependency("mapbox_earcut")
    geometry = _dependency("shapely.geometry")
    scale = UNIT_FACTORS[cfg["unit"]]
    prepared = _prepare_geometry(document, cfg)
    entities = prepared["entities"]
    objects, reports = [], {}
    selected = prepared["selected"]
    selected_ids = {e["id"] for members in selected.values() for e in members}
    for e in entities:
        if e["id"] not in selected_ids:
            reports[e["id"]] = {"id": e["id"], "layer": e["layer"], "status": "ignored",
                                "reason": "此图层或实体未选中建模。"}
    # Ignored or blocked layers must not drag the working origin far away from
    # the selected geometry. Height/base edits keep this same XY transform.
    origin = prepared["origin"]
    transform = {"source_unit": cfg["unit"], "meters_per_unit": scale,
                 "origin_source_units": [*origin, 0.0], "model_up_axis": "Z",
                 "glb_up_axis": "Y", "glb_position_mapping": ["x", "z", "-y"],
                 "float32_relative_tolerance": FLOAT32_REL_TOL,
                 "float32_absolute_tolerance_m": FLOAT32_ABS_TOL_M,
                 "curve_tolerance_mm": cfg["curve_tolerance_mm"],
                 "curve_max_error_mm": max((e.get("curve_max_error_mm", 0) for e in entities), default=0),
                 "endpoint_roundoff_limit_m": MAX_JOIN_ROUNDOFF_M,
                 "description": "Origin = minimum XY of selected, supported layers. model XY = (source XY - origin XY) * meters_per_unit; model Z = user base/height. GLB = (model x, model z, -model y)."}
    vertex_count = 0
    for layer, members in selected.items():
        _checkpoint()
        role = cfg["layers"][layer]
        checked = prepared["layers"][layer]
        failure, polygons = checked["failure"], checked["polygons"]
        if failure:
            for e in members:
                reports[e["id"]] = {"id": e["id"], "layer": layer, "status": "failed",
                                    "reason": e["reason"] if e["status"] != "ready" else failure}
            continue
        parents, depths = checked["parents"], checked["depths"]
        layer_objects, layer_reports = [], {}
        for i, e in enumerate(members):
            if depths[i] % 2:
                if cfg["overrides"].get(e["id"]):
                    raise CAD3DError(f"实体 {e['id']} 是孔洞边界，请修改所属实体的参数。")
                continue
            holes = [j for j, parent in enumerate(parents) if parent == i]
            polygon = geometry.Polygon(polygons[i].exterior.coords,
                                       [polygons[j].exterior.coords for j in holes])
            values = {**cfg["parameters"][role], **cfg["overrides"].get(e["id"], {})}
            height, base = _check_parameters(values, e["id"])
            try:
                mesh = trimesh.creation.extrude_polygon(polygon, height, engine="earcut")
                mesh.apply_translation([0, 0, base])
                expected_volume = float(polygon.area * height)
                if (not mesh.is_watertight or not mesh.is_winding_consistent
                        or not math.isfinite(float(mesh.volume)) or mesh.volume <= 0
                        or not math.isclose(float(mesh.volume), expected_volume, rel_tol=1e-7, abs_tol=1e-15)):
                    raise CAD3DError("拉伸未通过封闭网格或体积检查，该图层未生成模型。")
                if not all(math.isfinite(float(x)) for row in mesh.vertices for x in row):
                    raise CAD3DError("拉伸生成了非有限顶点。")
                _check_float32_precision(mesh)
                vertex_count += len(mesh.vertices)
                if vertex_count > MAX_MODEL_VERTICES:
                    raise CAD3DError("生成模型超过顶点限制。")
                source_members = [e, *[members[j] for j in holes]]
                source_ids = [source_id for source in source_members
                              for source_id in source.get("source_entity_ids", [source["id"]])]
                source_metadata = [metadata for source in source_members for metadata in source.get("source_entities", [])]
                obj = {"id": e["id"], "layer": layer, "role": role,
                       "source_entity_ids": source_ids,
                       "source_entities": source_metadata,
                       "parameters": {"height_m": height, "base_m": base},
                       "vertices": mesh.vertices.tolist(), "faces": mesh.faces.tolist(),
                       "bounds": {"min": mesh.bounds[0].tolist(), "max": mesh.bounds[1].tolist()},
                       "volume_m3": float(mesh.volume), "footprint_area_m2": float(polygon.area),
                       "footprint": {"outer": [list(point) for point in polygon.exterior.coords],
                                     "holes": [[list(point) for point in ring.coords] for ring in polygon.interiors]},
                       "hole_count": len(holes), "color": ROLE_COLORS[role]}
                layer_objects.append(obj)
                for source in source_members:
                    source_id = source["id"]
                    layer_reports[source_id] = {"id": source_id, "layer": layer, "status": "modeled",
                                                "object_id": e["id"],
                                                "reason": "已按实体边界拉伸。" if source_id == e["id"]
                                                else f"已作为实体 {e['id']} 的贯通孔洞保留。"}
            except Exception as exc:
                failure = f"图层拉伸失败：{type(exc).__name__}: {exc}"
                break
        if failure:
            for e in members:
                reports[e["id"]] = {"id": e["id"], "layer": layer, "status": "failed", "reason": failure}
        else:
            objects.extend(layer_objects)
            reports.update(layer_reports)
    bounds = _bounds([p for obj in objects for p in (obj["bounds"]["min"], obj["bounds"]["max"])], 3)
    report = [{**reports[e["id"]], "id": source_id, "contour_id": e["id"]}
              for e in entities for source_id in e.get("source_entity_ids", [e["id"]])]
    return {"schema_version": 1, "filename": document.get("filename", ""),
            "source_sha256": document.get("sha256", ""), "objects": objects, "report": report,
            "bounds": bounds, "transform": transform, "config": cfg,
            "diagnostics": prepared["diagnostics"],
            "preview_entities": entities,
            "summary": {status: sum(row["status"] == status for row in report)
                        for status in ("modeled", "ignored", "failed")},
            "warnings": ["结果仅供交互几何预览，不含完整 Revit/BIM 语义、结构审批或门窗自动识别。",
                         "不同图层的实体相互独立，跨图层相交部分未作布尔合并。"]}


def export_glb(model: dict) -> bytes:
    """Export true meshes with source/parameter metadata, in metres and Y-up."""
    if not isinstance(model, dict) or not isinstance(model.get("objects"), list) or not model["objects"]:
        raise CAD3DError("没有成功建模的实体可供导出。")
    trimesh = _dependency("trimesh")
    scene = trimesh.Scene()
    scene.metadata = {"generator": "Civil Buddy CAD 3D deterministic preview", "units": "m",
                      "source_sha256": model.get("source_sha256", ""),
                      "transform": copy.deepcopy(model.get("transform", {})),
                      "config": copy.deepcopy(model.get("config", {}))}
    total = 0
    try:
        for obj in model["objects"]:
            total += len(obj["vertices"])
            if total > MAX_MODEL_VERTICES:
                raise CAD3DError("生成模型超过顶点限制。")
            mesh = trimesh.Trimesh(vertices=obj["vertices"], faces=obj["faces"], process=False)
            if not mesh.is_watertight:
                raise CAD3DError(f"实体 {obj['id']} 不是封闭网格。")
            _check_float32_precision(mesh)
            mesh.metadata = {key: copy.deepcopy(obj[key]) for key in
                             ("id", "layer", "role", "source_entity_ids", "parameters", "volume_m3")}
            mesh.metadata["source_entities"] = copy.deepcopy(obj.get("source_entities", []))
            # Uniform vertex color avoids trimesh's face->vertex conversion,
            # which would otherwise pull in the unrelated scipy extra.
            mesh.visual.vertex_colors = obj.get("color", [140, 170, 200, 255])
            mesh.apply_transform([[1, 0, 0, 0], [0, 0, 1, 0], [0, -1, 0, 0], [0, 0, 0, 1]])
            mesh.units = "m"
            scene.add_geometry(mesh, node_name=obj["id"], geom_name=obj["id"])
        return bytes(scene.export(file_type="glb"))
    except CAD3DError:
        raise
    except Exception as exc:
        raise CAD3DError(f"GLB 导出失败：{type(exc).__name__}: {exc}") from exc
