"""Strict SI JSON -> first-order elastic Pynite beam/frame results.

No scripts, paths, automatic loads or code-design verdicts are accepted. Each
call creates a fresh solver model and only returns JSON-compatible values.
Supports and material/load values must be explicit. The caller must obtain
user-confirmed coordinates and owns their provenance and any persistence.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
import importlib.util
from importlib.metadata import PackageNotFoundError, version
import math
import re
from typing import Any

from packing_assistant.runtime.cancel import check

MAX_NODES = 64
MAX_MEMBERS = 128
MAX_LOADS = 512
MAX_COMBINATIONS = 8
MAX_RESULT_POINTS = 50000
_ID = re.compile(r"[A-Za-z0-9_-]{1,48}\Z")
_NODE_LOADS = {"FX", "FY", "FZ", "MX", "MY", "MZ"}
_MEMBER_LOADS = {"Fx", "Fy", "Fz", "FX", "FY", "FZ"}


class FrameAnalysisError(ValueError):
    """A user-visible model, dependency, or solver failure."""


def available() -> bool:
    return importlib.util.find_spec("Pynite") is not None


def _object(value: Any, required: set[str], optional: set[str], label: str) -> dict:
    if not isinstance(value, dict) or set(value) - required - optional or required - set(value):
        raise FrameAnalysisError(f"{label} 字段缺失或包含不支持的字段；不接受脚本、文件路径或任意求解器选项。")
    return value


def _number(value: Any, label: str, lower: float = -1e12, upper: float = 1e12) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise FrameAnalysisError(f"{label} 必须是有限数值。")
    try:
        result = float(value)
    except OverflowError as exc:
        raise FrameAnalysisError(f"{label} 超出数值范围。") from exc
    if not math.isfinite(result) or not lower <= result <= upper:
        raise FrameAnalysisError(f"{label} 必须在 {lower:g} 至 {upper:g} 的有限范围内。")
    return result


def _identifier(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise FrameAnalysisError(f"{label} 必须是 1 至 48 位英文字母、数字、下划线或连字符。")
    return value


def _rows(value: Any, label: str, minimum: int, maximum: int) -> list:
    if not isinstance(value, list) or not minimum <= len(value) <= maximum:
        raise FrameAnalysisError(f"{label} 数量必须为 {minimum} 至 {maximum}，超出分析预算或列表为空。")
    return value


def _index(rows: list[dict], label: str) -> dict[str, dict]:
    result = {}
    for row in rows:
        key = _identifier(row["id"], f"{label}.id")
        if key in result:
            raise FrameAnalysisError(f"{label} 编号重复：{key}。")
        result[key] = row
    return result


def validate_frame(payload: Any) -> dict:
    """Validate a bounded explicit model without importing the optional solver."""
    check()
    required = {"schema_version", "units", "nodes", "members", "materials", "sections",
                "load_cases", "combinations", "nodal_loads", "member_loads"}
    data = deepcopy(_object(payload, required, {"samples", "source", "title"}, "模型"))
    if type(data["schema_version"]) is not int or data["schema_version"] != 1 or data["units"] != "SI":
        raise FrameAnalysisError("只支持 schema_version=1、units='SI'（m、N、Pa、rad）。")
    if data.get("source", "user") not in ("user", "synthetic"):
        raise FrameAnalysisError("source 只支持 user 或 synthetic；服务不会推断真实图纸证据。")
    data["source"] = data.get("source", "user")
    if "title" in data and (not isinstance(data["title"], str) or len(data["title"]) > 160
                             or any(ord(c) < 32 for c in data["title"])):
        raise FrameAnalysisError("title 必须是不含控制字符、最多 160 字符的文本。")
    samples = data.get("samples", 21)
    if type(samples) is not int or not 3 <= samples <= 201:
        raise FrameAnalysisError("samples 必须是 3 至 201 的整数。")
    data["samples"] = samples

    for row in _rows(data["nodes"], "nodes", 2, MAX_NODES):
        _object(row, {"id", "x_m", "y_m", "z_m", "support"}, set(), "节点")
        for key in ("x_m", "y_m", "z_m"):
            row[key] = _number(row[key], f"节点.{key}", -1e6, 1e6)
        if (not isinstance(row["support"], list) or len(row["support"]) != 6
                or any(type(v) is not bool for v in row["support"])):
            raise FrameAnalysisError("节点 support 必须显式给出 [DX,DY,DZ,RX,RY,RZ] 六个布尔约束。")
    nodes = _index(data["nodes"], "节点")
    coords = {key: tuple(row[k] for k in ("x_m", "y_m", "z_m")) for key, row in nodes.items()}
    if len(set(coords.values())) != len(coords):
        raise FrameAnalysisError("存在重合节点；请合并并明确连接关系。")

    for row in _rows(data["materials"], "materials", 1, 32):
        _object(row, {"id", "E_Pa", "G_Pa", "nu", "density_kg_m3"}, set(), "材料")
        row["E_Pa"] = _number(row["E_Pa"], "E_Pa", 1e3, 1e13)
        row["G_Pa"] = _number(row["G_Pa"], "G_Pa", 1e3, 1e13)
        row["nu"] = _number(row["nu"], "nu", -0.99, 0.4999)
        row["density_kg_m3"] = _number(row["density_kg_m3"], "density_kg_m3", 0, 1e6)
        expected = row["E_Pa"] / (2 * (1 + row["nu"]))
        if not math.isclose(expected, row["G_Pa"], rel_tol=1e-5):
            raise FrameAnalysisError("各向同性材料须满足 G=E/[2(1+nu)]；请核对单位和材料输入。")
    materials = _index(data["materials"], "材料")
    for row in _rows(data["sections"], "sections", 1, 32):
        _object(row, {"id", "A_m2", "Iy_m4", "Iz_m4", "J_m4"}, set(), "截面")
        row["A_m2"] = _number(row["A_m2"], "A_m2", 1e-12, 1e4)
        for key in ("Iy_m4", "Iz_m4", "J_m4"):
            row[key] = _number(row[key], key, 1e-18, 1e8)
    sections = _index(data["sections"], "截面")

    pairs, used_nodes, lengths = set(), set(), {}
    for row in _rows(data["members"], "members", 1, MAX_MEMBERS):
        _object(row, {"id", "i", "j", "material_id", "section_id", "rotation_deg"}, set(), "杆件")
        for key, known in (("i", nodes), ("j", nodes), ("material_id", materials), ("section_id", sections)):
            if not isinstance(row[key], str) or row[key] not in known:
                raise FrameAnalysisError(f"杆件 {row.get('id')} 引用了未知 {key}：{row[key]}。")
        if row["i"] == row["j"]:
            raise FrameAnalysisError("杆件两端不能是同一个节点。")
        pair = frozenset((row["i"], row["j"]))
        if pair in pairs:
            raise FrameAnalysisError("存在重复或反向重叠杆件；请明确唯一杆件。")
        pairs.add(pair)
        used_nodes.update(pair)
        length = math.dist(coords[row["i"]], coords[row["j"]])
        if not 1e-6 <= length <= 1e5:
            raise FrameAnalysisError("杆件长度须为 1e-6 至 1e5 m。")
        row["rotation_deg"] = _number(row["rotation_deg"], "rotation_deg", -360, 360)
        lengths[_identifier(row["id"], "杆件.id")] = length
        # No implicit physical-member splitting: the submitted graph must say
        # exactly where the joints are, which also makes support checks explicit.
        start, end = coords[row["i"]], coords[row["j"]]
        vector = [end[k] - start[k] for k in range(3)]
        # Pynite 3.2.0 PhysMember.descritize includes nodes within
        # 1e-12 * (1 + L), inclusively. Our exclusion must be at least as
        # conservative, including for long members, or the solver silently
        # adds connections absent from the submitted node/member graph.
        joint_tolerance = max(1e-8, 1e-12 * (1.0 + length))
        for node_id, point in coords.items():
            if node_id in pair:
                continue
            t = sum((point[k] - start[k]) * vector[k] for k in range(3)) / length**2
            if 0 < t < 1 and math.dist(point, [start[k] + t * vector[k] for k in range(3)]) <= joint_tolerance:
                raise FrameAnalysisError(f"杆件 {row['id']} 经过或过近于中间节点 {node_id}；请核对位置并在该节点显式拆分杆件。")
    members = _index(data["members"], "杆件")
    if used_nodes != set(nodes):
        raise FrameAnalysisError("存在未连接杆件的孤立节点：" + ", ".join(sorted(set(nodes) - used_nodes)))

    for row in _rows(data["load_cases"], "load_cases", 1, 8):
        _object(row, {"id"}, set(), "荷载工况")
    cases = _index(data["load_cases"], "荷载工况")
    for row in _rows(data["combinations"], "combinations", 1, MAX_COMBINATIONS):
        _object(row, {"id", "factors"}, set(), "荷载组合")
        factors = row["factors"]
        if not isinstance(factors, dict) or not factors or set(factors) - set(cases):
            raise FrameAnalysisError("组合 factors 必须显式引用已有荷载工况。")
        row["factors"] = {k: _number(v, f"组合系数 {k}", -100, 100) for k, v in factors.items()}
        if not any(row["factors"].values()):
            raise FrameAnalysisError("荷载组合不能全为零。")
    _index(data["combinations"], "荷载组合")
    if samples * len(members) * len(data["combinations"]) > MAX_RESULT_POINTS:
        raise FrameAnalysisError("杆件、组合与采样点乘积超出结果预算。")

    case_loads = set()
    for row in _rows(data["nodal_loads"], "nodal_loads", 0, MAX_LOADS):
        _object(row, {"node_id", "case_id", "direction", "value"}, set(), "节点荷载")
        if (not isinstance(row["node_id"], str) or row["node_id"] not in nodes
                or not isinstance(row["case_id"], str) or row["case_id"] not in cases
                or not isinstance(row["direction"], str) or row["direction"] not in _NODE_LOADS):
            raise FrameAnalysisError("节点荷载只能引用已有节点、工况及全局 FX/FY/FZ/MX/MY/MZ。")
        row["value"] = _number(row["value"], "节点荷载 value（N 或 N·m）")
        case_loads.add(row["case_id"])
    for row in _rows(data["member_loads"], "member_loads", 0, MAX_LOADS):
        _object(row, {"member_id", "case_id", "direction", "w1_N_m", "w2_N_m", "x1_m", "x2_m"}, set(), "杆件分布荷载")
        if (not isinstance(row["member_id"], str) or row["member_id"] not in members
                or not isinstance(row["case_id"], str) or row["case_id"] not in cases
                or not isinstance(row["direction"], str) or row["direction"] not in _MEMBER_LOADS):
            raise FrameAnalysisError("分布荷载只能引用已有杆件、工况及 Fx/Fy/Fz（局部）或 FX/FY/FZ（全局）。")
        for key in ("w1_N_m", "w2_N_m"):
            row[key] = _number(row[key], key)
        length = lengths[row["member_id"]]
        for key in ("x1_m", "x2_m"):
            row[key] = _number(row[key], key, 0, length)
        if row["x1_m"] >= row["x2_m"]:
            raise FrameAnalysisError("分布荷载须满足 0 <= x1_m < x2_m <= 杆件长度。")
        case_loads.add(row["case_id"])
    if len(data["nodal_loads"]) + len(data["member_loads"]) > MAX_LOADS:
        raise FrameAnalysisError("荷载总数超出分析预算。")
    if set(cases) - case_loads:
        raise FrameAnalysisError("每个荷载工况至少需要一条显式荷载，允许输入零值表示空载。")
    used_cases = {case for combo in data["combinations"] for case, factor in combo["factors"].items() if factor}
    if used_cases != set(cases):
        raise FrameAnalysisError("每个荷载工况必须至少进入一个非零系数组合，避免静默忽略荷载。")
    check()
    return data


def _check_supports(data: dict) -> None:
    """Catch free rigid-body modes even when their load happens to be zero."""
    import numpy as np
    nodes = {row["id"]: row for row in data["nodes"]}
    graph: dict[str, set] = defaultdict(set)
    for member in data["members"]:
        graph[member["i"]].add(member["j"])
        graph[member["j"]].add(member["i"])
    unseen = set(nodes)
    while unseen:
        check()
        seed = min(unseen)
        stack, component = [seed], set()
        while stack:
            current = stack.pop()
            if current not in component:
                component.add(current)
                stack.extend(graph[current] - component)
        unseen -= component
        coords = np.array([[nodes[key][k] for k in ("x_m", "y_m", "z_m")] for key in sorted(component)])
        origin = coords.mean(axis=0)
        scale = max(float(np.ptp(coords, axis=0).max()), 1e-6)
        constraints = []
        for key in sorted(component):
            node = nodes[key]
            x, y, z = (np.array([node[k] for k in ("x_m", "y_m", "z_m")]) - origin) / scale
            modes = [[1, 0, 0, 0, z, -y], [0, 1, 0, -z, 0, x], [0, 0, 1, y, -x, 0],
                     [0, 0, 0, 1, 0, 0], [0, 0, 0, 0, 1, 0], [0, 0, 0, 0, 0, 1]]
            constraints.extend(modes[dof] for dof, fixed in enumerate(node["support"]) if fixed)
        if not constraints or np.linalg.matrix_rank(np.array(constraints), tol=1e-10) < 6:
            raise FrameAnalysisError("结构不稳定：连接组 " + ", ".join(sorted(component))
                                     + " 的支座未约束全部刚体位移/转动；请核对六个自由度。")


def _values(array: Any) -> list[float]:
    result = [float(x) for x in array]
    if any(not math.isfinite(x) for x in result):
        raise FrameAnalysisError("求解器返回非有限结果；模型可能不稳定或数值尺度不适合。")
    return result


def analyze_frame(payload: Any) -> dict:
    """Solve the validated model, returning global node and local member results."""
    data = validate_frame(payload)
    if not available():
        raise FrameAnalysisError("梁框架分析依赖未安装，请安装 requirements-analysis.txt（PyniteFEA）。")
    try:
        from Pynite import FEModel3D
        engine_version = version("PyniteFEA")
    except (ImportError, PackageNotFoundError) as exc:
        raise FrameAnalysisError("梁框架依赖未完整安装，请重新安装 requirements-analysis.txt。") from exc
    from packing_assistant.runtime.cancel import RunCancelled
    _check_supports(data)
    check()
    model = FEModel3D()
    try:
        for row in data["materials"]:
            model.add_material(row["id"], row["E_Pa"], row["G_Pa"], row["nu"], row["density_kg_m3"])
        for row in data["sections"]:
            model.add_section(row["id"], row["A_m2"], row["Iy_m4"], row["Iz_m4"], row["J_m4"])
        for row in data["nodes"]:
            model.add_node(row["id"], row["x_m"], row["y_m"], row["z_m"])
            model.def_support(row["id"], *row["support"])
        for row in data["members"]:
            check()
            model.add_member(row["id"], row["i"], row["j"], row["material_id"], row["section_id"], rotation=row["rotation_deg"])
        for row in data["combinations"]:
            model.add_load_combo(row["id"], row["factors"])
        for row in data["nodal_loads"]:
            model.add_node_load(row["node_id"], row["direction"], row["value"], row["case_id"])
        for row in data["member_loads"]:
            model.add_member_dist_load(row["member_id"], row["direction"], row["w1_N_m"], row["w2_N_m"],
                                       row["x1_m"], row["x2_m"], row["case_id"])
        check()
        model.analyze_linear(check_stability=True, check_statics=False, sparse=True)
        check()
        results = []
        for combo in data["combinations"]:
            check()
            name = combo["id"]
            nodes = []
            for node_id, node in model.nodes.items():
                nodes.append({"id": node_id,
                              "displacement_m": _values(getattr(node, k)[name] for k in ("DX", "DY", "DZ")),
                              "rotation_rad": _values(getattr(node, k)[name] for k in ("RX", "RY", "RZ")),
                              "reaction_N": _values(getattr(node, k)[name] for k in ("RxnFX", "RxnFY", "RxnFZ")),
                              "reaction_Nm": _values(getattr(node, k)[name] for k in ("RxnMX", "RxnMY", "RxnMZ"))})
            members = []
            for member_id, member in model.members.items():
                check()
                count = data["samples"]
                axial = member.axial_array(count, name)
                curve = {"x_m": _values(axial[0]), "axial_N": _values(axial[1]),
                         "shear_y_N": _values(member.shear_array("Fy", count, name)[1]),
                         "shear_z_N": _values(member.shear_array("Fz", count, name)[1]),
                         "moment_y_Nm": _values(member.moment_array("My", count, name)[1]),
                         "moment_z_Nm": _values(member.moment_array("Mz", count, name)[1]),
                         "torque_Nm": _values(member.torque_array(count, name)[1]),
                         "dx_m": _values(member.deflection_array("dx", count, name)[1]),
                         "dy_m": _values(member.deflection_array("dy", count, name)[1]),
                         "dz_m": _values(member.deflection_array("dz", count, name)[1])}
                axes = [_values(row) for row in member.T()[:3, :3]]
                members.append({"id": member_id, "i": member.i_node.name, "j": member.j_node.name,
                                "length_m": float(member.L()), "local_axes_global": axes, "curves": curve,
                                "sampled_extrema": {key: {"min": min(values), "max": max(values)}
                                                    for key, values in curve.items() if key != "x_m"}})
            results.append({"id": name, "factors": combo["factors"], "nodes": nodes, "members": members})
    except RunCancelled:
        raise
    except FrameAnalysisError:
        raise
    except Exception as exc:
        # Only validated scalar data reached the solver; avoid returning engine
        # internals, paths, or unbounded tracebacks to the browser.
        raise FrameAnalysisError("梁框架求解失败：请核对支座稳定性、杆件连接、截面与单位。"
                                 + f"（{type(exc).__name__}）") from exc
    check()
    return {"ok": True, "schema_version": 1, "analysis": "linear_elastic_frame",
            "units": {"length": "m", "force": "N", "moment": "N*m", "stress": "Pa", "rotation": "rad"},
            "source": data["source"], "title": data.get("title", "梁框架线弹性分析"),
            "engine": {"name": "PyniteFEA", "version": engine_version},
            "model": data, "combinations": results,
            "assumptions": ["一阶、小位移、各向同性线弹性梁框架；杆件端部为刚接。",
                            "杆件仅在共有节点编号处连接；图形交叉不自动成为节点。",
                            "支座按六个全局自由度约束；未自动计入自重、荷载组合或设计规范限值。",
                            "杆件结果按局部坐标；曲线极值仅为采样值，节点反力按全局坐标。",
                            "结果为结构分析数值，不作规范合格判定。"]}


def synthetic_example(kind: str = "beam") -> dict:
    """Explicit classroom fixtures, never defaults for a user's real design."""
    data = {"schema_version": 1, "units": "SI", "source": "synthetic", "title": "合成教学样例：简支梁均布荷载",
            "samples": 41,
            "nodes": [{"id": "N1", "x_m": 0.0, "y_m": 0.0, "z_m": 0.0, "support": [True, True, True, True, False, False]},
                      {"id": "N2", "x_m": 4.0, "y_m": 0.0, "z_m": 0.0, "support": [False, True, True, False, False, False]}],
            "materials": [{"id": "M1", "E_Pa": 200e9, "G_Pa": 200e9 / 2.6, "nu": 0.3, "density_kg_m3": 7850.0}],
            "sections": [{"id": "S1", "A_m2": 0.01, "Iy_m4": 8e-6, "Iz_m4": 8e-6, "J_m4": 1e-5}],
            "members": [{"id": "B1", "i": "N1", "j": "N2", "material_id": "M1", "section_id": "S1", "rotation_deg": 0.0}],
            "load_cases": [{"id": "L1"}], "combinations": [{"id": "C1", "factors": {"L1": 1.0}}],
            "nodal_loads": [], "member_loads": [{"member_id": "B1", "case_id": "L1", "direction": "FY",
                                                 "w1_N_m": -1000.0, "w2_N_m": -1000.0, "x1_m": 0.0, "x2_m": 4.0}]}
    if kind == "beam":
        return data
    if kind == "frame":
        data["title"] = "合成教学样例：门式刚架水平荷载"
        data["nodes"] = [{"id": "N1", "x_m": 0.0, "y_m": 0.0, "z_m": 0.0, "support": [True] * 6},
                         {"id": "N2", "x_m": 0.0, "y_m": 3.0, "z_m": 0.0, "support": [False] * 6},
                         {"id": "N3", "x_m": 4.0, "y_m": 3.0, "z_m": 0.0, "support": [False] * 6},
                         {"id": "N4", "x_m": 4.0, "y_m": 0.0, "z_m": 0.0, "support": [True] * 6}]
        data["members"] = [{"id": key, "i": first, "j": last, "material_id": "M1", "section_id": "S1", "rotation_deg": 0.0}
                           for key, first, last in (("B1", "N1", "N2"), ("B2", "N2", "N3"), ("B3", "N3", "N4"))]
        data["member_loads"] = []
        data["nodal_loads"] = [{"node_id": "N2", "case_id": "L1", "direction": "FX", "value": 1000.0}]
        return data
    raise FrameAnalysisError("仅支持 beam 或 frame 合成教学样例。")
