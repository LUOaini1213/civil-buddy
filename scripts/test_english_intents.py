#!/usr/bin/env python3
"""English requests in steps mode: intent (chat / run / both) and the post that runs.

    python scripts/test_english_intents.py            # pins + held-out floors (exit 1 on failure)
    python scripts/test_english_intents.py --score    # held-out numbers only, with the misses

The pins below are the development sentences the English rules were written against. The held-out rounds in
test/benchmarks/task_intent/heldout_en*.json were written before the rules ran on them; see their `note`.
"""
from __future__ import annotations

import json
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packing_assistant.runtime.expert_skills import match_skill  # noqa: E402
from packing_assistant.runtime.task_router import route_task  # noqa: E402
from packing_assistant.understand import understand  # noqa: E402

BENCH = ROOT / "test" / "benchmarks" / "task_intent"
# Below each round's first run, accuracy / post / false_run: heldout_en 1.000 / 1.000 / 0 (not blind), heldout_en2
# 0.786 / 0.889 / 0, heldout_en3 (statements; not blind) 1.000 / 1.000 / 0. False runs stay 0.
FLOORS = {"heldout_en.json": {"accuracy": 0.90, "post_accuracy": 0.90, "false_run": 0},
          "heldout_en2.json": {"accuracy": 0.75, "post_accuracy": 0.85, "false_run": 0},
          "heldout_en3.json": {"accuracy": 0.90, "post_accuracy": 0.85, "false_run": 0}}


def post_of(text: str) -> str | None:
    """The post a steps-mode turn would use (agent_loop: one routed post, else match_skill)."""
    route = route_task(text)
    if route["workflow"]:
        return route["workflow"]
    if route["expert_ids"]:
        return "+".join(route["expert_ids"])
    return match_skill(text)


def score(path: Path) -> dict:
    rows = json.loads(path.read_text(encoding="utf-8"))["cases"]
    misses, wrong_post = [], []
    for row in rows:
        got = route_task(row["text"])["intent"]
        if got != row["intent"]:
            misses.append({**row, "got": got})
        if row["intent"] != "chat":
            post = post_of(row["text"])
            if post != row["post"]:
                wrong_post.append({**row, "got": post})
    wanted = [r for r in rows if r["intent"] != "chat"]
    return {"n": len(rows), "accuracy": 1 - len(misses) / len(rows),
            "request_recall": 1 - sum(m["intent"] != "chat" for m in misses) / len(wanted),
            "false_run": sum(m["intent"] == "chat" for m in misses),
            "post_accuracy": 1 - len(wrong_post) / len(wanted), "misses": misses, "wrong_post": wrong_post}


def report(name: str, result: dict) -> None:
    print(f"{name} n={result['n']}  acc {result['accuracy']:.3f}  req.recall {result['request_recall']:.3f}  "
          f"false_run {result['false_run']}  post {result['post_accuracy']:.3f}")
    for miss in result["misses"]:
        print(f"    intent want {miss['intent']:<5} got {miss['got']:<5} {miss['text']}")
    for miss in result["wrong_post"]:
        print(f"    post   want {miss['post']!s:<14} got {miss['got']!s:<14} {miss['text']}")


REQUESTS = (
    ("write the daily report for level 12, 7 installers, sunny", "run", "pm-daily"),
    ("Please prepare today's site diary: 4 installers, crane down 2 hours", "run", "pm-daily"),
    ("Now update the site diary with the rain stoppage", "run", "pm-daily"),
    ("Pls draft a toolbox talk on glass handling", "run", "safety-brief"),
    ("Hi, can you write the safety briefing for tomorrow's glazing works?", "run", "safety-brief"),
    ("I need a method statement for bracket anchoring on the podium", "run", "construction"),
    ("Method statement for the gondola installation: 2 gondolas, 45 m", "run", "construction"),
    ("Give me a load plan for the brackets, 20GP", "run", "pack-ship"),
    ("Pack facade_panels.xlsx into 40HQ", "run", "pack-ship"),
    ("Calculate how many containers the 3rd batch needs", "run", "pack-ship"),
    ("Could you parse the tender and pull out the closing date?", "run", "bid-parse"),
    ("Check the tender response for missing forms", "run", "bid-compliance"),
    ("Draft the technical proposal section on installation sequence", "run", "bid-tech"),
    ("Explain the daily report fields, then fill in one for today", "both", "pm-daily"),
    ("Walk me through a load plan. Then prepare one for batch 3", "both", "pack-ship"),
)
QUESTIONS = (
    "I'll write the daily report myself later",
    "The daily report for yesterday had the wrong headcount",
    "Can you explain what a method statement covers?",
    "Does the tender allow alternative designs",
    "Should we check the load plan again?",
    "Who reviews the daily report before it goes to the consultant?",
    "Do not prepare the toolbox briefing, the site is closed today",
    "Draft is fine, thanks",
    "Check whether the ITT asks for a mock-up",
    "Tell me what CR16 means",
    "Thanks, the load plan is approved",
    "Outline has no chapter 3 yet",
)
# Review of the first English rules (2026-09-26): each of these ran and wrote a file; on 0f9c13c each was chat.
STATEMENTS = (
    "Daily report for yesterday was wrong",
    "Method statement for level 3 was approved by the PE",
    "Update on the tender: client extended the closing date to Friday",
    "Update on the method statement: PE has approved it",
    "Update from site: gondola 2 is fixed",
    "Plan B is to use 20GP containers",
    "Plan for tomorrow is to install 12 panels at L9",
    "List of defects is attached",
    "I think you reviewed the tender already",
    "I saw you prepared the daily report yesterday",
    "Draft approved for the method statement",
    "Check out the load plan I sent",
    "Extract from the ITT attached for your reference",
    "Review comments from the consultant are in the tender folder",
    "Toolbox talk on Monday at 8am, all installers to attend",
    "We need a method statement from the subcon by Friday",
    "Record high rainfall today, 2 hours lost",
    "Calculate",
)
# The post is the deliverable the verb asks for, not the context in front of it.
GOVERNED = (
    ("2 containers arrived at 10am, please write the daily report", "run", "pm-daily"),
    ("Containers arrived. Write the daily report for today", "run", "pm-daily"),
    ("For the tender, draft a method statement for panel installation", "run", "construction"),
    ("Based on the ITT, prepare the compliance schedule", "run", "bid-compliance"),
    ("Under the tender, prepare the technical proposal", "run", "bid-tech"),
    ("Explain the tender, then draft the compliance schedule", "both", "bid-compliance"),
    ("The daily report says the load plan is late. Update the load plan for batch 4", "run", "pack-ship"),
)


class EnglishIntentTests(unittest.TestCase):
    def test_english_requests_run_on_the_right_post(self):
        for text, intent, post in REQUESTS:
            with self.subTest(text=text):
                self.assertEqual(route_task(text)["intent"], intent)
                self.assertEqual(post_of(text), post)

    def test_english_questions_statements_and_refusals_do_not_write(self):
        for text in QUESTIONS:
            with self.subTest(text=text):
                self.assertEqual(route_task(text)["intent"], "chat")

    def test_status_messages_about_a_deliverable_do_not_write(self):
        for text in STATEMENTS:
            with self.subTest(text=text):
                self.assertEqual(route_task(text)["intent"], "chat")
                self.assertEqual(understand(text), "chat")

    def test_a_long_message_of_deliverable_titles_stays_fast(self):
        # Unbounded, each "Daily report for ..." scanned to the end of the text for a status word: 12.7 s here.
        started = time.perf_counter()
        self.assertEqual(route_task("Daily report for level 5, " * 1500 + "it was wrong")["intent"], "chat")
        self.assertLess(time.perf_counter() - started, 3.0)

    def test_the_requested_deliverable_names_the_post_not_the_context(self):
        for text, intent, post in GOVERNED:
            with self.subTest(text=text):
                self.assertEqual(route_task(text)["intent"], intent)
                self.assertEqual(post_of(text), post)

    def test_the_earliest_english_phrase_names_the_post(self):
        itt = ("INVITATION TO TENDER\n\n1.1 The Main Contractor invites tenders for unitised curtain wall.\n\n"
               "5.2 Tenderers shall submit a method statement for panel installation.")
        self.assertEqual(route_task(itt)["expert_ids"], ["bid-parse"])
        self.assertEqual(route_task("Draft a method statement for the tender")["expert_ids"], ["construction"])
        self.assertEqual(route_task("Check the tender response for missing forms")["expert_ids"], ["bid-compliance"])

    def test_latin_ids_match_whole_words_only(self):
        self.assertIsNone(match_skill("Write a progress report for level 5"))      # not $port
        self.assertIsNone(match_skill("facade_panels.xlsx"))                        # not $facade
        self.assertEqual(match_skill("Plan containers for facade_panels.xlsx"), "pack-ship")
        self.assertEqual(match_skill("Facade testing requirements"), "facade")
        self.assertEqual(match_skill("plan-master__network 固定 WBS"), "plan-master")   # a job file still names its post

    def test_contract_english_verbs_reach_understand(self):
        # understand() is what a turn with the post already selected uses (gateway /api/agent with expert_id).
        self.assertEqual(understand("Write the daily report for today"), "run")
        self.assertEqual(understand("Please prepare the toolbox briefing"), "run")
        self.assertEqual(understand("I'll write the daily report later"), "chat")
        # phrase_write is a case-sensitive substring in both stacks: "Draft a" would hit "Draft approved", "you review"
        # would hit "you reviewed", "you write" would make a question write.
        for text in ("Draft approved by the consultant, thanks", "Write access to the drawings folder is granted",
                     "Write update: gondola 2 back in service", "Did you write the daily report?",
                     "Have you reviewed the tender?"):
            with self.subTest(text=text):
                self.assertEqual(understand(text), "chat")

    def test_chinese_demo_commands_are_unchanged(self):
        self.assertEqual(route_task("解析招标 facade_itt_doc.md")["intent"], "run")
        self.assertEqual(post_of("解析招标 facade_itt_doc.md"), "bid-parse")
        self.assertEqual(route_task("按 facade_panels_zh.xlsx 装柜，柜型 40HQ")["intent"], "run")
        self.assertEqual(post_of("按 facade_panels_zh.xlsx 装柜，柜型 40HQ"), "pack-ship")
        self.assertEqual(route_task("ITT 是什么意思")["intent"], "chat")
        self.assertIsNone(match_skill("ITT 是什么意思"))
        # Mixed lines as on 0f9c13c: a Chinese post phrase decides alone, a bare "container" names no post, and an
        # English word glued to Chinese does not open an English clause.
        self.assertEqual(route_task("帮我做技术标，含 method statement")["expert_ids"], ["bid-tech"])
        self.assertEqual(route_task("写一份日报，今天 3 个 container 到场")["intent"], "run")
        self.assertIsNone(post_of("写一份日报，今天 3 个 container 到场"))
        for text, intent in (("Plan 元数据表无效。", "chat"), ("List checkpoint indexes（sqlite 模式 SQL 直查，否则扫 output/sessions/）。", "chat"),
                             ("SKIP 表格装箱门禁：本环境没有 cargo", "run"),
                             ("What-if：在现有 state 上改约束/过滤材料，重跑同一 Team 闭环，产出 plan_diff。", "chat")):
            with self.subTest(text=text):
                self.assertEqual(route_task(text)["intent"], intent)

    def test_held_out_rounds_hold_their_floors(self):
        for name, floor in FLOORS.items():
            result = score(BENCH / name)
            with self.subTest(round=name):
                self.assertGreaterEqual(result["accuracy"], floor["accuracy"])
                self.assertGreaterEqual(result["post_accuracy"], floor["post_accuracy"])
                self.assertLessEqual(result["false_run"], floor["false_run"])


def main() -> int:
    for name in FLOORS:
        report(name.removesuffix(".json"), score(BENCH / name))
    if "--score" in sys.argv:
        return 0
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(EnglishIntentTests)
    return 0 if unittest.TextTestRunner(verbosity=1).run(suite).wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
