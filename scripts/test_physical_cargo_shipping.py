#!/usr/bin/env python3
"""Physical cargo stays whole across gateway confirmation and shipment export.

Synthetic inputs, isolated storage and in-process HTTP only; no model endpoint.
"""
from __future__ import annotations

from copy import deepcopy
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
_TEMP = tempfile.TemporaryDirectory(prefix="cb-physical-cargo-", ignore_cleanup_errors=True)
OUT = Path(_TEMP.name) / "out"
os.environ.update({
    "PYTHON_DOTENV_DISABLED": "1", "PACKING_LLM_AGENT": "0", "PACKING_SKIP_SKJOLBER": "1",
    "CB_STORAGE": "sqlite", "PACKING_OUTPUT_DIR": str(OUT), "PACKING_TRACE_DIR": str(OUT / "traces"),
    "CB_DB_PATH": str(Path(_TEMP.name) / "sessions.db"),
    "PACKING_LG_CHECKPOINT_PATH": str(Path(_TEMP.name) / "checkpoints.db"),
})
for key in [key for key in os.environ if key.endswith("_API_KEY")]:
    os.environ.pop(key)
os.environ.pop("CIVIL_TOKEN", None)

from fastapi.testclient import TestClient  # noqa: E402
import gateway.app as gateway  # noqa: E402
from packing_assistant.export_pack import export_shipment_xlsx, ShipmentSourceError  # noqa: E402
from packing_assistant.tools.cargo_conservation import check_conservation  # noqa: E402

SOLID = {"id": "SYN-SOLID", "name": "One solid member", "quantity": 1, "weight_kg": 2000,
         "length_mm": 1200, "width_mm": 120, "height_mm": 100, "note": "Batch 3; painted blue"}
OPTIONS = {"max_box_net_kg": 1500, "clearance_mm": 0, "multi_start": False,
           "standard_boxes": True, "force_dense_sheets": False, "crate_passthrough": False}


class PhysicalCargoShippingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(gateway.app)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()

    def pipeline(self, sid, row, auto):
        response = self.client.post("/api/pipeline", json={
            "user_input": "Synthetic packing check", "session_id": sid, "materials": [row],
            "preset": "", "mode": "steps", "enable_auto_confirm": auto, "save_artifacts": False,
            "container_type": "40HQ", "packing_options": OPTIONS,
        })
        self.assertEqual(response.status_code, 200, response.text)
        return response.json().get("public", response.json())

    def assert_export_refused(self, sid):
        before = set((OUT / "exports").glob("*"))
        response = self.client.post("/api/export/shipment", json={"session_id": sid})
        self.assertEqual(response.status_code, 409, response.text)
        self.assertIn("出运单未导出", response.json()["detail"])
        self.assertEqual(set((OUT / "exports").glob("*")), before)

    def test_virtual_piece_refused_after_auto_and_human_confirmation(self):
        for auto in (False, True):
            with self.subTest(auto=auto):
                sid = "synthetic-solid-" + str(auto)
                state = self.pipeline(sid, SOLID, auto)
                self.assertFalse(state["ship_ok"])
                refusal = state["needs_human"][0]
                self.assertEqual(refusal["reason"], "physical_split_not_authorized")
                for key, value in SOLID.items():
                    self.assertEqual(refusal["source_material"][key], value)
                if not auto:
                    self.assertEqual(state["phase"], "await_user_confirm")
                    response = self.client.post("/api/confirm", json={
                        "session_id": sid, "action": "confirm", "container_type": "40HQ"})
                    self.assertEqual(response.status_code, 200, response.text)
                    state = response.json().get("public", response.json())
                self.assertFalse(state["ship_ok"])
                self.assertFalse(state["container_plan"]["can_fit"])
                self.assertEqual(state["container_plan"]["layout"], [])
                self.assertEqual(state["needs_human"][0]["reason"], "physical_split_not_authorized")
                self.assert_export_refused(sid)

    def test_conflicting_weights_refuse_pipeline_and_export(self):
        row = dict(SOLID, total_weight_kg=1000)
        state = self.pipeline("synthetic-weight-conflict", row, True)
        self.assertFalse(state["ship_ok"])
        self.assertEqual(state["needs_human"][0]["reason"], "source_weight_mismatch")
        self.assertEqual(state.get("boxes") or [], [])
        for key, value in row.items():
            self.assertEqual(state["needs_human"][0]["source_material"][key], value)
        self.assert_export_refused("synthetic-weight-conflict")

    def test_cached_success_cannot_authorize_export_or_overwrite_output(self):
        for conflict in (False, True):
            with self.subTest(conflict=conflict):
                row = dict(SOLID, **({"total_weight_kg": 1000} if conflict else {}))
                state = {"materials": [row], "ship_ok": True,
                         "container_plan": {"can_fit": True, "containers_used": 1},
                         "por_manifest": {"by_part": [{"part_no": "OLD", "total_kg": 1000}]},
                         "secure_work_order": {"items": []},
                         "boxes": [] if conflict else [{"contents": [{"source_material_id": "SYN-SOLID", "split_of": 2}]}]}
                before = deepcopy(state)
                folder = OUT / ("cached-" + str(conflict))
                folder.mkdir(parents=True)
                sentinel = folder / "existing.txt"
                sentinel.write_text("keep existing output")
                with self.assertRaises(ShipmentSourceError):
                    export_shipment_xlsx(state, output_dir=folder)
                self.assertEqual(state, before)
                self.assertEqual(list(folder.iterdir()), [sentinel])
                self.assertEqual(sentinel.read_text(), "keep existing output")
                # The gateway must map the same restored state to 409, too.
                sid = "cached-success-" + str(conflict)
                gateway._SESSIONS[sid] = deepcopy(state)
                self.assert_export_refused(sid)

    def test_whole_pieces_with_general_notes_still_pack_and_export(self):
        row = dict(SOLID, quantity=2, weight_kg=1000, total_weight_kg=2000)
        sid = "synthetic-whole-pieces"
        state = self.pipeline(sid, row, True)
        self.assertTrue(state["container_plan"]["can_fit"])
        stored = gateway._get_session(sid)
        ledger = check_conservation(stored["materials"], stored["boxes"])
        self.assertTrue(ledger["ok"])
        self.assertEqual(ledger["pieces_out"], 2)
        self.assertEqual(ledger["kg_out"], 2000)
        self.assertEqual(ledger["mass_split_rows"], [])
        self.assertFalse(state.get("needs_human"))
        response = self.client.post("/api/export/shipment", json={"session_id": sid})
        self.assertEqual(response.status_code, 200, response.text)
        file = Path(response.json()["xlsx_path"])
        file.resolve().relative_to(OUT.resolve())
        self.assertTrue(file.is_file())
        download = self.client.get(response.json()["download_url"])
        self.assertEqual(download.status_code, 200)
        self.assertTrue(download.content.startswith(b"PK"))


if __name__ == "__main__":
    unittest.main()
