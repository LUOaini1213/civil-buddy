"""Geometric section properties of confirmed CAD material regions, including holes."""
from __future__ import annotations

import hashlib
import json
import math
from importlib.metadata import version


def analyze_section(document: dict, config: dict) -> dict:
    from packing_assistant.cad3d.geometry import analyze_document, UNIT_FACTORS
    from packing_assistant.runtime.cancel import check

    check()
    if not isinstance(config, dict):
        raise ValueError("截面配置必须是 JSON 对象。")
    if config.get("mode") != "section":
        raise ValueError("请切换到构件截面模式，再计算截面性质。")
    if config.get("confirmed_solid") is not True:
        raise ValueError("请先确认实体区域与孔洞。")
    analysis = analyze_document(document, config)
    if not analysis["buildable"] or analysis["diagnostics"]:
        raise ValueError("当前选集存在轮廓问题，请先处理二维诊断。")
    contours = analysis["contours"]
    if len(contours) > 16 or sum(len(c["points"]) + sum(map(len, c["holes"])) for c in contours) > 12000:
        raise ValueError("每次截面分析最多 16 个材料区域、12000 个轮廓顶点；请缩小选集。")
    from shapely.geometry import Polygon
    from sectionproperties.pre.geometry import Geometry
    from sectionproperties.analysis.section import Section

    millimeters_per_unit = UNIT_FACTORS[config["unit"]] * 1000
    regions = []
    for contour in contours:
        check()
        # Translate in source coordinates before scaling: large survey origins
        # must not lose local section precision when subtracting second moments.
        ox = min(p[0] for p in contour["points"])
        oy = min(p[1] for p in contour["points"])
        convert = lambda ring: [((x - ox) * millimeters_per_unit, (y - oy) * millimeters_per_unit) for x, y in ring]
        polygon = Polygon(convert(contour["points"]), [convert(ring) for ring in contour["holes"]])
        if not polygon.is_valid or polygon.area <= 1e-9:
            raise ValueError("材料区无效或小于支持的截面面积。")
        geometry = Geometry(polygon)
        # Geometric integration is exact on polygon edges; no torsion/warping
        # claim is made and no unnecessarily refined mesh is needed here.
        geometry.create_mesh(mesh_sizes=polygon.area / 50, coarse=True)
        section = Section(geometry)
        section.calculate_geometric_properties()
        check()
        area = float(section.get_area())
        cx, cy = map(float, section.get_c())
        ixx, iyy, ixy = map(float, section.get_ic())
        i11, i22 = map(float, section.get_ip())
        phi = float(section.get_phi())
        if not all(math.isfinite(v) for v in (area, cx, cy, ixx, iyy, ixy, i11, i22, phi)) or min(area, ixx, iyy, i11, i22) <= 0:
            raise ValueError("截面性质未得到有效有限值。")
        if not math.isclose(area, polygon.area, rel_tol=1e-7, abs_tol=1e-7):
            raise ValueError("网格面积与包含孔洞的原轮廓面积不一致，未发布结果。")
        # Integration/subtraction leaves tiny product-of-inertia noise even in
        # symmetric sections. Expose its scale instead of an arbitrary-looking
        # scientific notation value or a false principal direction for a square.
        inertia_tolerance = 1e-12 * max(abs(ixx), abs(iyy), abs(i11), abs(i22))
        if abs(ixy) <= inertia_tolerance:
            ixy = 0.0
        angle_defined = abs(i11 - i22) > 2 * inertia_tolerance
        phi = (phi + 90.0) % 180.0 - 90.0 if angle_defined else None
        if phi is not None and abs(phi) < 1e-9:
            phi = 0.0
        regions.append({
            "outer_id": contour["outer_id"], "source_entity_ids": contour["source_entity_ids"],
            "layer": contour["layer"], "hole_ids": contour["hole_ids"],
            "area_mm2": area, "centroid_source": [ox + cx / millimeters_per_unit, oy + cy / millimeters_per_unit],
            "centroid_local_mm": [cx, cy], "origin_source": [ox, oy],
            "Ixx_mm4": ixx, "Iyy_mm4": iyy, "Ixy_mm4": ixy,
            "I11_mm4": i11, "I22_mm4": i22, "principal_angle_deg": phi,
            "principal_angle_defined": angle_defined,
            "inertia_noise_tolerance_mm4": inertia_tolerance,
            "rx_mm": math.sqrt(ixx / area), "ry_mm": math.sqrt(iyy / area),
            "mesh_elements": len(section.elements),
        })
    check()
    return {"kind": "section", "engine": "sectionproperties", "engine_version": version("sectionproperties"),
            "source_sha256": document.get("sha256"), "unit": config["unit"],
            "curve_tolerance_mm": analysis["curve_tolerance_mm"],
            "config_sha256": hashlib.sha256(json.dumps(config, sort_keys=True, allow_nan=False).encode()).hexdigest(),
            "regions": regions, "total_area_mm2": sum(row["area_mm2"] for row in regions),
            "notes": ["各材料区域分别计算；不把不相连的构件自动合成一个承载截面。",
                      "惯性矩关于各区域形心轴，形心原图坐标使用已确认图纸单位。",
                      "Ixy=∫(x-cx)(y-cy)dA；近零积分噪声按各区域数值容差归零。",
                      "主轴角从原图 +X 逆时针转向 I11 轴，范围 [-90°,90°)，轴线以 180° 等价；I11≈I22 时无唯一方向。",
                      "曲线结果对应当前弦高误差下的离散轮廓；未计算扭转、强度或规范合格结论。"]}
