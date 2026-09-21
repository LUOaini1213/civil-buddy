"""Optional STEP solids from the same validated polygon profiles as the preview.

This does not reconstruct native splines or parametric CAD history. All geometry
comes from a successful server-side model, never an Agent-generated script.
Serialization and independent STEP re-reading happen entirely in memory.
"""
from __future__ import annotations

import importlib.util
import io
import math
from threading import RLock

_LOCK = RLock()
MAX_STEP_VERTICES = 10000
MAX_STEP_OBJECTS = 128
MAX_STEP_BYTES = 64 * 1024 * 1024


def available() -> bool:
    return importlib.util.find_spec("cadquery") is not None


def export_step(model: dict) -> bytes:
    from .geometry import CAD3DError
    from packing_assistant.runtime import cancel
    if not available():
        raise CAD3DError("STEP 依赖未安装，请运行 python -m pip install -r requirements-cad-step.txt")
    objects = model.get("objects", []) if isinstance(model, dict) else []
    if not objects or len(objects) > MAX_STEP_OBJECTS:
        raise CAD3DError(f"STEP 导出需要 1–{MAX_STEP_OBJECTS} 个已生成构件。")
    try:
        import cadquery as cq
        from OCP.STEPControl import STEPControl_Writer, STEPControl_Reader, STEPControl_AsIs
        from OCP.IFSelect import IFSelect_RetDone
        from OCP.Interface import Interface_Static
        with _LOCK:
            solids, count, expected_volume = [], 0, 0.
            for obj in objects:
                cancel.check()
                footprint = obj.get("footprint")
                if not isinstance(footprint, dict):
                    raise CAD3DError("此模型缺少已校验轮廓，请重新生成后导出 STEP。")
                base, height = obj["parameters"]["base_m"] * 1000, obj["parameters"]["height_m"] * 1000
                wires = []
                for ring in [footprint["outer"], *footprint["holes"]]:
                    if len(ring) > 1 and ring[0] == ring[-1]:
                        ring = ring[:-1]
                    count += len(ring)
                    if len(ring) < 3 or count > MAX_STEP_VERTICES:
                        raise CAD3DError(f"STEP 轮廓无效或超过 {MAX_STEP_VERTICES} 个顶点预算。")
                    if any(len(p) != 2 or any(type(v) not in (int, float) or not math.isfinite(v) for v in p) for p in ring):
                        raise CAD3DError("STEP 轮廓包含无效坐标。")
                    wires.append(cq.Wire.makePolygon([cq.Vector(p[0] * 1000, p[1] * 1000, base) for p in ring], close=True))
                solid = cq.Solid.extrudeLinear(wires[0], wires[1:], cq.Vector(0, 0, height))
                expected = obj["volume_m3"] * 1e9
                if not solid.isValid() or not math.isclose(solid.Volume(), expected, rel_tol=1e-7, abs_tol=1e-5):
                    raise CAD3DError("STEP 实体没有通过有效性或体积核对。")
                solids.append(solid)
                expected_volume += expected
            cancel.check()
            compound = cq.Compound.makeCompound(solids)
            writer = STEPControl_Writer()
            previous_unit = Interface_Static.CVal_s("write.step.unit")
            try:
                Interface_Static.SetCVal_s("write.step.unit", "MM")
                if writer.Transfer(compound.wrapped, STEPControl_AsIs) != IFSelect_RetDone:
                    raise CAD3DError("STEP 实体转换失败。")
                stream = io.BytesIO()
                if writer.WriteStream(stream) != IFSelect_RetDone:
                    raise CAD3DError("STEP 序列化失败。")
            finally:
                if previous_unit:
                    Interface_Static.SetCVal_s("write.step.unit", previous_unit)
            payload = stream.getvalue()
            if len(payload) > MAX_STEP_BYTES:
                raise CAD3DError("STEP 文件超过导出预算。")
            # A successful writer is insufficient; check the actual artifact.
            reader = STEPControl_Reader()
            if reader.ReadStream("civil-buddy.step", io.BytesIO(payload)) != IFSelect_RetDone or not reader.TransferRoots():
                raise CAD3DError("STEP 文件重新读取失败。")
            restored = cq.Shape.cast(reader.OneShape())
            if (len(restored.Solids()) != len(solids) or not restored.isValid()
                    or not math.isclose(restored.Volume(), expected_volume, rel_tol=1e-7, abs_tol=1e-5)):
                raise CAD3DError("STEP 重开后的实体数量或体积不一致。")
            original_box, restored_box = compound.BoundingBox(), restored.BoundingBox()
            if any(not math.isclose(getattr(original_box, key), getattr(restored_box, key), rel_tol=1e-8, abs_tol=1e-5)
                   for key in ("xmin", "xmax", "ymin", "ymax", "zmin", "zmax")):
                raise CAD3DError("STEP 重开后的尺寸或位置不一致。")
            cancel.check()
            return payload
    except CAD3DError:
        raise
    except (ImportError, OSError) as exc:
        raise CAD3DError("STEP 内核无法加载，请检查 requirements-cad-step.txt 的可选依赖。") from exc
    except Exception as exc:
        from packing_assistant.runtime.cancel import RunCancelled
        if isinstance(exc, RunCancelled):
            raise
        raise CAD3DError(f"STEP 导出失败：{type(exc).__name__}: {exc}") from exc
