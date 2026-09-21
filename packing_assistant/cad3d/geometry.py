"""Strict DXF solid boundaries -> parameterized meshes, without model-generated code.

Only closed, zero-width, straight 2D polylines on the world XY plane are
accepted. A selected layer is atomic: an invalid/unsupported entity or touching
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
FLOAT32_REL_TOL = 1e-5
FLOAT32_ABS_TOL_M = 1e-7

UNIT_FACTORS = {"mm": 0.001, "cm": 0.01, "m": 1.0, "in": 0.0254, "ft": 0.3048}
DXF_UNITS = {0: ("unitless", None), 1: ("in", 0.0254), 2: ("ft", 0.3048),
             4: ("mm", 0.001), 5: ("cm", 0.01), 6: ("m", 1.0)}
ROLE_COLORS = {"wall": [100, 151, 224, 255], "column": [246, 180, 86, 255],
               "slab": [142, 162, 180, 255], "section": [78, 192, 170, 255]}


class CAD3DError(ValueError):
    """An explainable input, dependency or geometry failure."""


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
    value = float(value)
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


def _read_polyline(entity: Any) -> tuple[list[list[float]], str | None]:
    """Return original XY coordinates and an explicit unsupported reason."""
    kind = entity.dxftype()
    if kind == "LWPOLYLINE":
        raw = list(entity.get_points("xyseb"))
        points = [[float(p[0]), float(p[1])] for p in raw]
        closed = entity.closed
        curved = any(p[4] != 0 for p in raw)
        width = entity.dxf.get("const_width", 0) != 0 or any(p[2] != 0 or p[3] != 0 for p in raw)
        elevation = float(entity.dxf.get("elevation", 0))
        plane_bad = elevation != 0
    else:
        vertices = entity.vertices
        points = [[float(v.dxf.location.x), float(v.dxf.location.y)] for v in vertices]
        closed = entity.is_closed
        curved = (bool(entity.dxf.get("flags", 0) & (2 | 4))
                  or entity.dxf.get("smooth_type", 0) != 0
                  or any(v.dxf.get("bulge", 0) != 0 or v.dxf.get("flags", 0) & (1 | 2 | 8 | 16)
                         for v in vertices))
        width = (entity.dxf.get("default_start_width", 0) != 0
                 or entity.dxf.get("default_end_width", 0) != 0
                 or any(v.dxf.get("start_width", 0) != 0 or v.dxf.get("end_width", 0) != 0
                        for v in vertices))
        plane_bad = (not entity.is_2d_polyline or entity.dxf.elevation.z != 0
                     or any(v.dxf.location.z != 0 for v in vertices))
    if len(points) > MAX_ENTITY_VERTICES:
        raise CAD3DError(f"单个实体超过 {MAX_ENTITY_VERTICES} 个顶点限制。")
    if any(not math.isfinite(x) or abs(x) > MAX_COORDINATE for p in points for x in p):
        return [], "坐标不是有限数值或超出支持范围。"
    if plane_bad or tuple(entity.dxf.get("extrusion", (0, 0, 1))) != (0, 0, 1):
        return points, "仅支持世界坐标 XY 平面上 Z=0 的二维轮廓；非共面、带原图标高或倾斜轮廓未自动投影。"
    if entity.dxf.get("thickness", 0) != 0:
        return points, "暂不支持 DXF 自带 thickness，请移除后显式填写拉伸高度。"
    if curved:
        return points, "暂不支持圆弧、bulge 弧段或拟合曲线，未用控制框或直线代替原曲线。"
    if width:
        return points, "带宽多段线属于线条，尚非确认的实体边界；请提供明确的内外轮廓。"
    if not closed:
        return points, "轮廓未闭合：DXF 未设置闭合标记，未自动补线。"
    if len(points) > 1 and points[0] == points[-1]:
        points = points[:-1]  # a stored duplicate endpoint, not geometry repair
    return points, None


def inspect_dxf(data: bytes, filename: str) -> dict:
    """Read an ASCII DXF modelspace without altering geometry or inferring units."""
    if not isinstance(data, bytes) or not data:
        raise CAD3DError("请上传非空 DXF 文件。")
    if len(data) > MAX_DXF_BYTES:
        raise CAD3DError(f"DXF 超过 {MAX_DXF_BYTES // 1024 // 1024} MiB 大小限制。")
    if not isinstance(filename, str) or not filename.lower().endswith(".dxf"):
        raise CAD3DError("当前预览仅接受 DXF。请将 DWG 单独转换为 DXF 后上传。")
    if data.startswith(b"AutoCAD Binary DXF"):
        raise CAD3DError("暂不支持二进制 DXF，请另存为 ASCII DXF。")
    ezdxf = _dependency("ezdxf")
    _dependency("shapely.geometry")
    try:
        probe = io.StringIO(data.decode("latin1"), newline=None)
        encoding = _dependency("ezdxf.filemanagement").dxf_stream_info(probe).encoding
        drawing = ezdxf.read(io.StringIO(data.decode(encoding, errors="strict"), newline=None))
    except Exception as exc:
        raise CAD3DError(f"DXF 读取失败，未自动修复图纸：{type(exc).__name__}: {exc}") from exc
    space = drawing.modelspace()
    if len(drawing.entitydb) > MAX_DATABASE_ENTITIES:
        raise CAD3DError(f"DXF 数据库超过 {MAX_DATABASE_ENTITIES} 个实体限制（含块和布局）。")
    if len(space) > MAX_ENTITIES:
        raise CAD3DError(f"DXF 模型空间超过 {MAX_ENTITIES} 个实体限制。")
    entities = []
    counts: dict[str, int] = defaultdict(int)
    total_vertices = 0
    all_points = []
    for entity in space:
        kind, layer = entity.dxftype(), str(entity.dxf.get("layer", "0"))
        item = {"id": str(entity.dxf.handle), "layer": layer, "type": kind,
                "status": "unsupported", "reason": "", "points": []}
        counts[layer] += 1
        if kind in ("LWPOLYLINE", "POLYLINE"):
            points, reason = _read_polyline(entity)
            item["points"] = points
            if reason:
                item["reason"] = reason
                if reason.startswith("轮廓未闭合") or reason.startswith("坐标"):
                    item["status"] = "invalid"
            else:
                try:
                    _polygon(points)
                    item["status"] = "ready"
                    item["reason"] = "闭合直线轮廓；实体含义与单位仍需确认。"
                except CAD3DError as exc:
                    item.update(status="invalid", reason=str(exc))
        else:
            reasons = {"LINE": "未自动拼接独立 LINE 实体，请提供闭合多段线。",
                       "CIRCLE": "当前版本暂不支持圆形轮廓。",
                       "ARC": "当前版本暂不支持圆弧。",
                       "INSERT": "未自动展开块参照，请提供明确的实体轮廓。",
                       "SPLINE": "当前版本暂不支持样条曲线轮廓。"}
            item["reason"] = reasons.get(kind, f"{kind} 不是支持的闭合实体边界，暂未建模。")
            if kind == "LINE":
                points = [[float(entity.dxf.start.x), float(entity.dxf.start.y)],
                          [float(entity.dxf.end.x), float(entity.dxf.end.y)]]
                if all(math.isfinite(x) and abs(x) <= MAX_COORDINATE for p in points for x in p):
                    item["points"] = points
        total_vertices += len(item["points"])
        if total_vertices > MAX_VERTICES:
            raise CAD3DError(f"DXF 超过 {MAX_VERTICES} 个顶点限制。")
        all_points.extend(item["points"])
        entities.append(item)
    units_code = int(drawing.header.get("$INSUNITS", 0))
    name, factor = DXF_UNITS.get(units_code, ("unsupported", None))
    return {"schema_version": 1, "filename": filename, "sha256": hashlib.sha256(data).hexdigest(),
            "units": {"code": units_code, "name": name, "meters_per_unit": factor},
            "layers": [{"name": name, "suggested_role": _suggest_role(name), "entity_count": count}
                       for name, count in sorted(counts.items())],
            "entities": entities, "bounds": _bounds(all_points, 2),
            "warnings": ["仅检查模型空间，图纸空间布局暂未建模。",
                         "图层建议尚未确认；仅可拉伸用户确认的实体边界。",
                         "选中图层若含不支持或无效实体，整层暂停建模，以免填实尚未处理的孔洞。"]}


def _checked_config(document: dict, config: dict) -> dict:
    if not isinstance(config, dict):
        raise CAD3DError("建模配置必须是 JSON 对象。")
    cfg = copy.deepcopy(config)
    if set(cfg) - {"mode", "unit", "confirmed_solid", "layers", "parameters", "overrides"}:
        raise CAD3DError("建模配置包含未知设置。")
    if not isinstance(cfg.get("mode"), str) or cfg["mode"] not in ("building", "section"):
        raise CAD3DError("请选择建筑 building 或截面 section 模式。")
    if not isinstance(cfg.get("unit"), str) or cfg["unit"] not in UNIT_FACTORS:
        raise CAD3DError("请明确确认图纸单位：mm、cm、m、in 或 ft。")
    if cfg.get("confirmed_solid") is not True:
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
    for role in set(layers.values()) - {"ignore"}:
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
        _check_parameters({**params[role], **values}, entity_id)
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


def build_model(document: dict, config: dict) -> dict:
    """Extrude user-confirmed contours into closed Z-up metre meshes."""
    entities = _checked_entities(document)
    cfg = _checked_config(document, config)
    trimesh = _dependency("trimesh")
    _dependency("mapbox_earcut")
    geometry = _dependency("shapely.geometry")
    scale = UNIT_FACTORS[cfg["unit"]]
    objects, reports = [], {}
    selected: dict[str, list[dict]] = defaultdict(list)
    for e in entities:
        role = cfg["layers"].get(e["layer"], "ignore")
        if role == "ignore":
            reports[e["id"]] = {"id": e["id"], "layer": e["layer"], "status": "ignored",
                                "reason": "此图层未选中建模。"}
        else:
            selected[e["layer"]].append(e)
    # Ignored or blocked layers must not drag the working origin far away from
    # the selected geometry. Height/base edits keep this same XY transform.
    ready_points = [p for members in selected.values()
                    if len(members) <= MAX_LAYER_RINGS and all(e["status"] == "ready" for e in members)
                    for e in members for p in e["points"]]
    original_bounds = _bounds(ready_points, 2)
    origin = original_bounds["min"] if original_bounds else [0.0, 0.0]
    transform = {"source_unit": cfg["unit"], "meters_per_unit": scale,
                 "origin_source_units": [*origin, 0.0], "model_up_axis": "Z",
                 "glb_up_axis": "Y", "glb_position_mapping": ["x", "z", "-y"],
                 "float32_relative_tolerance": FLOAT32_REL_TOL,
                 "float32_absolute_tolerance_m": FLOAT32_ABS_TOL_M,
                 "description": "Origin = minimum XY of selected, supported layers. model XY = (source XY - origin XY) * meters_per_unit; model Z = user base/height. GLB = (model x, model z, -model y)."}
    vertex_count = 0
    for layer, members in selected.items():
        role = cfg["layers"][layer]
        failure = None
        if any(e["status"] != "ready" for e in members):
            failure = "整层暂停：不支持或无效实体可能代表孔洞；请清理或拆分此图层后再建模。"
        if len(members) > MAX_LAYER_RINGS:
            failure = f"图层超过 {MAX_LAYER_RINGS} 个轮廓限制。"
        polygons = []
        if not failure:
            try:
                for e in members:
                    points = [[(p[0] - origin[0]) * scale, (p[1] - origin[1]) * scale]
                              for p in e["points"]]
                    if any(abs(x) > MAX_EXTENT_M for p in points for x in p):
                        raise CAD3DError("平移原点后坐标仍超出支持的米制范围。")
                    polygons.append(_polygon(points))
                for i, first in enumerate(polygons):
                    for second in polygons[i + 1:]:
                        if first.boundary.intersects(second.boundary):
                            raise CAD3DError("图层含相触、相交或重复轮廓；未自动合并或修复。")
            except CAD3DError as exc:
                failure = str(exc)
        if failure:
            for e in members:
                reports[e["id"]] = {"id": e["id"], "layer": layer, "status": "failed",
                                    "reason": e["reason"] if e["status"] != "ready" else failure}
            continue
        parents = []
        for i, polygon in enumerate(polygons):
            containers = [j for j, other in enumerate(polygons) if i != j and other.contains(polygon)]
            parents.append(min(containers, key=lambda j: polygons[j].area) if containers else None)
        depths = []
        for i in range(len(members)):
            depth, parent = 0, parents[i]
            while parent is not None:
                depth, parent = depth + 1, parents[parent]
            depths.append(depth)
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
                source_ids = [e["id"], *[members[j]["id"] for j in holes]]
                obj = {"id": e["id"], "layer": layer, "role": role,
                       "source_entity_ids": source_ids,
                       "parameters": {"height_m": height, "base_m": base},
                       "vertices": mesh.vertices.tolist(), "faces": mesh.faces.tolist(),
                       "bounds": {"min": mesh.bounds[0].tolist(), "max": mesh.bounds[1].tolist()},
                       "volume_m3": float(mesh.volume), "footprint_area_m2": float(polygon.area),
                       "hole_count": len(holes), "color": ROLE_COLORS[role]}
                layer_objects.append(obj)
                for source_id in source_ids:
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
    report = [reports[e["id"]] for e in entities]
    return {"schema_version": 1, "filename": document.get("filename", ""),
            "source_sha256": document.get("sha256", ""), "objects": objects, "report": report,
            "bounds": bounds, "transform": transform, "config": cfg,
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
