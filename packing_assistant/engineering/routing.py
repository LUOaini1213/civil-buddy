"""Explicit road graphs -> shortest route, separate from construction CPM."""
from __future__ import annotations

from importlib.metadata import version
import math
import re

from packing_assistant.runtime.cancel import check

MAX_NODES = 200
MAX_EDGES = 500
IDENTIFIER = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,63}\Z")
METRICS = {"distance_m": "m", "travel_time_min": "min"}


def _object(value, keys, label):
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError(f"{label}必须且只能包含：{', '.join(sorted(keys))}。")
    return value


def _id(value, label):
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise ValueError(f"{label}须以英文字母开头，仅含字母、数字、下划线或连字符，最多 64 字符。")
    return value


def _text(value, label, maximum=100):
    if (not isinstance(value, str) or not value.strip() or len(value) > maximum
            or any(ord(char) < 32 or ord(char) == 127 for char in value)):
        raise ValueError(f"{label}须为 1–{maximum} 个字符，不得含控制字符。")
    return value.strip()


def validate_route(payload):
    """Validate only explicit weights; no coordinates or speed assumptions."""
    check()
    _object(payload, {"source", "metric", "origin", "destination", "nodes", "edges"}, "路线输入")
    if payload["source"] not in ("user", "synthetic"):
        raise ValueError("source 只支持 user 或 synthetic。")
    if not isinstance(payload["metric"], str) or payload["metric"] not in METRICS:
        raise ValueError("metric 只支持 distance_m（米）或 travel_time_min（分钟）。")
    if not isinstance(payload["nodes"], list) or not 1 <= len(payload["nodes"]) <= MAX_NODES:
        raise ValueError(f"路网须有 1–{MAX_NODES} 个明确节点。")
    if not isinstance(payload["edges"], list) or len(payload["edges"]) > MAX_EDGES:
        raise ValueError(f"道路最多 {MAX_EDGES} 条。")
    nodes, node_ids = [], set()
    for row in payload["nodes"]:
        check()
        _object(row, {"id", "name"}, "道路节点")
        ident = _id(row["id"], "节点编号")
        if ident in node_ids:
            raise ValueError(f"节点编号重复：{ident}。")
        node_ids.add(ident)
        nodes.append({"id": ident, "name": _text(row["name"], "节点名称")})
    origin, destination = _id(payload["origin"], "起点编号"), _id(payload["destination"], "终点编号")
    if origin not in node_ids or destination not in node_ids:
        raise ValueError("起点和终点必须引用已有道路节点。")
    edges, edge_ids = [], set()
    for row in payload["edges"]:
        check()
        _object(row, {"id", "from", "to", "weight", "bidirectional", "closed", "source"}, "道路")
        ident = _id(row["id"], "道路编号")
        if ident in edge_ids:
            raise ValueError(f"道路编号重复：{ident}。")
        edge_ids.add(ident)
        start, end = _id(row["from"], "道路起点"), _id(row["to"], "道路终点")
        if start not in node_ids or end not in node_ids:
            raise ValueError(f"{ident}：道路引用了未知节点。")
        if start == end:
            raise ValueError(f"{ident}：道路两端须为不同节点。")
        weight = row["weight"]
        if type(weight) not in (int, float) or not 0 < weight <= 1e9 or not math.isfinite(weight):
            raise ValueError(f"{ident}：边权须为大于 0 且不超过 1e9 的有限数值，单位由 metric 明确。")
        if type(row["bidirectional"]) is not bool or type(row["closed"]) is not bool:
            raise ValueError(f"{ident}：双向和封路状态必须是布尔值。")
        edges.append({"id": ident, "from": start, "to": end, "weight": float(weight),
                      "bidirectional": row["bidirectional"], "closed": row["closed"],
                      "source": _text(row["source"], f"{ident} 的边权来源", 200)})
    return {"source": payload["source"], "metric": payload["metric"], "origin": origin,
            "destination": destination, "nodes": nodes, "edges": edges}


def calculate_route(payload):
    """Dijkstra on a fresh MultiDiGraph; closed roads never enter the graph."""
    model = validate_route(payload)
    try:
        import networkx as nx
    except ImportError as exc:
        raise ImportError("场内路线依赖未就绪，请安装 NetworkX 后重试。") from exc
    graph = nx.MultiDiGraph()
    graph.add_nodes_from(sorted(row["id"] for row in model["nodes"]))
    for edge in sorted(model["edges"], key=lambda row: row["id"]):
        check()
        if edge["closed"]:
            continue
        graph.add_edge(edge["from"], edge["to"], key=edge["id"], edge_id=edge["id"],
                       weight=edge["weight"], source=edge["source"], reversed=False)
        if edge["bidirectional"]:
            graph.add_edge(edge["to"], edge["from"], key=edge["id"], edge_id=edge["id"],
                           weight=edge["weight"], source=edge["source"], reversed=True)
    check()
    try:
        path = nx.shortest_path(graph, model["origin"], model["destination"], weight="weight", method="dijkstra")
        found = True
    except nx.NetworkXNoPath:
        path, found = [], False
    check()
    segments = []
    for start, end in zip(path, path[1:]):
        check()
        # NetworkX MultiDiGraph evaluates the minimum parallel-edge weight.
        # Keep the exact source edge, including reverse traversal, in the report.
        edge = min(graph[start][end].values(), key=lambda row: (row["weight"], row["edge_id"]))
        segments.append({"edge_id": edge["edge_id"], "from": start, "to": end,
                         "weight": edge["weight"], "source": edge["source"], "reversed": edge["reversed"]})
    total = math.fsum(segment["weight"] for segment in segments) if found else None
    check()
    return {"ok": True, "route_found": found, "model": model, "metric": model["metric"],
            "unit": METRICS[model["metric"]], "total_weight": total, "path_node_ids": path,
            "segments": segments, "excluded_edge_ids": [edge["id"] for edge in model["edges"] if edge["closed"]],
            "engine": {"name": "NetworkX", "version": version("networkx"), "algorithm": "Dijkstra"},
            "message": "已按明确路网计算路线。" if found else "当前路网、通行方向和封路状态下，起点到终点不可达。",
            "notes": ["这是场内道路最短路线，独立于施工工序的关键路径与最短工期。",
                      "只使用用户明确输入的边权、方向及封路状态；不从示意图位置推断距离或速度。",
                      "通行时间视为本次输入的固定边权；未加入随出发时刻变化的交通预测。",
                      "同权重最短路线可能有多条，本次展示其中一条；分段保留原道路编号与来源。"]}
