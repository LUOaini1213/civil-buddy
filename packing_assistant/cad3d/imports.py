"""Bounded DXF overview and reproducible layer/region selection before strict geometry.

Overview paths are display samples, never modeling coordinates. Selection uses
complete conservative entity bounds and original instance-qualified handles.
The original source bytes are neither rewritten nor reduced here.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import io
import math
from typing import Any

MAX_SCAN_BYTES = 64 * 1024 * 1024
MAX_SCAN_DATABASE_ENTITIES = 300_000
MAX_SCAN_EXPANDED_ENTITIES = 250_000
MAX_SCAN_BLOCK_DEPTH = 8
MAX_PREVIEW_ENTITIES = 2000
MAX_PREVIEW_POINTS = 64
MAX_LAYER_FILTER = 256


def _check() -> None:
    from packing_assistant.runtime.cancel import check
    check()


class _CheckedStream(io.StringIO):
    def readline(self, *args, **kwargs):
        _check()
        return super().readline(*args, **kwargs)


def read_drawing(data: bytes):
    import ezdxf
    from ezdxf.filemanagement import dxf_stream_info
    if not isinstance(data, bytes) or not data or len(data) > MAX_SCAN_BYTES:
        raise ValueError("DXF 不能为空，且分阶段导入最多支持 64 MiB。")
    if data.startswith(b"AutoCAD Binary DXF"):
        raise ValueError("请将二进制 DXF 另存为文本 DXF 后上传。")
    _check()
    probe = _CheckedStream(data.decode("latin1"), newline=None)
    try:
        info = dxf_stream_info(probe)
        text = data.decode(info.encoding)
        drawing = ezdxf.read(_CheckedStream(text, newline=None))
    except (UnicodeError, ValueError, ezdxf.DXFError) as exc:
        raise ValueError("DXF 无法读取，请检查文件完整性与编码。") from exc
    _check()
    if len(drawing.entitydb) > MAX_SCAN_DATABASE_ENTITIES:
        raise ValueError(f"DXF 数据库超过扫描上限 {MAX_SCAN_DATABASE_ENTITIES} 个实体。")
    return drawing


def normalize_filter(value: dict) -> dict:
    if not isinstance(value, dict) or set(value) - {"layers", "bounds"}:
        raise ValueError("选择范围仅允许图层列表与原图 XY 范围。")
    layers = value.get("layers")
    if (not isinstance(layers, list) or not 1 <= len(layers) <= MAX_LAYER_FILTER
            or any(not isinstance(name, str) or not name or len(name) > 255 for name in layers)):
        raise ValueError(f"请选择 1–{MAX_LAYER_FILTER} 个有效图层。")
    result = {"layers": sorted(set(layers))}
    bounds = value.get("bounds")
    if bounds is not None:
        if (not isinstance(bounds, (list, tuple)) or len(bounds) != 4
                or any(type(number) not in {int, float} or abs(number) > 1e12 or not math.isfinite(number) for number in bounds)
                or not bounds[0] < bounds[2] or not bounds[1] < bounds[3]):
            raise ValueError("区域须为有限的 [最小X, 最小Y, 最大X, 最大Y]，且范围不能为零。")
        result["bounds"] = list(bounds)
    return result


def _union(first, second):
    if first is None: return second
    if second is None: return first
    return {"min": [min(first["min"][i], second["min"][i]) for i in range(2)],
            "max": [max(first["max"][i], second["max"][i]) for i in range(2)]}


def _bounds(entity):
    from ezdxf import bbox
    # Composite annotations can dereference their own geometry blocks outside
    # our explicit INSERT budgets. Keep these unknown rather than recursively
    # traversing them through ezdxf's unbounded virtual-entity path.
    if entity.dxftype() not in {"LINE", "CIRCLE", "ARC", "LWPOLYLINE", "POLYLINE", "SPLINE", "ELLIPSE", "POINT", "HATCH", "TEXT", "MTEXT"}:
        return None
    if entity.dxftype() in {"TEXT", "MTEXT"} and len(str(entity.dxf.get("text", ""))) > 2000:
        return None
    try:
        box = bbox.extents([entity], fast=True)
        if box.has_data:
            values = [*box.extmin, *box.extmax]
            if all(math.isfinite(number) and abs(number) <= 1e12 for number in values):
                return {"min": values[:3], "max": values[3:]}
    except (ValueError, TypeError, ArithmeticError, AttributeError):
        pass
    return None


def _xybox(box):
    return {"min": box["min"][:2], "max": box["max"][:2]} if box else None


def _transformed_bounds(box, matrix):
    if box is None: return None
    corners = [matrix.transform((x, y, z)) for x in (box["min"][0], box["max"][0])
               for y in (box["min"][1], box["max"][1]) for z in (box["min"][2], box["max"][2])]
    if any(not math.isfinite(number) or abs(number) > 1e12 for point in corners for number in point):
        return None
    return {"min": [min(point[i] for point in corners) for i in range(3)],
            "max": [max(point[i] for point in corners) for i in range(3)]}


def _union3(first, second):
    if first is None: return second
    if second is None: return first
    return {"min": [min(first["min"][i], second["min"][i]) for i in range(3)],
            "max": [max(first["max"][i], second["max"][i]) for i in range(3)]}


def _outside(box, region):
    return bool(box and region and (box["max"][0] < region[0] or box["max"][1] < region[1]
                or box["min"][0] > region[2] or box["min"][1] > region[3]))


class _Overview:
    """Count repeated block definitions once; never expand millions just to overview."""
    def __init__(self, drawing):
        self.drawing, self.cache, self.boxes = drawing, {}, {}
        self.visited = 0

    def info(self, entity, inherited="0", names=()):
        _check()
        self.visited += 1
        if self.visited > MAX_SCAN_DATABASE_ENTITIES * 4:
            raise ValueError("图层概览计算超过受控定义预算，请拆分复杂嵌套块。")
        layer = str(entity.dxf.get("layer", "0"))
        if layer == "0": layer = inherited
        if entity.dxftype() != "INSERT":
            identifier = str(entity.dxf.handle)
            if identifier not in self.boxes: self.boxes[identifier] = _bounds(entity)
            box = self.boxes[identifier]
            return {"bounds": box, "layers": Counter({layer: 1}), "unknown": int(box is None), "depth": 0}
        name = str(entity.dxf.name)
        if name in names or len(names) >= MAX_SCAN_BLOCK_DEPTH:
            raise ValueError(f"块参照循环或超过扫描的 {MAX_SCAN_BLOCK_DEPTH} 层嵌套上限。")
        key = (name, layer)
        block = self.drawing.blocks.get(name)
        if block is None or not len(block):
            return {"bounds": None, "layers": Counter({layer: 1}), "unknown": 1, "depth": 1}
        if key not in self.cache:
            box, layers, unknown, depth = None, Counter(), 0, 1
            for child in block:
                metadata = self.info(child, layer, (*names, name))
                box = _union3(box, metadata["bounds"])
                layers.update(metadata["layers"])
                unknown += metadata["unknown"]
                depth = max(depth, metadata["depth"] + 1)
            self.cache[key] = {"bounds": box, "layers": layers, "unknown": unknown, "depth": depth}
        metadata = self.cache[key]
        if len(names) + metadata["depth"] > MAX_SCAN_BLOCK_DEPTH:
            raise ValueError(f"块参照超过扫描的 {MAX_SCAN_BLOCK_DEPTH} 层嵌套上限。")
        repeat = entity.dxf.get("row_count", 1) * entity.dxf.get("column_count", 1)
        if repeat != 1:
            return {"bounds": None, "layers": Counter({k: v * repeat for k, v in metadata["layers"].items()}),
                    "unknown": sum(metadata["layers"].values()) * repeat, "depth": metadata["depth"]}
        return {"bounds": _transformed_bounds(metadata["bounds"], entity.matrix44()),
                "layers": metadata["layers"], "unknown": metadata["unknown"], "depth": metadata["depth"]}


def _leaves(drawing, *, layers=None, region=None):
    """Expand only candidate branches, using conservative cached definition bounds."""
    from ezdxf.math import Matrix44
    overview = _Overview(drawing)
    visited = 0

    def visit(entity, root, matrix, path=(), names=(), inherited="0"):
        nonlocal visited
        _check()
        visited += 1
        if visited > MAX_SCAN_EXPANDED_ENTITIES:
            raise ValueError(f"块展开超过扫描上限 {MAX_SCAN_EXPANDED_ENTITIES} 个实体，请在 CAD 中拆分图纸。")
        kind = entity.dxftype()
        handle = str(entity.dxf.get("handle") or "")
        raw_layer = str(entity.dxf.get("layer", "0"))
        layer = inherited if path and raw_layer == "0" else raw_layer
        logical_id = "/".join((*path, handle))
        metadata = overview.info(entity, inherited)
        if layers is not None and not layers.intersection(metadata["layers"]):
            return
        conservative = _transformed_bounds(metadata["bounds"], matrix)
        # Unknown child bounds prevent pruning their parent: a hole must not vanish.
        if not metadata["unknown"] and _outside(conservative, region):
            return
        if kind == "INSERT":
            name = str(entity.dxf.name)
            block = drawing.blocks.get(name)
            if name in names or len(path) >= MAX_SCAN_BLOCK_DEPTH:
                raise ValueError(f"块参照循环或超过扫描的 {MAX_SCAN_BLOCK_DEPTH} 层嵌套上限。")
            if block is not None and len(block):
                # Arrays cannot be quietly collapsed to their first instance.
                if entity.dxf.get("row_count", 1) != 1 or entity.dxf.get("column_count", 1) != 1:
                    # A selected child layer must retain the parent rejection,
                    # even when the INSERT itself lives on layer 0.
                    failure_layer = sorted(layers.intersection(metadata["layers"]))[0] if layers is not None else layer
                    yield root, logical_id, failure_layer, kind, None, None
                    return
                combined = entity.matrix44() @ matrix
                for child in block:
                    yield from visit(child, root, combined, (*path, handle), (*names, name), layer)
                return
        yield root, logical_id, layer, kind, _xybox(conservative), None

    for root in drawing.modelspace():
        yield from visit(root, root, Matrix44())


def _preview(entity, box):
    if entity is None or box is None:
        return []
    from ezdxf.disassemble import make_primitive
    try:
        primitive = make_primitive(entity)
        if primitive.path is None:
            return []
        diagonal = math.dist(box["min"], box["max"])
        points = []
        for point in primitive.path.flattening(max(diagonal / 128, 1e-6)):
            _check()
            if len(points) >= MAX_PREVIEW_POINTS:
                break
            xy = [point.x, point.y]
            if all(math.isfinite(number) for number in xy):
                points.append(xy)
        return points
    except (ValueError, TypeError, ArithmeticError, AttributeError):
        return []


def scan_dxf(data: bytes, filename: str) -> dict:
    drawing = read_drawing(data)
    overview = _Overview(drawing)
    layers, preview, bounds = {}, [], None
    expanded, unknown = 0, 0
    kinds = Counter()
    for index, entity in enumerate(drawing.modelspace(), 1):
        metadata = overview.info(entity)
        box = _xybox(metadata["bounds"])
        identifier, layer, kind = str(entity.dxf.handle), str(entity.dxf.layer), entity.dxftype()
        expanded += sum(metadata["layers"].values())
        kinds[kind] += 1
        for effective_layer, count in metadata["layers"].items():
            record = layers.setdefault(effective_layer, {"name": effective_layer, "entity_count": 0, "bounds": None, "unknown_bounds": 0})
            record["entity_count"] += count
            record["bounds"] = _union(record["bounds"], box)
            record["unknown_bounds"] += min(count, metadata["unknown"])
        bounds = _union(bounds, box)
        unknown += metadata["unknown"]
        # Stable root-entity samples avoid expanding repeated blocks for display.
        slot = index - 1 if index <= MAX_PREVIEW_ENTITIES else ((index * 2654435761) & 0xffffffff) % index
        if slot < MAX_PREVIEW_ENTITIES:
            row = {"id": identifier, "layer": layer, "type": kind, "bounds": box,
                   "points": _preview(entity, box) if kind != "INSERT" else [], "display_only": True,
                   "block_overview": kind == "INSERT", "layers": sorted(metadata["layers"])}
            if len(preview) < MAX_PREVIEW_ENTITIES: preview.append(row)
            else: preview[slot] = row
    _check()
    return {"schema": "civil.cad.scan.v1", "filename": filename, "sha256": hashlib.sha256(data).hexdigest(),
            "source_bytes": len(data), "layers": sorted(layers.values(), key=lambda row: row["name"]),
            "bounds": bounds, "preview": preview, "preview_sampled": expanded > len(preview),
            "preview_scope": "modelspace-paths-and-block-bounds",
            "counts": {"modelspace": len(drawing.modelspace()), "database": len(drawing.entitydb),
                       "expanded": expanded, "expanded_is_counted_not_materialized": True,
                       "previewed": len(preview), "unknown_bounds": unknown, "types": dict(kinds)},
            "units_code": int(drawing.header.get("$INSUNITS", 0)),
            "warnings": ["这是分阶段导入概览；实体路径经过限量抽样，块仅显示保守包围框，不能据此推断尺寸或建模成功。",
                         "请选择图层和原图坐标范围后严检。跨越选择边界的实体不会被裁切或自动补线。",
                         "无法确定范围的实体仍会送交严检，避免把孔洞静默遗漏。"]}


def filter_modelspace(drawing, source_filter: dict):
    selected = normalize_filter(source_filter)
    layers = set(selected["layers"])
    wanted = selected.get("bounds")
    roots, selected_ids, seen_layers = {}, [], set()
    counts = Counter()
    excluded = []
    available = set()
    overview = _Overview(drawing)
    for root in drawing.modelspace(): available.update(overview.info(root)["layers"])
    if layers - available:
        raise ValueError("选择包含不存在的有效图层：" + "、".join(sorted(layers - available)))
    for root, identifier, layer, kind, box, _ in _leaves(drawing, layers=layers, region=wanted):
        seen_layers.add(layer)
        if layer not in layers:
            counts["excluded_layer"] += 1
            continue
        if wanted and box:
            low, high = box["min"], box["max"]
            inside = low[0] >= wanted[0] and low[1] >= wanted[1] and high[0] <= wanted[2] and high[1] <= wanted[3]
            if not inside:
                crossing = not (high[0] < wanted[0] or high[1] < wanted[1] or low[0] > wanted[2] or low[1] > wanted[3])
                counts["excluded_crossing" if crossing else "excluded_outside"] += 1
                if crossing and len(excluded) < 100:
                    excluded.append({"id": identifier, "layer": layer, "type": kind, "bounds": box,
                                     "reason": "实体跨越选择区域边界，未裁切、未建模。"})
                continue
        if box is None: counts["selected_unknown_bounds"] += 1
        selected_ids.append(identifier)
        roots[str(root.dxf.handle)] = root
    if not selected_ids:
        raise ValueError("当前图层与区域没有完整实体，请扩大范围或调整图层。")
    _check()
    return list(roots.values()), selected, {"selected_entity_ids": selected_ids, "selected": len(selected_ids),
                                           "exclusion_count_scope": "visited-candidate-leaves; disjoint branches pruned",
                                           **dict(counts), "excluded": excluded}
