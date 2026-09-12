#!/usr/bin/env python3
"""Canonical catalog, all-post contracts, executable routing and skill discovery."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import json
import os
import runpy
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "demo"))
sys.path.insert(0, str(ROOT / "scripts"))
os.environ["PYTHON_DOTENV_DISABLED"] = "1"

import catalog_seed
import store
import build_codex_expert_skills as generator
from packing_assistant import expert_capabilities as caps
from packing_assistant.expert_roster import list_experts
from packing_assistant.runtime.expert_skills import catalog_preamble, load_skill, prompt_suffix
from packing_assistant.runtime.tool_engine import get_engine


class CapabilityTests(unittest.TestCase):
    def setUp(self):
        self.seed = caps.load_seed()
        self.rows = {e["id"]: e for e in self.seed["experts"]}
        self.tmp = tempfile.TemporaryDirectory(prefix="civil-capability-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_all_public_expert_fields_and_categories_match_authority(self):
        self.assertEqual(len(self.rows), 66)
        self.assertEqual(len(self.seed["categories"]), 16)
        self.assertEqual(catalog_seed.CATEGORIES, self.seed["categories"])
        for expert in catalog_seed.EXPERTS:
            with self.subTest(expert=expert.id):
                expected = {key: self.rows[expert.id][key] for key in expert.to_dict()}
                self.assertEqual(expert.to_dict(), expected)
        for expert in list_experts():
            self.assertEqual(list(expert.exclusive), self.rows[expert.id]["exclusive"])
            self.assertEqual(expert.risk, self.rows[expert.id]["risk"])

    def test_catalog_consumes_changed_canonical_values_without_a_python_copy(self):
        modified = deepcopy(self.seed)
        modified["experts"][0]["title"] = "独立来源探针"
        modified["experts"][0]["pipeline"] = "探针流程"
        with patch.object(caps, "load_seed", return_value=modified):
            namespace = runpy.run_path(str(ROOT / "demo" / "catalog_seed.py"))
        self.assertEqual(namespace["EXPERTS"][0].title, "独立来源探针")
        self.assertEqual(namespace["EXPERTS"][0].pipeline, "探针流程")
        self.assertNotEqual(catalog_seed.EXPERTS[0].title, "独立来源探针")

    def test_custom_expert_and_builtin_overrides_keep_the_existing_expert_api(self):
        custom = {"id": "user-quality", "name": "用户质量岗", "category": "hse",
                  "title": "用户自定流程", "risk": "high", "aliases": ["自定检查"],
                  "pipeline": "用户步骤甲 → 用户步骤乙"}
        payload = {"experts": [custom], "patches": {"architecture": {
            "name": "本公司建筑岗", "pipeline": "本公司资料 → 本公司审查"}},
            "disabled": ["traffic"]}
        path = self.root / "catalog.json"
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        with patch.object(store, "DATA", path):
            expert = store.get_expert("user-quality")
            self.assertIsInstance(expert, catalog_seed.Expert)
            self.assertFalse(expert.builtin)
            self.assertEqual(expert.pipeline, custom["pipeline"])
            self.assertEqual(expert.aliases, ("自定检查",))
            self.assertEqual(store.get_expert("architecture").name, "本公司建筑岗")
            self.assertIsNone(store.get_expert("traffic"))
        self.assertIsNone(caps.get_capability("user-quality"))
        self.assertEqual(path.read_text(encoding="utf-8"), json.dumps(payload, ensure_ascii=False))

    def test_all_66_contracts_have_distinct_professional_content_and_real_references(self):
        contracts = [e["capability"] for e in self.seed["experts"]]
        for field in ("inputs", "steps", "output_sections", "output_tables", "acceptance", "limitations"):
            self.assertEqual(len({json.dumps(c[field], ensure_ascii=False, sort_keys=True) for c in contracts}), 66,
                             f"{field} unexpectedly collapsed into category boilerplate")
        for row in self.seed["experts"]:
            with self.subTest(expert=row["id"]):
                cap = caps.get_capability(row["id"])
                self.assertEqual(cap["inputs"], row["capability"]["inputs"])
                self.assertTrue(all(tool["available"] for tool in cap["tools"]))
                self.assertTrue(all((ROOT / p).is_file() for p in cap["reference_paths"]))
                self.assertFalse(cap["calculator_connected"])
                self.assertTrue(cap["submit_blocked"])
                self.assertGreaterEqual(len(cap["output_tables"][0]["columns"]), 3)
                self.assertIn("UNSPECIFIED", cap["inputs"][0])

    def test_architecture_hr_bim_and_packing_have_their_specific_completion_conditions(self):
        arch = caps.get_capability("architecture")
        self.assertEqual(len(arch["output_sections"]), 10)
        self.assertIn("专业界面", arch["output_sections"])
        self.assertTrue(any("面积" in check and "[A001]" in check for check in arch["acceptance"]))
        labor = caps.get_capability("hr-labor")
        self.assertTrue({"劳动合同条款", "劳务协议", "派遣三方", "非全日制"} <= set(labor["output_sections"]))
        self.assertTrue(any("补偿[A001]" in check for check in labor["acceptance"]))
        training = caps.get_capability("hr-train")
        self.assertIn("签到空表", training["output_sections"])
        self.assertTrue(any("公司项目班组" in check for check in training["acceptance"]))
        qto = caps.get_capability("bim-qto")
        self.assertIn("重复扣减", qto["output_sections"])
        self.assertTrue(any("数量" in check and "UNSPECIFIED" in check for check in qto["acceptance"]))
        self.assertTrue(any("不扫描IFC" in text for text in caps.get_capability("bim-coord")["limitations"]))
        pack = caps.get_capability("pack-ship")
        self.assertEqual(pack["implementation"], "solver_snapshot_projection")
        self.assertTrue(any("can_fit=false" in text for text in pack["acceptance"]))

    def test_generated_tool_map_is_the_exact_seed_projection(self):
        disk = json.loads((ROOT / "workbench" / "yibiao-map.json").read_text(encoding="utf-8"))
        self.assertEqual(disk, caps.tier_map())
        tools = [name for e in disk["experts"] for name in e["exclusive"]]
        self.assertEqual(len(tools), 70)
        self.assertEqual(len(set(tools)), 70)
        self.assertEqual(disk["generated_from"], "workbench/seed.json")

    def test_real_runtime_plans_match_declared_tools_for_every_post(self):
        from packing_assistant.runtime import agent_loop

        with patch.object(agent_loop, "_OUT", self.root):
            for row in self.seed["experts"]:
                with self.subTest(expert=row["id"]):
                    planned = agent_loop._plan_calls(
                        "准备本岗草稿", expert_id=row["id"], session_id="cap-plan",
                        p0_confirmed=True, packing_summary={}, project_name="契约探针")
                    names = [call["name"] for call in planned["calls"]]
                    self.assertEqual(names, row["capability"]["runtime_tools"])
                    self.assertTrue(all(name in get_engine().tools for name in names))
        self.assertFalse(any(self.root.iterdir()), "Planning may not create business artifacts")

    def test_all_high_risk_plans_require_current_confirmation(self):
        from packing_assistant.runtime import agent_loop

        for row in self.seed["experts"]:
            if row["risk"] != "high":
                continue
            with self.subTest(expert=row["id"]):
                planned = agent_loop._plan_calls(
                    "写本岗草稿", expert_id=row["id"], session_id="cap-gate",
                    p0_confirmed=False, packing_summary=None, project_name="")
                self.assertTrue(planned["hitl"])
                self.assertEqual(planned["calls"], [])

    def test_all_70_exclusive_tools_keep_owner_and_chat_write_gates(self):
        engine = get_engine()
        for row in self.seed["experts"]:
            for name in row["exclusive"]:
                with self.subTest(tool=name):
                    other = "architecture" if row["id"] != "architecture" else "structure"
                    denied = engine.execute(name, {"text": "只做接口验证", "session_id": "cap-owner"},
                                            expert_id=other, intent="run")
                    self.assertFalse(denied["ok"])
                    self.assertEqual(denied["error_code"], "permission_denied")
                    if engine.tools[name].writes:
                        denied = engine.execute(name, {"text": "只聊天", "session_id": "cap-chat"},
                                                expert_id=row["id"], intent="chat")
                        self.assertFalse(denied["ok"])
                        self.assertEqual(denied["error_code"], "permission_denied")

    def test_all_posts_chat_without_writing_business_files(self):
        from packing_assistant import expert_turn, llm

        with patch.object(expert_turn, "_OUT", self.root), patch.object(
            llm, "chat", side_effect=AssertionError("contract tests are offline")
        ):
            for expert in list_experts():
                with self.subTest(expert=expert.id):
                    result = expert_turn.run_expert_turn("这是什么意思，先别写", expert.id)
                    self.assertEqual(result["intent"], "chat")
                    self.assertFalse(result["wrote"])
                    self.assertEqual(result["files"], [])
        self.assertFalse(any(self.root.iterdir()))

    def test_availability_reflects_registration_instead_of_metadata_claims(self):
        engine = get_engine()
        tools = {name: spec for name, spec in engine.tools.items() if name != "architecture__memo"}
        with patch.object(engine, "tools", tools):
            self.assertFalse(caps.get_capability("architecture")["tools"][0]["available"])
        self.assertTrue(caps.get_capability("architecture")["tools"][0]["available"])

    def test_both_skill_mirrors_are_generated_from_full_contracts(self):
        expected = generator.expected_files()
        self.assertEqual(len(expected), 67)
        for eid, content in expected.items():
            with self.subTest(expert=eid):
                for folder in (".agents", ".codex"):
                    self.assertEqual((ROOT / folder / "skills" / eid / "SKILL.md").read_text(encoding="utf-8"), content)
                if eid == "civil-buddy":
                    continue
                cap = self.rows[eid]["capability"]
                self.assertTrue(all(value in content for value in cap["inputs"]))
                self.assertTrue(all(value in content for value in cap["output_sections"]))
                self.assertTrue(all(value in content for value in cap["acceptance"]))
                self.assertLess(len(content), 5000, "Move substantial conditional detail into references")

    def test_discovery_stays_small_and_loads_only_selected_skill(self):
        listing = caps.list_capabilities()
        self.assertEqual(len(listing), 66)
        self.assertTrue(all("inputs" not in row and "output_sections" not in row for row in listing))
        preamble = catalog_preamble()
        selected = prompt_suffix("architecture")
        self.assertIn("architecture__memo", selected)
        self.assertNotIn("geotech__brief", selected)
        self.assertNotIn("architecture__memo", preamble)
        self.assertNotIn("成文十章并核对", preamble)
        self.assertEqual(load_skill("architecture")["name"], "architecture")

    def test_invalid_contracts_cannot_fall_back_to_a_generic_post(self):
        cases = []
        missing = deepcopy(self.seed)
        del missing["experts"][0]["capability"]
        cases.append(missing)
        duplicate = deepcopy(self.seed)
        duplicate["experts"][1]["exclusive"] = list(duplicate["experts"][0]["exclusive"])
        cases.append(duplicate)
        wrong_route = deepcopy(self.seed)
        wrong_route["experts"][0]["capability"]["steps"][0]["tools"] = ["structure__calc_outline"]
        cases.append(wrong_route)
        drift = deepcopy(self.seed)
        drift["experts"][0]["pipeline"] = "unmaintained alternate pipeline"
        cases.append(drift)
        short = deepcopy(self.seed)
        short["experts"][0]["capability"]["acceptance"] = []
        cases.append(short)
        for index, candidate in enumerate(cases):
            with self.subTest(case=index), self.assertRaises(ValueError):
                caps.validate_seed(candidate)

    def test_capability_and_catalog_results_are_independent_copies(self):
        original = caps.get_capability("architecture")
        changed = caps.get_capability("architecture")
        changed["inputs"].clear()
        changed["tools"][0]["available"] = False
        self.assertEqual(caps.get_capability("architecture"), original)
        self.seed["experts"].clear()
        self.assertEqual(len(caps.load_seed()["experts"]), 66)
        for identifier in ("unknown-post", "../architecture", "", None):
            self.assertIsNone(caps.get_capability(identifier))


if __name__ == "__main__":
    unittest.main(verbosity=2)
