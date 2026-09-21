"""Offline IFC/IDS acceptance using actual libraries and synthetic IFC data."""
from __future__ import annotations

import base64
from contextlib import redirect_stdout
from copy import deepcopy
import hashlib
import importlib.util
import io
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["PYTHON_DOTENV_DISABLED"] = "1"

from packing_assistant.engineering.ifc import _source, _model, check_model, compare_models, synthetic_examples

AVAILABLE = all(importlib.util.find_spec(name) is not None for name in ("ifcopenshell", "ifctester", "ifcdiff", "defusedxml"))


def source(raw, name="model.ifc"):
    return {"name": name, "data_b64": base64.b64encode(raw).decode("ascii")}


class UploadValidation(unittest.TestCase):
    def test_only_bounded_file_contents_with_plain_names_are_accepted(self):
        invalid = [source(b"ok", "../model.ifc"), source(b"ok", "C:model.ifc"),
                   source(b"ok", "model\n.ifc"), source(b"ok", "model.ifc\x00"),
                   source(b"ok", "model.dwg"), source(b""), source(b"a" * 20),
                   {"name": "model.ifc", "data_b64": "!!!!"},
                   {"name": "model.ifc", "data_b64": False},
                   {"name": "model.ifc", "data_b64": "eA==", "path": "outside"}]
        for item in invalid:
            with self.subTest(item=item), self.assertRaises(ValueError):
                _source(item, ".ifc", 10)
        raw, info = _source(source(b"actual bytes"), ".ifc", 20)
        self.assertEqual(info["sha256"], hashlib.sha256(raw).hexdigest())


@unittest.skipUnless(AVAILABLE, "Install optional requirements-engineering.txt for IFC acceptance")
class ActualIfcAcceptance(unittest.TestCase):
    def setUp(self):
        import ifcopenshell
        self.ifc = ifcopenshell
        self.files = synthetic_examples()

    @staticmethod
    def guid(number):
        import ifcopenshell.guid
        return ifcopenshell.guid.compress(f"{number:032x}")

    def compare(self, old, new):
        with redirect_stdout(io.StringIO()):
            return compare_models({"old": source(old.to_string().encode()), "new": source(new.to_string().encode())})

    def test_ids_failure_contains_actual_entity_and_reason_then_passes(self):
        inputs = {"ifc": source(self.files["old.ifc"]), "ids": source(self.files["requirements.ids"], "rules.ids")}
        before = deepcopy(inputs)
        failure = check_model(inputs)
        self.assertFalse(failure["report"]["status"])
        failed = failure["report"]["specifications"][0]["requirements"][0]["failed_entities"][0]
        self.assertEqual(failed["global_id"], self.guid(int("1" * 32, 16)))
        self.assertTrue(failed["reason"])
        self.assertEqual(inputs, before)
        inputs["ifc"] = source(self.files["new.ifc"])
        passed = check_model(inputs)
        self.assertTrue(passed["report"]["status"])
        self.assertEqual(passed["source"]["sha256"], hashlib.sha256(self.files["new.ifc"]).hexdigest())

    def test_ifc_added_deleted_attributes_properties_spaces_and_openings(self):
        model = self.ifc.file(schema="IFC4")
        walls = [model.create_entity("IfcWall", GlobalId=self.guid(i), Name=f"Wall {i}") for i in (1, 2, 3)]
        model.create_entity("IfcSpace", GlobalId=self.guid(4), Name="Room")
        model.create_entity("IfcOpeningElement", GlobalId=self.guid(5), Name="Opening")
        prop = model.create_entity("IfcPropertySingleValue", Name="FireRating", NominalValue=model.create_entity("IfcLabel", "old"))
        pset = model.create_entity("IfcPropertySet", GlobalId=self.guid(8), Name="Pset_WallCommon", HasProperties=[prop])
        model.create_entity("IfcRelDefinesByProperties", GlobalId=self.guid(9), RelatedObjects=[walls[2]], RelatingPropertyDefinition=pset)
        newer = self.ifc.file.from_string(model.to_string())
        newer.by_guid(self.guid(1)).Name = "changed"
        newer.remove(newer.by_guid(self.guid(2)))
        newer.create_entity("IfcWall", GlobalId=self.guid(6), Name="Added")
        newer.by_type("IfcPropertySingleValue")[0].NominalValue = newer.create_entity("IfcLabel", "new")
        newer.by_guid(self.guid(5)).Name = "Opening also changed"
        newer.create_entity("IfcOpeningElement", GlobalId=self.guid(7), Name="New opening")
        result = self.compare(model, newer)
        self.assertEqual([e["global_id"] for e in result["added"]], [self.guid(6)])
        self.assertEqual([e["global_id"] for e in result["deleted"]], [self.guid(2)])
        changed = {e["global_id"]: e for e in result["changed"]}
        self.assertEqual(set(changed), {self.guid(1), self.guid(3)})
        self.assertTrue(changed[self.guid(1)]["changes"]["attributes_changed"])
        self.assertTrue(changed[self.guid(3)]["changes"]["properties_changed"])
        self.assertEqual(result["unchanged_count"], 1)
        self.assertTrue(any("IfcFeatureElement" in note for note in result["notes"]))

    def test_unchanged_spatial_objects_count_in_both_supported_schema_families(self):
        for schema in ("IFC4", "IFC2X3"):
            with self.subTest(schema=schema):
                model = self.ifc.file(schema=schema)
                model.create_entity("IfcSpace", GlobalId=self.guid(1), Name="Room")
                model.create_entity("IfcOpeningElement", GlobalId=self.guid(2), Name="Opening")
                result = self.compare(model, model)
                self.assertEqual(result["unchanged_count"], 1)
                self.assertEqual(result["changed"], [])

    def test_no_common_ids_gives_warning_without_guessing_matches(self):
        old = self.ifc.file(schema="IFC4"); newer = self.ifc.file(schema="IFC4")
        old.create_entity("IfcWall", GlobalId=self.guid(1), Name="Same text")
        newer.create_entity("IfcWall", GlobalId=self.guid(2), Name="Same text")
        result = self.compare(old, newer)
        self.assertEqual(len(result["added"]), 1); self.assertEqual(len(result["deleted"]), 1)
        self.assertEqual(result["unchanged_count"], 0)
        self.assertIn("没有共同", result["notes"][0])

    def test_duplicate_missing_or_invalid_global_ids_are_rejected(self):
        for invalid in (self.guid(1), None, "not-a-guid", "9" * 22):
            with self.subTest(global_id=invalid):
                model = self.ifc.file(schema="IFC4")
                model.create_entity("IfcWall", GlobalId=self.guid(1))
                # Model the missing required value in the uploaded STEP text:
                # the entity setter itself correctly refuses assigning None.
                model.create_entity("IfcWall", GlobalId=self.guid(2) if invalid is None else invalid)
                text = model.to_string()
                if invalid is None:
                    text = text.replace(f"'{self.guid(2)}'", "$", 1)
                with self.assertRaisesRegex(ValueError, "GlobalId"):
                    _model(source(text.encode()))

    def test_bad_ifc_or_cross_schema_diff_is_rejected(self):
        truncated = self.files["old.ifc"].replace(b"END-ISO-10303-21;", b"")
        for raw in (b"not ifc", b"ISO-10303-21; broken data", b"\xff", truncated):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                _model(source(raw))
        model, _ = _model(source(self.files["old.ifc"] + b"\n/* valid trailing comment */\n"))
        self.assertEqual(model.schema, "IFC4")
        with self.assertRaisesRegex(ValueError, "相同 IFC schema"):
            self.compare(self.ifc.file(schema="IFC4"), self.ifc.file(schema="IFC2X3"))

    def test_ids_dtd_xxe_bad_namespace_and_empty_rules_never_validate(self):
        base = self.files["requirements.ids"].decode()
        attack = b'<!DOCTYPE ids [<!ENTITY xxe SYSTEM "file:///does-not-exist/secret">]><ids xmlns="http://standards.buildingsmart.org/IDS">&xxe;</ids>'
        cases = [attack, b'<ids xmlns="https://untrusted.invalid/IDS"/>',
                 b'<ids xmlns="http://standards.buildingsmart.org/IDS"/>', b'<broken>']
        for raw in cases:
            with self.subTest(raw=raw), patch("ifctester.ids.Ids.validate") as validate:
                with self.assertRaisesRegex(ValueError, "IDS 内容无效"):
                    check_model({"ifc": source(self.files["old.ifc"]), "ids": source(raw, "bad.ids")})
                validate.assert_not_called()
        self.assertIn("specifications", base)

    def test_extra_fields_or_arbitrary_paths_are_not_tools(self):
        with self.assertRaises(ValueError):
            check_model({"ifc": source(self.files["old.ifc"]), "ids": {"path": "../rules.ids"}})
        with self.assertRaises(ValueError):
            compare_models({"old": source(self.files["old.ifc"]), "new": source(self.files["new.ifc"]), "code": "print(1)"})


if __name__ == "__main__":
    unittest.main()
