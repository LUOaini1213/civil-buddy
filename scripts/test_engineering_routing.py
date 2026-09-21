"""Offline routing tests: real NetworkX, road provenance, and HTTP isolation."""
from copy import deepcopy
import os
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["PYTHON_DOTENV_DISABLED"] = "1"
from fastapi import FastAPI
from fastapi.testclient import TestClient
from demo import routing_api
from packing_assistant.engineering import routing
from packing_assistant.runtime import cancel


def fixture():
    return {"source": "synthetic", "metric": "distance_m", "origin": "A", "destination": "D",
            "nodes": [{"id": ident, "name": "Synthetic " + ident} for ident in "ABCD"],
            "edges": [{"id": ident, "from": first, "to": last, "weight": weight,
                       "bidirectional": True, "closed": False, "source": "Synthetic test road"}
                      for ident, first, last, weight in [("AB", "A", "B", 4), ("BD", "B", "D", 4),
                                                       ("AC", "A", "C", 2), ("CD", "C", "D", 3)]]}


class RoutingTests(unittest.TestCase):
    def test_shortest_distance_and_source_edge_trace(self):
        model = fixture(); before = deepcopy(model)
        result = routing.calculate_route(model)
        self.assertEqual(model, before)
        self.assertTrue(result["route_found"])
        self.assertEqual(result["path_node_ids"], ["A", "C", "D"])
        self.assertEqual(result["total_weight"], 5)
        self.assertEqual(result["unit"], "m")
        self.assertEqual([row["edge_id"] for row in result["segments"]], ["AC", "CD"])
        self.assertTrue(all(row["source"] == "Synthetic test road" for row in result["segments"]))
        self.assertEqual(result["engine"]["name"], "NetworkX")

    def test_closure_reroutes_then_reports_unreachable(self):
        model = fixture(); model["edges"][3]["closed"] = True
        result = routing.calculate_route(model)
        self.assertEqual(result["total_weight"], 8)
        self.assertEqual(result["path_node_ids"], ["A", "B", "D"])
        self.assertEqual(result["excluded_edge_ids"], ["CD"])
        model["edges"][1]["closed"] = True
        result = routing.calculate_route(model)
        self.assertFalse(result["route_found"])
        self.assertIsNone(result["total_weight"])
        self.assertEqual(result["segments"], [])

    def test_one_way_reverse_and_identity_route(self):
        model = fixture(); model["origin"], model["destination"] = "D", "A"
        for edge in model["edges"]:
            edge["bidirectional"] = False
        self.assertFalse(routing.calculate_route(model)["route_found"])
        model["edges"][3]["bidirectional"] = model["edges"][2]["bidirectional"] = True
        result = routing.calculate_route(model)
        self.assertEqual(result["total_weight"], 5)
        self.assertTrue(all(row["reversed"] for row in result["segments"]))
        model["destination"] = model["origin"]
        result = routing.calculate_route(model)
        self.assertEqual(result["path_node_ids"], ["D"])
        self.assertEqual(result["total_weight"], 0)

    def test_parallel_roads_return_exact_edge_and_fixed_time_units(self):
        model = fixture(); model["metric"] = "travel_time_min"
        model["edges"].append({**model["edges"][2], "id": "EXPRESS", "weight": 1, "source": "Synthetic stopwatch entry"})
        result = routing.calculate_route(model)
        self.assertEqual(result["total_weight"], 4)
        self.assertEqual(result["unit"], "min")
        self.assertEqual(result["segments"][0]["edge_id"], "EXPRESS")
        self.assertEqual(result["segments"][0]["source"], "Synthetic stopwatch entry")

    def test_invalid_weights_ids_and_permissions_are_rejected(self):
        for value in [-1, 0, True, "5", float("nan"), float("inf"), 10**1000]:
            model = fixture(); model["edges"][0]["weight"] = value
            with self.subTest(weight=str(value)[:25]), self.assertRaises(ValueError):
                routing.validate_route(model)
        for mutate in [lambda m: m.update(code="arbitrary-code"),
                       lambda m: m["nodes"][0].update(x=123),
                       lambda m: m["edges"][0].update(filename="../road.csv"),
                       lambda m: m["nodes"].append(m["nodes"][0]),
                       lambda m: m["edges"].append(m["edges"][0]),
                       lambda m: m["edges"][0].update(closed="false"),
                       lambda m: m["edges"][0].update(source=""),
                       lambda m: m["edges"][0].update(to="UNKNOWN"),
                       lambda m: m.update(origin="UNKNOWN")]:
            model = fixture(); mutate(model)
            with self.assertRaises(ValueError): routing.validate_route(model)

    def test_algorithm_cancellation_never_returns_late_result(self):
        import networkx as nx
        original = nx.shortest_path
        event = threading.Event()
        def finish_then_cancel(*args, **kwargs):
            result = original(*args, **kwargs)
            event.set()
            return result
        with cancel.scope(event=event), patch.object(nx, "shortest_path", finish_then_cancel):
            with self.assertRaises(cancel.RunCancelled): routing.calculate_route(fixture())
        self.assertEqual(routing.calculate_route(fixture())["total_weight"], 5)


class RoutingHTTPTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI(); app.include_router(routing_api.router)
        self.client = TestClient(app); self.addCleanup(self.client.close)

    def test_page_real_calculation_and_origin_gate(self):
        page = self.client.get("/engineering/routes")
        self.assertEqual(page.status_code, 200)
        self.assertEqual(page.headers["cache-control"], "no-cache")
        response = self.client.post("/api/engineering/routes/calculate", json={"model": fixture()})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["total_weight"], 5)
        response = self.client.post("/api/engineering/routes/calculate", json={"model": fixture()}, headers={"Origin": "https://outside.invalid"})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.client.post("/api/engineering/routes/calculate", json={"model": fixture(), "path": "../x"}).status_code, 422)

    def test_precancel_does_not_dispatch_and_new_operation_succeeds(self):
        identifier = "e" * 32
        self.assertEqual(self.client.post(f"/api/engineering/routes/operations/{identifier}/cancel").status_code, 200)
        with patch.object(routing, "calculate_route") as solver:
            response = self.client.post("/api/engineering/routes/calculate", json={"model": fixture()}, headers={"X-CAD-Operation-ID": identifier})
            self.assertEqual(response.status_code, 499, response.text)
            solver.assert_not_called()
        response = self.client.post("/api/engineering/routes/calculate", json={"model": fixture()}, headers={"X-CAD-Operation-ID": "f" * 32})
        self.assertEqual(response.status_code, 200, response.text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
