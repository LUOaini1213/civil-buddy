#!/usr/bin/env python3
"""The tender and the packing as one linked run (packing_assistant/tender_packing_link.py), on SYNTHETIC files.

  container   the plan is made in the type the tender's clause names (40HQ, and 40GP for a variant), 40HQ by default
              when it names none (said so); a type the planner cannot model gets no plan and goes to a person
  mass        a per-container mass clause is checked against the plan's per-container figures: within the limit,
              over it (gap), and on a cargo-only basis
  never       securing / lashing (CTU Code), A-frame stillages / upright / no stacking and delivery sequencing are never
              "covered"; crate structure pending detailed design stays with a person
  linked      a changed panel list (rev B) re-run names the statements that changed (containers 6 -> 8) and the inputs
              that moved; the same inputs change nothing; a clause removed from the tender withdraws its statement
  entry       English and Chinese trigger phrases reach it in steps mode (no model key) and write the matrix, the
              English bid-book and tender-packing-link.json; pack-ship takes the container type typed in the request
  gateway     /api/tender/delivery says materials_source = "sample" when it packs its canned materials, and takes the
              container type from the tender when the request gives none
  demo        scripts/demo_facade.py exits 0 and prints the link
No model and no network.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["PYTHON_DOTENV_DISABLED"] = "1"
for _key in [k for k in os.environ if k.endswith("_API_KEY")] + ["CIVIL_SANDBOX", "CIVIL_APPROVAL", "CIVIL_JOB_ROOT"]:
    os.environ.pop(_key, None)
os.environ["CIVIL_AGENT_MODE"] = "steps"

FIXTURES = ROOT / "examples" / "facade-demo"
ITT = (FIXTURES / "facade_itt_doc.md").read_text(encoding="utf-8")
CONTAINER_CLAUSE = "4.8 Containers: panels fabricated overseas shall be shipped and delivered to site in 40HQ (40 ft high cube) containers."
MASS_CLAUSE = ("4.9 Container gross mass: the gross mass of each loaded container, including the container tare, shall not exceed "
               "20,000 kg to suit the site hoisting and road haulage arrangements.")
SEQUENCE_CLAUSE = ("4.11 Delivery sequence: deliveries shall be sequenced to the approved installation programme, floor by floor, "
                   "and each delivery shall be notified to the Main Contractor 48 hours in advance.")
HANDLING_CLAUSE = ("4.7 Packing and delivery: unitised panels shall be transported upright on steel A-frame stillages with the "
                   "glass faces protected; glazed panels shall not be stacked.")


def variant(**replace: str) -> str:
    text = ITT
    for old, new in replace.items():
        clause = {"container": CONTAINER_CLAUSE, "mass": MASS_CLAUSE, "sequence": SEQUENCE_CLAUSE, "handling": HANDLING_CLAUSE}[old]
        assert clause in text, old
        text = text.replace(clause, new)
    return text


class Link(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from packing_assistant.runtime import workspace

        cls.tmp = tempfile.TemporaryDirectory(prefix="tender-link-test-")
        cls.job = Path(cls.tmp.name).resolve() / "job"
        (cls.job / "inputs").mkdir(parents=True)
        for name in ("facade_itt_doc.md", "facade_panels.xlsx", "facade_panels_rev_b.xlsx"):
            shutil.copyfile(FIXTURES / name, cls.job / name)
        variants = {
            "itt_40gp.md": variant(container=CONTAINER_CLAUSE.replace("40HQ (40 ft high cube)", "40GP")),
            "itt_open_top.md": variant(container=CONTAINER_CLAUSE.replace("40HQ (40 ft high cube)", "40 ft open top")),
            "itt_no_type.md": variant(container="4.8 Containers: panels fabricated overseas shall be shipped to site in containers."),
            "itt_mass_6t.md": variant(mass=MASS_CLAUSE.replace("20,000 kg", "6,000 kg")),
            "itt_payload.md": variant(mass="4.9 Container payload: the maximum payload of each loaded container shall not exceed 2,500 kg."),
            "itt_plain.md": variant(handling="4.7 Packing: panels shall be packed in crates."),
            "itt_no_sequence.md": variant(sequence="4.11 Deliveries shall be notified to the Main Contractor in advance."),
        }
        for name, text in variants.items():
            (cls.job / name).write_text(text, encoding="utf-8")
        (cls.job / "CIVIL.md").write_text("# CIVIL.md\n\n- 项目：合成示例办公楼幕墙分包\n- 辖区：SG\n", encoding="utf-8")
        cls.cwd = Path.cwd()
        home = patch.object(Path, "home", return_value=Path(cls.tmp.name) / "no-home")
        home.start()
        cls.addClassCleanup(home.stop)
        os.chdir(cls.job)
        workspace.activate(cls.job)

    @classmethod
    def tearDownClass(cls):
        from packing_assistant.runtime import workspace

        workspace.deactivate()
        os.chdir(cls.cwd)
        cls.tmp.cleanup()

    def link(self, tender: str = "facade_itt_doc.md", panels: str = "facade_panels.xlsx", previous=None):
        from packing_assistant.tender_packing_link import run_link

        return run_link(str(self.job / tender), str(self.job / panels), previous=previous)

    @staticmethod
    def by_kind(out):
        return {s["kind"]: s for s in out["statements"]}

    # container type ------------------------------------------------------------------------------------------
    def test_plan_is_made_in_the_type_the_clause_names(self):
        out = self.link()
        record = out["record"]
        self.assertEqual(record["container"], {"type": "40HQ", "source": "tender_clause", "clause": "4.8",
                                               "reason": "Container type 40HQ taken from Clause 4.8."})
        self.assertEqual(out["plan"]["container_type"], "40HQ")
        self.assertEqual(self.by_kind(out)["container_type"]["status"], "covered")
        other = self.link("itt_40gp.md")
        self.assertEqual(other["record"]["container"]["type"], "40GP")
        self.assertEqual(other["plan"]["container_type"], "40GP")          # not the 40HQ default
        self.assertEqual(self.by_kind(other)["container_type"]["figures"]["plan_container_type"], "40GP")

    def test_no_type_in_the_tender_is_the_default_said_so(self):
        out = self.link("itt_no_type.md")
        self.assertEqual(out["record"]["container"]["source"], "default")
        self.assertIn("names no container type", out["record"]["container"]["reason"])
        row = self.by_kind(out)["container_type"]
        self.assertEqual(row["status"], "human_required")
        self.assertIn("planner's default", row["text"])
        self.assertIsNone(row["clause"])

    def test_a_type_the_planner_cannot_model_gets_no_plan(self):
        out = self.link("itt_open_top.md")
        record = out["record"]
        self.assertIsNone(record["container"]["type"])
        self.assertIn("40OT", record["container"]["reason"])
        self.assertIsNone(out["plan"])
        self.assertIsNone(record["plan"])
        self.assertIsNone(record["inputs"]["plan"]["sha256"])
        self.assertTrue(all(s["status"] != "covered" for s in out["statements"]), out["statements"])
        self.assertTrue(self.by_kind(out)["containers_used"]["placeholder"])
        self.assertIn("No plan", out["reply"])
        self.assertNotIn("pack-plan.json", [d["name"] for d in out["deliverables"]])

    # mass ----------------------------------------------------------------------------------------------------
    def test_mass_clause_is_checked_per_container(self):
        row = self.by_kind(self.link())["gross_mass"]
        f = row["figures"]
        self.assertEqual((f["limit_kg"], f["limit_basis"], f["max_cargo_kg"], f["container_tare_kg"], f["max_gross_kg"]),
                         (20000.0, "gross", 2582.8, 3890.0, 6472.8))
        self.assertEqual(f["margin_kg"], 13527.2)
        self.assertEqual(row["status"], "partial")            # A-frame stillage mass (4.7) is not in the figure
        self.assertIn("[TO CONFIRM", row["text"])
        over = self.by_kind(self.link("itt_mass_6t.md"))["gross_mass"]
        self.assertEqual(over["status"], "gap")
        self.assertIn("exceeds the limit by 472.8 kg", over["text"])
        payload = self.by_kind(self.link("itt_payload.md"))["gross_mass"]
        self.assertEqual((payload["figures"]["limit_basis"], payload["status"]), ("cargo", "gap"))     # 2,582.8 > 2,500
        plain = self.by_kind(self.link("itt_plain.md"))["gross_mass"]
        self.assertEqual(plain["status"], "covered")            # no unmodelled packaging: the figure is the evidence
        self.assertEqual(plain["figures"]["margin_kg"], 13527.2)

    # never covered -------------------------------------------------------------------------------------------
    def test_lashing_stillages_and_sequence_are_never_covered(self):
        for name in ("facade_itt_doc.md", "itt_40gp.md", "itt_plain.md", "itt_mass_6t.md", "itt_open_top.md"):
            out = self.link(name)
            for s in out["statements"]:
                if s["kind"] in ("securing", "handling", "delivery_sequence"):
                    self.assertEqual(s["status"], "human_required", (name, s))
                    self.assertTrue(s["placeholder"] and s["text"].startswith("[TO CONFIRM"), s)
        kinds = self.by_kind(self.link())
        self.assertEqual(kinds["securing"]["clause"], "4.10")
        self.assertIn("CTU", kinds["securing"]["text"])
        self.assertEqual(kinds["handling"]["clause"], "4.7")
        self.assertIn("A-frame stillage size, tare or capacity", kinds["handling"]["text"])
        self.assertEqual(kinds["crate_structure"]["status"], "human_required")
        self.assertEqual(kinds["crate_structure"]["figures"]["pending_design"], 24)
        self.assertEqual(kinds["containers_used"]["status"], "partial")       # crate model, not the A-frame of 4.7
        self.assertEqual(kinds["containers_used"]["figures"]["containers_used"], 6)
        self.assertEqual(kinds["containers_used"]["clause"], "4.8")          # the count is tied to the clause it satisfies

    def test_bidbook_logistics_section_cites_clause_and_figure(self):
        out = self.link()
        book = out["bidbook_markdown"]
        section = book.split("## 6. Logistics & Packing (linked to the loading plan)", 1)[1].split("\n## 7.", 1)[0]
        for s in out["statements"]:
            self.assertIn(f"**{s['id']} (Clause {s['clause']}).**", section)
        self.assertIn("6 x 40HQ", section)
        self.assertIn("6,472.8 kg", section)
        self.assertIn("sha256", section)
        self.assertIn("S$ [TO FILL]", book)                  # price stays a person's job
        self.assertIn("| ITT 4.9 | Gross mass per loaded container (S3) |", book)
        self.assertNotIn("Delivery packing was **not run**", book)
        self.assertTrue(out["submit_blocked"])

    # stay linked -----------------------------------------------------------------------------------------------
    def test_changed_panel_list_names_the_stale_statements(self):
        first = self.link()
        self.assertIsNone(first["record"]["changes_since_previous"])
        again = self.link(previous=first["record"])
        same = again["record"]["changes_since_previous"]
        self.assertEqual((same["inputs_changed"], same["changed"], same["needs_reconfirmation"]), ([], [], []))
        rev_b = self.link(panels="facade_panels_rev_b.xlsx", previous=first["record"])
        changes = rev_b["record"]["changes_since_previous"]
        self.assertEqual([i["input"] for i in changes["inputs_changed"]], ["panel_list", "plan"])
        by_id = {c["id"]: c for c in changes["changed"]}
        self.assertEqual(by_id["S2"]["figures"]["containers_used"], [6, 8])
        self.assertEqual(by_id["S3"]["figures"]["max_cargo_kg"], [2582.8, 2862.8])
        self.assertIn("S2", changes["needs_reconfirmation"])
        self.assertIn("S3", changes["needs_reconfirmation"])
        self.assertIn("containers used 6 -> 8", changes["summary"])
        self.assertEqual([c["id"] for c in changes["unchanged"]], ["S1", "S4", "S5"])
        self.assertIn("Changed since the previous run", rev_b["bidbook_markdown"])
        dropped = self.link("itt_no_sequence.md", previous=first["record"])["record"]["changes_since_previous"]
        self.assertEqual([i["input"] for i in dropped["inputs_changed"]], ["tender"])
        self.assertEqual([w["key"] for w in dropped["withdrawn"]], ["delivery_sequence@4.11"])
        self.assertIn("withdrawn", dropped["summary"])

    def test_record_binds_statement_clause_figures_and_hashes(self):
        import hashlib
        import json

        out = self.link()
        record = json.loads(next(d["text"] for d in out["deliverables"] if d["name"] == "tender-packing-link.json"))
        self.assertEqual(record["inputs"]["tender"]["sha256"], hashlib.sha256((self.job / "facade_itt_doc.md").read_bytes()).hexdigest())
        self.assertEqual(record["inputs"]["panel_list"]["sha256"],
                         hashlib.sha256((self.job / "facade_panels.xlsx").read_bytes()).hexdigest())
        self.assertEqual(len(record["inputs"]["plan"]["sha256"]), 64)
        self.assertEqual(record["materials_source"], "panel_list")
        self.assertIs(record["submit_blocked"], True)
        self.assertIs(record["confirmed_by_person"], False)
        for s in record["statements"]:
            self.assertTrue({"id", "clause", "clause_sha256", "figures", "sha256", "status"} <= set(s))

    def test_reads_stay_inside_the_job_folder(self):
        from packing_assistant.tender_packing_link import run_link

        with self.assertRaises(PermissionError):
            run_link(str(FIXTURES / "facade_itt_doc.md"), str(self.job / "facade_panels.xlsx"))

    # entry points ----------------------------------------------------------------------------------------------
    def test_trigger_phrases_route_to_the_linked_run(self):
        from packing_assistant.runtime.task_router import route_task, wants_link

        for text in ("Link the tender facade_itt_doc.md to the packing list facade_panels.xlsx and write the logistics response",
                     "Write the tender logistics response from facade_itt_doc.md and facade_panels.xlsx",
                     "Plan the packing of facade_panels.xlsx under the tender's clauses in facade_itt_doc.md",
                     "按招标 facade_itt_doc.md 和装箱单 facade_panels.xlsx 出投标物流应答",
                     "招标装柜联动：facade_itt_doc.md、facade_panels.xlsx"):
            route = route_task(text)
            self.assertTrue(wants_link(text), text)
            self.assertEqual((route["expert_ids"], route["intent"]), (["bid-parse"], "run"), text)
        for text in ("What is a logistics response?", "物流应答是什么？"):
            self.assertEqual(route_task(text)["intent"], "chat", text)
        for text in ("解析招标 facade_itt_doc.md", "按 facade_panels.xlsx 装柜，柜型 40HQ", "Parse the tender facade_itt_doc.md",
                     "不要做物流应答"):
            self.assertFalse(wants_link(text), text)

    def test_steps_mode_turns_write_the_linked_response(self):
        from packing_assistant.civil import run_task

        for session, text in (("link-en", "Link the tender facade_itt_doc.md to the packing list facade_panels.xlsx and write the logistics response"),
                              ("link-zh", "按招标 facade_itt_doc.md 和装箱单 facade_panels.xlsx 出投标物流应答")):
            out = run_task(text, session_id=session)
            self.assertEqual((out["ok"], out["skill"], out["agent_mode"]), (True, "bid-parse", "steps"), out.get("reply"))
            names = {Path(f["path"]).name for f in out["files"]}
            self.assertTrue({"tender-packing-link.json", "tender-packing-link.md", "bidbook.en.md", "pack-plan.json",
                             "tender.handoff.json"} <= names, names)
            self.assertIn("tender.packing_link", out["tools_run"])
            link = out["tender_packing_link"]
            self.assertEqual(link["plan"]["containers_used"], 6)
            self.assertIs(out["submit_blocked"], True)
        rev = run_task("招标装柜联动：按招标 facade_itt_doc.md 和改版装箱单 facade_panels_rev_b.xlsx 重出物流应答", session_id="link-zh")
        changes = rev["tender_packing_link"]["changes_since_previous"]
        self.assertIn("containers used 6 -> 8", changes["summary"])
        self.assertIn("bidbook.en.docx", changes["stale_exports"])     # the old Word copy is named, not left silent
        missing = run_task("Link the tender facade_itt_doc.md to the packing list and write the logistics response", session_id="link-miss")
        self.assertEqual((missing["ok"], missing["error_code"], missing["wrote"]), (False, "link_inputs", False))

    def test_pack_ship_takes_the_container_type_typed_in_the_request(self):
        from packing_assistant.civil import run_task

        out = run_task("按 facade_panels.xlsx 装柜，柜型 20GP", session_id="pack-20gp")
        plan = (out.get("pack_ship") or {}).get("plan") or {}
        self.assertEqual(plan.get("container_type"), "20GP", out.get("reply"))     # was 40HQ whatever was typed
        default = run_task("按 facade_panels.xlsx 装柜", session_id="pack-default")
        self.assertEqual(((default.get("pack_ship") or {}).get("plan") or {}).get("container_type"), "40HQ")
        refused = run_task("按 facade_panels.xlsx 装柜，柜型 40 ft open top", session_id="pack-ot")
        self.assertEqual((refused["ok"], refused["error_code"]), (False, "unknown_container_type"), refused.get("reply"))
        both = run_task("按 facade_panels.xlsx 装柜，柜型 20GP 或 40HQ", session_id="pack-two")
        self.assertEqual((both["ok"], both["error_code"], both["wrote"]), (False, "ambiguous_container_type", False))


class Gateway(unittest.TestCase):
    def test_sample_materials_are_said_and_the_tender_type_is_used(self):
        from fastapi.testclient import TestClient

        from gateway.app import app

        client = TestClient(app)
        text = "三、采用海运整柜 40GP。\n四、重心与绑扎须符合 CTU。\n"
        out = client.post("/api/tender/delivery", json={"text": text, "run_delivery": True, "session_id": "link-gw"}).json()
        self.assertEqual(out["materials_source"], "sample")
        self.assertEqual(out["packing_summary"]["materials_source"], "sample")
        self.assertEqual(out["packing_summary"]["container_type_requested"], "40GP")      # from the tender, not 40HQ
        self.assertEqual(out["container_decision"]["source"], "tender_clause")
        self.assertIn("SAMPLE MATERIALS", out["bidbook_markdown"])
        given = client.post("/api/tender/delivery", json={"text": text, "run_delivery": True, "container_type": "40HQ",
                                                          "materials": [{"name": "crate", "length_mm": 1200, "width_mm": 1000,
                                                                         "height_mm": 1000, "weight_kg": 300, "quantity": 2,
                                                                         "total_weight_kg": 600}],
                                                          "session_id": "link-gw2"}).json()
        self.assertEqual(given["materials_source"], "request")
        self.assertEqual(given["packing_summary"]["container_type_requested"], "40HQ")
        self.assertNotIn("SAMPLE MATERIALS", given["bidbook_markdown"])


class Demo(unittest.TestCase):
    def test_demo_exits_0_and_prints_the_link(self):
        with tempfile.TemporaryDirectory(prefix="facade-demo-link-") as tmp:
            env = {k: v for k, v in os.environ.items() if not k.endswith("_API_KEY") and k not in ("CIVIL_JOB_ROOT", "CIVIL_AGENT_MODE")}
            env.update(PYTHON_DOTENV_DISABLED="1", PYTHONUTF8="1")
            done = subprocess.run([sys.executable, str(ROOT / "scripts" / "demo_facade.py"), "--job", str(Path(tmp) / "job")],
                                  capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, timeout=600)
        self.assertEqual(done.returncode, 0, done.stdout[-3000:] + done.stderr[-2000:])
        out = done.stdout
        self.assertIn("== 1 Tender <-> packing, linked", out)
        self.assertIn("container type: Container type 40HQ taken from Clause 4.8.", out)
        self.assertIn("link record: .civil-buddy/out/civil-link/bid-parse/tender-packing-link.json", out)
        self.assertIn("S2 Clause 4.8 · containers_used · partial · 6 x 40HQ", out)
        self.assertIn("containers used 6 -> 8", out)
        self.assertIn("statements S2, S3, S6, S7 need re-confirmation", out)
        self.assertIn("PASS demo_facade", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
