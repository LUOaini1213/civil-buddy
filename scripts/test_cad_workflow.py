"""Selections, source dimensions and staged imports survive project handoff."""
from copy import deepcopy
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["PYTHON_DOTENV_DISABLED"] = "1"
import ezdxf
from packing_assistant.cad3d.geometry import inspect_dxf, build_model, analyze_document
from packing_assistant.cad3d.dimensions import bind_dimension
from packing_assistant.cad3d.projects import CadProjectStore


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / "output", prefix="cad-workflow-")
        self.addCleanup(self.temp.cleanup)
        self.store = CadProjectStore(Path(self.temp.name) / "projects")
        env = patch.dict(os.environ, {"CIVIL_SANDBOX": "workspace-write"})
        env.start(); self.addCleanup(env.stop)
        drawing = ezdxf.new("R2010"); drawing.units = 4
        drawing.layers.new("SECTION"); drawing.layers.new("NOTES")
        space = drawing.modelspace()
        def rectangle(x, y, w, h):
            return space.add_lwpolyline([(x,y),(x+w,y),(x+w,y+h),(x,y+h)], close=True, dxfattribs={"layer":"SECTION"}).dxf.handle
        self.shell = rectangle(0, 0, 50, 153)
        self.hole = rectangle(5, 5, 40, 143)
        self.frame = rectangle(-100, -100, 400, 500)
        space.add_text("not material", dxfattribs={"layer":"NOTES"})
        dimension = space.add_linear_dim(base=(0, -20), p1=(0,0), p2=(1200,0), text="1200", dxfattribs={"layer":"NOTES"})
        dimension.render(); self.dimension = dimension.dimension.dxf.handle
        stream = io.StringIO(); drawing.write(stream); self.source = stream.getvalue().encode("utf-8")
        self.doc = inspect_dxf(self.source, "synthetic-selected-section.dxf")
        self.cfg = {"mode":"section","unit":"mm","confirmed_solid":True,
                    "layers":{"SECTION":"section","NOTES":"ignore"},
                    "parameters":{"section":{"height_m":None,"base_m":0}}, "overrides":{},
                    "selection":{"include_ids":[self.shell,self.hole],"exclude_ids":[self.frame],
                                 "groups":[{"name":"chosen section","entity_ids":[self.shell,self.hole]}]}}
        self.cfg = bind_dimension(self.doc,self.cfg,{"dimension_id":self.dimension,"role":"section",
                         "parameter":"height_m","value_source":"annotation"})["config"]

    def save(self, doc=None, cfg=None, model=None):
        return self.store.save(name="selected fixture", document=doc or self.doc, source=self.source,
                               draft_config=cfg or self.cfg, model=model)

    def test_selected_hole_and_binding_survive_restart_and_handoff(self):
        model = build_model(self.doc, self.cfg)
        self.assertEqual(len(model["objects"]), 1)
        self.assertEqual(model["objects"][0]["hole_count"], 1)
        self.assertAlmostEqual(model["objects"][0]["volume_m3"], .001930 * 1.2)
        model["source"] = {key:self.doc[key] for key in ("filename","sha256","units")}
        saved = self.save(model=model)
        script = "from pathlib import Path; import json,sys; from packing_assistant.cad3d.projects import CadProjectStore; print(json.dumps(CadProjectStore(Path(sys.argv[1])).open(sys.argv[2])))"
        proc = subprocess.run([sys.executable,"-c",script,str(self.store.root),saved["id"]], cwd=ROOT,
                              capture_output=True,text=True,encoding="utf-8",timeout=40,check=True)
        fresh = json.loads(proc.stdout)
        self.assertEqual(fresh["model"], model)
        other = CadProjectStore(Path(self.temp.name) / "colleague")
        copied = other.import_bundle(self.store.export_bundle(saved["id"]))
        self.assertNotEqual(copied["project"]["id"], saved["id"])
        self.assertTrue(copied["confirmation_reset"])
        self.assertEqual(copied["model"], model)
        self.assertEqual(copied["draft_config"]["dimension_bindings"], self.cfg["dimension_bindings"])

    def test_incomplete_selected_draft_reopens_without_fabricated_length(self):
        cfg = deepcopy(self.cfg); cfg["dimension_bindings"] = []
        cfg["parameters"]["section"]["height_m"] = None
        saved = self.save(cfg=cfg)
        reopened = self.store.open(saved["id"])
        self.assertNotIn("model", reopened)
        self.assertIsNone(reopened["draft_config"]["parameters"]["section"]["height_m"])
        report = analyze_document(reopened["document"], reopened["draft_config"])
        self.assertEqual(len(report["contours"]), 1)
        self.assertEqual(report["contours"][0]["hole_ids"], [self.hole])

    def test_staged_source_filter_is_saved_and_replayed(self):
        filtered = inspect_dxf(self.source, "synthetic-selected-section.dxf", source_filter={"layers":["SECTION"]})
        cfg = deepcopy(self.cfg); cfg["dimension_bindings"] = []; cfg["layers"].pop("NOTES")
        saved = self.save(doc=filtered, cfg=cfg)
        reopened = self.store.open(saved["id"])
        self.assertEqual(reopened["document"]["sha256"], self.doc["sha256"])
        self.assertEqual(reopened["document"]["source_filter"], filtered["source_filter"])
        self.assertEqual(self.store.source(saved["id"]), self.source)
        other = CadProjectStore(Path(self.temp.name) / "colleague")
        copied = other.import_bundle(self.store.export_bundle(saved["id"]))
        self.assertEqual(copied["document"]["source_filter"], filtered["source_filter"])

    def test_forged_selection_or_dimension_is_not_saved(self):
        for field, value in (("selection", {"include_ids":["invented"]}),
                             ("dimension_bindings",[{"dimension_id":"missing","role":"section","parameter":"height_m","value_source":"annotation"}])):
            cfg = deepcopy(self.cfg); cfg[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError): self.save(cfg=cfg)
        self.assertEqual(self.store.list_projects(), [])

    def test_click_order_does_not_prevent_saving_generated_model(self):
        cfg = deepcopy(self.cfg)
        cfg["selection"] = {"include_ids":[self.hole,self.shell]}
        model = build_model(self.doc, cfg)
        model["source"] = {key:self.doc[key] for key in ("filename","sha256","units")}
        saved = self.save(cfg=cfg, model=model)
        reopened = self.store.open(saved["id"])
        self.assertEqual(reopened["model"], model)
        self.assertEqual(reopened["draft_config"]["selection"], model["config"]["selection"])


if __name__ == "__main__": unittest.main()
