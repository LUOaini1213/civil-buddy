"""Optional STEP export: units, through-holes, reopen checks, and cancellation."""
from copy import deepcopy
import io
import json
import os
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["PYTHON_DOTENV_DISABLED"] = "1"
from packing_assistant.cad3d import step
from packing_assistant.cad3d.geometry import inspect_dxf, build_model
from packing_assistant.runtime import cancel


class MissingStepTests(unittest.TestCase):
    def test_optional_dependency_has_clear_install_hint(self):
        with patch.object(step, "available", return_value=False):
            with self.assertRaisesRegex(ValueError, "requirements-cad-step"):
                step.export_step({})


@unittest.skipUnless(step.available(), "optional CadQuery not installed")
class StepTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        folder = ROOT / "examples/cad-to-3d"
        doc = inspect_dxf((folder / "synthetic-hollow-section-mm.dxf").read_bytes(), "fixture.dxf")
        cfg = json.loads((folder / "synthetic-section-config.json").read_text(encoding="utf-8"))
        cls.model = build_model(doc, cfg)

    def test_reopens_true_solids_with_same_hole_volume_and_dimensions(self):
        import cadquery as cq
        from OCP.STEPControl import STEPControl_Reader
        from OCP.IFSelect import IFSelect_RetDone
        payload = step.export_step(self.model)
        self.assertTrue(payload.startswith(b"ISO-10303-21"))
        reader = STEPControl_Reader()
        self.assertEqual(reader.ReadStream("fixture.step", io.BytesIO(payload)), IFSelect_RetDone)
        reader.TransferRoots()
        shape = cq.Shape.cast(reader.OneShape())
        self.assertTrue(shape.isValid())
        self.assertEqual(len(shape.Solids()), len(self.model["objects"]))
        self.assertAlmostEqual(shape.Volume() / 1e9, sum(row["volume_m3"] for row in self.model["objects"]), places=9)
        box = shape.BoundingBox()
        for name, axis in (("xlen",0),("ylen",1),("zlen",2)):
            self.assertAlmostEqual(getattr(box,name) / 1000, self.model["bounds"]["max"][axis] - self.model["bounds"]["min"][axis], places=7)
        # Through-hole makes more than the six faces of a solid rectangular bar.
        self.assertGreater(len(shape.Faces()), 6)

    def test_volume_tampering_and_unbounded_work_rejected(self):
        wrong = deepcopy(self.model); wrong["objects"][0]["volume_m3"] *= 2
        with self.assertRaisesRegex(ValueError,"体积"): step.export_step(wrong)
        with patch.object(step, "MAX_STEP_VERTICES", 2):
            with self.assertRaisesRegex(ValueError,"预算"): step.export_step(self.model)

    def test_cancel_never_serializes_and_other_call_is_unaffected(self):
        event = threading.Event(); event.set()
        with cancel.scope(event=event):
            with self.assertRaises(cancel.RunCancelled): step.export_step(self.model)
        self.assertTrue(step.export_step(self.model).startswith(b"ISO-10303-21"))


if __name__ == "__main__": unittest.main()
