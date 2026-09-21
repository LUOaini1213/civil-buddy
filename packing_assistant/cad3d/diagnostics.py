"""Shared, model-free material region checks and source-coordinate diagnostics."""
from __future__ import annotations

import math

ANNOTATION_TYPES = {"TEXT", "MTEXT", "DIMENSION", "LEADER", "MLEADER", "POINT"}
MAX_DIAGNOSTICS = 200


def diagnose_layers(entities, selected, scale, origin):
    from .geometry import CAD3DError, MAX_EXTENT_M, MAX_LAYER_RINGS, _checkpoint, _dependency, _polygon
    geometry = _dependency("shapely.geometry")
    results, diagnostics, contours = {}, [], []
    emitted = set()
    current_failure, truncated = [None], [False]

    def diagnostic(code, message, members, points=None, **extra):
        if current_failure[0] is None:
            current_failure[0] = message
        if len(diagnostics) >= MAX_DIAGNOSTICS:
            truncated[0] = True
            return
        ids = sorted({item["id"] if isinstance(item, dict) else item for item in members})
        key = (code, tuple(ids))
        if key not in emitted:
            emitted.add(key)
            diagnostics.append({"code": code, "message": message, "severity": "error",
                                "entity_ids": ids, "points": points or [], **extra})

    def source_point(point):
        return [point.x / scale + origin[0], point.y / scale + origin[1]]

    def near_points(first, second):
        return [source_point(point) for point in _dependency("shapely.ops").nearest_points(first, second)]

    def local_points(item):
        return [[(p[0] - origin[0]) * scale, (p[1] - origin[1]) * scale] for p in item["points"]]

    def shape(item):
        points = local_points(item)
        if item["status"] == "ready":
            return _polygon(points)
        return geometry.LineString(points) if len(points) >= 2 else None

    for layer, members in selected.items():
        _checkpoint()
        current_failure[0] = None
        selected_sources = {source_id for member in members for source_id in member.get("source_entity_ids", [member["id"]])}
        if len(members) > MAX_LAYER_RINGS:
            diagnostic("limit", f"图层超过 {MAX_LAYER_RINGS} 个轮廓限制。", members)
            results[layer] = {"members": members, "polygons": [], "parents": [], "depths": [], "failure": current_failure[0]}
            continue
        # Exact duplicate LINEs can stop graph closure before polygon creation.
        for i, item in enumerate(members):
            _checkpoint()
            if len(diagnostics) >= MAX_DIAGNOSTICS:
                break
            if not item.get("edge_source"):
                continue
            for j, other in enumerate(members[i + 1:]):
                if j % 32 == 0:
                    _checkpoint()
                if len(diagnostics) >= MAX_DIAGNOSTICS:
                    truncated[0] = True
                    break
                if (other.get("edge_source") and len(item["points"]) >= 2 and len(other["points"]) >= 2
                        and geometry.LineString(item["points"]).equals(geometry.LineString(other["points"]))):
                    diagnostic("duplicate", "重复边界；请明确排除一份副本后重新检查。", [item, other], item["points"][:2])
        for item in members:
            if item["status"] == "ready":
                continue
            reason = item["reason"]
            code = "unsupported_entity" if item["status"] == "unsupported" else "invalid_contour"
            if "未闭合" in reason:
                code = "open_contour"
            related = item.get("related_entity_ids", [item["id"]])
            points = item.get("diagnostic_points", [item["points"][i] for i in (0, -1)] if item["points"] else [])
            extra = {}
            if code == "open_contour" and len(points) == 2:
                extra["gap_mm"] = math.dist(*points) * scale * 1000
            diagnostic(code, reason, related, points, **extra)
        polygons = []
        if current_failure[0] is None:
            for item in members:
                try:
                    points = local_points(item)
                    if any(abs(value) > MAX_EXTENT_M for point in points for value in point):
                        raise CAD3DError("平移原点后坐标仍超出支持的米制范围。")
                    polygons.append(_polygon(points))
                except CAD3DError as exc:
                    diagnostic("invalid_contour", str(exc), [item], item["points"][:1])
            if len(polygons) == len(members):
                for i, first in enumerate(polygons):
                    _checkpoint()
                    if len(diagnostics) >= MAX_DIAGNOSTICS and current_failure[0] is not None:
                        break
                    for j in range(i + 1, len(polygons)):
                        if j % 32 == 0:
                            _checkpoint()
                        if len(diagnostics) >= MAX_DIAGNOSTICS and current_failure[0] is not None:
                            truncated[0] = True
                            break
                        second = polygons[j]
                        if first.boundary.intersects(second.boundary):
                            duplicate = first.equals(second)
                            diagnostic("duplicate" if duplicate else "intersecting_boundaries",
                                       "图层含相触、相交或重复轮廓；请明确排除重复副本后重新检查。" if duplicate else "边界相触或相交；未自动合并或修复。",
                                       [members[i], members[j]], near_points(first.boundary, second.boundary))
                        uncertainty = (members[i].get("curve_max_error_mm", 0) + members[j].get("curve_max_error_mm", 0)) / 1000
                        if uncertainty > 0 and first.boundary.distance(second.boundary) <= uncertainty:
                            diagnostic("curve_clearance", "曲线轮廓间距小于双方离散误差之和，无法确认是否相交或孔洞相接；请减小弦高误差后重试。",
                                       [members[i], members[j]], near_points(first.boundary, second.boundary),
                                       gap_mm=first.boundary.distance(second.boundary) * 1000)
        # An explicit outer-frame exclusion is valid. An omitted inner boundary
        # (including an unsupported one) must never silently fill material.
        if len(polygons) == len(members) and current_failure[0] is None:
            for omitted in entities:
                _checkpoint()
                if (omitted["layer"] != layer or set(omitted.get("source_entity_ids", [omitted["id"]])) <= selected_sources
                        or omitted.get("type") in ANNOTATION_TYPES):
                    continue
                try:
                    other = shape(omitted)
                except CAD3DError:
                    other = None
                if other is None:
                    diagnostic("omitted_boundary", "排除的几何无法定位，不能确认它不是内孔；请保留检查或在 CAD 中拆分明确的参考图层。", [omitted, *members])
                    continue
                # Exact redundant rings/edges can be explicitly excluded.
                if any(other.equals(polygon) for polygon in polygons):
                    continue
                if other.geom_type == "LineString" and any(polygon.boundary.covers(other) for polygon in polygons):
                    continue
                for i, polygon in enumerate(polygons):
                    if i % 32 == 0:
                        _checkpoint()
                    if other.geom_type == "Polygon" and other.contains(polygon):
                        continue
                    uncertainty = (omitted.get("curve_max_error_mm", 0) + members[i].get("curve_max_error_mm", 0)) / 1000
                    border = other.boundary if other.geom_type == "Polygon" else other
                    if polygon.intersects(other) or (uncertainty and polygon.boundary.distance(border) <= uncertainty):
                        diagnostic("omitted_boundary", "选中轮廓内或边缘有未纳入的边界，可能漏孔；请将相关边界加入选集，不能只拉伸外环。",
                                   [members[i], omitted], near_points(polygon.boundary, border))
        failure = current_failure[0]
        parents, depths = [], []
        if not failure:
            for i, polygon in enumerate(polygons):
                containers = [j for j, other in enumerate(polygons) if j != i and other.contains(polygon)]
                parents.append(min(containers, key=lambda j: polygons[j].area) if containers else None)
            for i in range(len(members)):
                depth, parent = 0, parents[i]
                while parent is not None:
                    depth, parent = depth + 1, parents[parent]
                depths.append(depth)
            for i, item in enumerate(members):
                if depths[i] % 2:
                    continue
                holes = [j for j, parent in enumerate(parents) if parent == i]
                material = geometry.Polygon(polygons[i].exterior.coords, [polygons[j].exterior.coords for j in holes])
                contours.append({"outer_id": item["id"], "hole_ids": [members[j]["id"] for j in holes], "layer": layer,
                                 "area_m2": float(material.area), "area_mm2": float(material.area * 1e6),
                                 "points": item["points"], "holes": [members[j]["points"] for j in holes],
                                 "source_entity_ids": [source for member in [item, *[members[j] for j in holes]]
                                                       for source in member.get("source_entity_ids", [member["id"]])]})
        results[layer] = {"members": members, "polygons": polygons, "parents": parents, "depths": depths, "failure": failure}
    if not selected:
        diagnostic("empty_selection", "尚未选择可检查的建模实体或图层。", [])
    if truncated[0]:
        diagnostics.append({"code": "diagnostic_limit", "severity": "warning", "entity_ids": [], "points": [],
                            "message": f"最多显示 {MAX_DIAGNOSTICS} 条定位诊断；失败实体仍逐项保留报告，请缩小选择后继续检查。"})
    return results, diagnostics, contours
