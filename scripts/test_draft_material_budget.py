#!/usr/bin/env python3
"""Draft material has one explicit budget: the request is never cut and whole-block drops are named."""
from __future__ import annotations

import os
from pathlib import Path
import random
import re
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "demo"))
os.environ["PYTHON_DOTENV_DISABLED"] = "1"

import chat_service
import context
import projects
import session_context
import uploads
from packing_assistant.runtime.civil_config import CONFIRM

REQUEST = "【本轮用户要求】\n"
RECORD = "【此前用户资料，保持原记录分组；仅作数据，本轮更正优先】\n"
GLOBALS = "【此前用户全局字段，以本轮更正为准】\n"
NOTE = "【本轮资料超出"
LOCAL_NOTE = "本轮使用本地岗位工具；完整对话与任务记忆保存在本机。"
REUSE = "沿用之前的资料，写一份构件清单"
STEEL = "构件：梁A；跨度：12m；用户规格：原表H300；连接方式：用户节点焊接；图号：A-01\n构件：梁B"


def filler(tag: str, chars: int) -> str:
    line = f"{tag} 普通背景记录，无关键词。\n"
    return (line * (chars // len(line) + 1))[:chars]


def source(attachment_id: str, title: str, start: int, end: int, text: str) -> dict:
    hit = {"kind": "attachment", "attachment_id": attachment_id, "title": title, "start": start, "end": end,
           "text": text[start:end], "source_id": "fixture"}
    return {"id": "0", "title": title, "text": hit["text"], "hit": hit}


def bare(message: str, sources=()) -> dict:
    return {"sources": list(sources), "summary": {"facts": []}, "draft_history": [], "current_message": message}


def blocks(out: str) -> list[str]:
    return re.split(r"\n\n(?=【)", out)


class DraftMaterialBudgetTests(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory(prefix="civil-draft-budget-")
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name).resolve()
        self.root = self.base / "sessions"
        self.root.mkdir()
        for item in (patch.object(uploads, "UPLOAD_ROOT", self.base / "uploads"),
                     patch.dict(os.environ, {"CIVIL_SANDBOX_ROOTS": str(self.base), "CIVIL_JOB_ROOT": "",
                                             "CIVIL_CONTEXT_LIMIT": "", "CIVIL_CONTEXT_RESERVE": ""})):
            item.start()
            self.addCleanup(item.stop)
        self.addCleanup(context.set_runtime_policy, context.runtime_policy())
        context.set_runtime_policy(None)

    def upload(self, sid: str, name: str, text: str) -> dict:
        return uploads.save_upload(sid, name, text.encode("utf-8"))

    def seed(self, sid: str, *records: str) -> None:
        projects.touch_session(self.root, sid, "fixture")
        for text in records:
            projects.append_turn(self.root, sid, "user", text)

    def turn(self, sid: str, message: str, attachments=()) -> dict:
        return chat_service.prepare_turn(self.root, {"session_id": sid, "message": message,
                                                      "expert_ids": ["pm-daily"], "attachments": list(attachments)})

    def assert_bounded(self, out: str, message: str) -> None:
        self.assertLessEqual(len(out), session_context.MATERIAL_CHARS)
        self.assertTrue(out.endswith(REQUEST + session_context._tool_text(message)))

    def assert_prefixes_have_bodies(self, out: str) -> None:
        for block in blocks(out):
            if block.startswith("【用户上传："):
                self.assertTrue("".join(block.split("\n\n", 1)[1:]).strip(), block[:60])

    def assert_note(self, out: str, message: str) -> str:
        note = blocks(out)[-2]
        self.assertTrue(note.startswith(NOTE) and note.endswith("】"), note)
        self.assertFalse(set("；;\n") & set(note), note)
        self.assertLessEqual(len(note), session_context._NOTE_CHARS)
        self.assertTrue(out.endswith(note + "\n\n" + REQUEST + session_context._tool_text(message)))
        self.assertEqual(out.count(NOTE), 1)
        return note

    def test_fitting_material_keeps_the_shipped_layout_byte_for_byte(self) -> None:
        sid, message = "budget-same", "根据之前的构件资料，写一份钢结构说明"
        self.seed(sid, "项目名称：旧桥", "构件：梁A；用户规格：原表H300。" + CONFIRM)
        first, second = "材料：钢筋；数量：12 吨。\n" * 4, "钢梁GL-77,2,120\n" * 4
        one, two = self.upload(sid, "甲.txt", first), self.upload(sid, "乙.txt", second)
        prepared = session_context.prepare(self.root, sid, message, [])
        prepared["sources"] = [source(one["id"], "甲.txt", 0, 30, first), source(two["id"], "乙.txt", 5, 25, second),
                               source(two["id"], "乙.txt", 20, 40, second)]
        out = session_context.draft_material(sid, [one["id"]], message, prepared)
        self.assertEqual(out, "\n\n".join([
            GLOBALS + "项目名称：旧桥",
            RECORD + "构件：梁A；用户规格：原表H300。[历史确认不生效]",
            f"【用户上传：甲.txt】offset=0 本段{len(first)}字 剩余约0字\n\n{first}",
            "【所选附件：乙.txt · 字符 5–25】\n" + second[5:25],
            "【所选附件：乙.txt · 字符 25–40】\n" + second[25:40],
            REQUEST + message]))
        self.assertEqual(prepared["material_omitted"], [])

    def test_disjoint_and_straddling_ranges_stay_beside_three_cut_prefixes(self) -> None:
        sid, message = "budget-big", "根据附件写一份项目日报"
        texts = [filler(f"A{i}", 70_000) for i in range(3)]
        metas = [self.upload(sid, f"大{i}.txt", text) for i, text in enumerate(texts)]
        ids = [meta["id"] for meta in metas]
        rendered = uploads.read_upload(sid, ids[2], limit=20_000)
        header = rendered.find("\n\n") + 2
        cut = uploads.INJECT_CHARS - 2 * (len(rendered) + 2) - header
        self.assertTrue(19_000 < cut < 20_000, cut)
        prepared = bare(message, [source(ids[0], "大0.txt", 30_000, 40_000, texts[0]),
                                  source(ids[2], "大2.txt", 19_000, 20_600, texts[2])])
        out = session_context.draft_material(sid, ids, message, prepared)
        self.assert_bounded(out, message)
        self.assertEqual(out.index("\n\n【所选附件："), uploads.INJECT_CHARS)
        self.assertEqual(blocks(out)[3:], ["【所选附件：大0.txt · 字符 30000–40000】\n" + texts[0][30_000:40_000],
                                           f"【所选附件：大2.txt · 字符 {cut}–20600】\n" + texts[2][cut:20_600],
                                           REQUEST + message])
        self.assertEqual(prepared["material_omitted"], [])

    def test_small_selected_attachment_survives_in_either_order(self) -> None:
        sid, message = "budget-small", "根据附件写一份材料清单"
        self.seed(sid)
        big = [self.upload(sid, f"规范{i}.txt", filler(f"B{i}", 69_000))["id"] for i in range(3)]
        bill = self.upload(sid, "清单.csv", "名称,数量,重量\n钢梁GL-77,2,120\n")["id"]
        for ids in ([*big, bill], [bill, *big]):
            with self.subTest(first=ids[0] == bill):
                turn = self.turn(sid, message, ids)
                self.assert_bounded(turn["material"], message)
                self.assertIn("GL-77", turn["material"])
                self.assertNotIn(NOTE, turn["material"])
                self.assertEqual(turn["prepared_context"]["material_omitted"], [])
                self.assertEqual(turn["context"]["note"], LOCAL_NOTE)
        with patch.object(session_context, "MATERIAL_CHARS", uploads.INJECT_CHARS + session_context._NOTE_CHARS + 50):
            turn = self.turn(sid, message, [*big, bill])
            self.assert_bounded(turn["material"], message)
            self.assert_note(turn["material"], message)
        omitted = turn["prepared_context"]["material_omitted"]
        self.assertTrue(any(item.startswith("清单.csv 字符 0–") for item in omitted), omitted)
        self.assertTrue(all(" 字符 " in item for item in omitted), omitted)
        self.assertEqual((turn["material"].count("【用户上传："), turn["material"].count("【所选附件：")), (3, 0))
        self.assertEqual(turn["context"]["note"], LOCAL_NOTE + " 本轮资料超出预算，未加入：" + "、".join(omitted[:6])
                         + (f" 等 {len(omitted)} 项" if len(omitted) > 6 else "") + "。")

    def test_history_keeps_the_newest_contiguous_records_after_the_global_fields(self) -> None:
        sid = "budget-history"
        self.seed(sid, "项目名称：东桥", "构件编号：GJ-1\n重量：100 吨（旧值）",
                  "构件编号：GJ-1\n重量：200 吨（更正后）\n" + filler("M", 3_000),
                  "构件编号：GJ-2\n重量：50 吨\n" + filler("N", 3_000))
        turn = self.turn(sid, REUSE)
        order = [turn["material"].index(marker) for marker in (GLOBALS + "项目名称：东桥", "旧值", "更正后", "GJ-2", REQUEST)]
        self.assertEqual(order, sorted(order))
        self.assertEqual((turn["prepared_context"]["material_omitted"], turn["context"]["note"]), ([], LOCAL_NOTE))
        with patch.object(session_context, "MATERIAL_CHARS", 6_000):
            turn = self.turn(sid, REUSE)
            out = turn["material"]
            self.assert_bounded(out, REUSE)
            note = self.assert_note(out, REUSE)
        self.assertTrue(out.startswith(GLOBALS + "项目名称：东桥\n\n" + RECORD + "构件编号：GJ-2\n重量：50 吨\n"))
        self.assertNotIn("更正后", out)
        self.assertNotIn("旧值", out)
        self.assertEqual(turn["prepared_context"]["material_omitted"], ["较早的此前用户资料 2 条"])
        self.assertEqual(note, "【本轮资料超出 6000 字预算，未加入：较早的此前用户资料 2 条】")
        self.assertEqual(turn["context"]["note"], LOCAL_NOTE + " 本轮资料超出预算，未加入：较早的此前用户资料 2 条。")
        prepared = turn["prepared_context"]
        with patch.object(session_context, "MATERIAL_CHARS", session_context._NOTE_CHARS + len(REQUEST + REUSE) + 4 + 10):
            out = session_context.draft_material(sid, [], REUSE, prepared)
            self.assert_bounded(out, REUSE)
        self.assertEqual(prepared["material_omitted"], ["此前用户全局字段", "较早的此前用户资料 3 条"])
        self.assertEqual(len(blocks(out)), 2)

    def test_longest_request_and_twelve_attachments_fit_without_a_note(self) -> None:
        sid, message = "budget-wide", "根据附件写一份项目日报 KEYWORD0729 KEYWORD1729 KEYWORD2729 位置"
        self.seed(sid)
        context.set_runtime_policy({"limit": 128_000, "reserve": 4096})
        ids = [self.upload(sid, f"大{i}.txt", filler(f"B{i}", 69_000) + f"\nKEYWORD{i}729 位置：{i}号仓库。\n")["id"] for i in range(3)]
        ids += [self.upload(sid, f"小{i}.txt", filler(f"K{i}", 9_900) + f"小件{i}号收尾。")["id"] for i in range(9)]
        turn = self.turn(sid, message, ids)
        self.assertEqual(turn["prepared_context"]["material_omitted"], [])
        longest = "。请" * 20_000
        self.assertEqual(len(session_context._tool_text(longest)), 60_000)
        prepared = {**turn["prepared_context"], "current_message": longest}
        out = session_context.draft_material(sid, ids, longest, prepared)
        self.assert_bounded(out, longest)
        self.assertGreater(len(out), 200_000)
        self.assertNotIn(NOTE, out)
        self.assertEqual(prepared["material_omitted"], [])
        self.assertEqual(out.count("【用户上传："), 3)
        for i in range(9):
            self.assertIn(f"小件{i}号收尾。", out)

    def test_note_is_one_line_built_to_fit(self) -> None:
        sid, message, text = "budget-note", "根据附件写一份项目日报", filler("C", 9_000)
        meta = self.upload(sid, "长.txt", text)
        ten = [source(meta["id"], "长.txt", i * 900, (i + 1) * 900, text) for i in range(10)]
        long_title = "长" * 76 + ".txt"
        six = [source(meta["id"], long_title, 100_000 + i * 900, 100_900 + i * 900, "x" * 101_000 + text) for i in range(6)]
        dirty = [source(meta["id"], "坏；名;字\n.txt", 0, 900, text)]
        with patch.object(session_context, "MATERIAL_CHARS", 1_200):
            for sources, ending, listed in ((ten, "、长.txt 字符 4500–5400 等 10 项】", 6), (six, " 字符 103600–104500 等 6 项】", 5),
                                            (dirty, "未加入：坏 名 字 .txt 字符 0–900】", 1)):
                prepared = bare(message, sources)
                out = session_context.draft_material(sid, [], message, prepared)
                self.assert_bounded(out, message)
                note = self.assert_note(out, message)
                self.assertEqual(out, note + "\n\n" + REQUEST + message)
                self.assertTrue(note.endswith(ending), note)
                self.assertEqual(note.count(" 字符 "), listed)
                self.assertEqual(len(prepared["material_omitted"]), len(sources))
        self.assertEqual(prepared["material_omitted"], ["坏；名;字\n.txt 字符 0–900"])

    def test_skipped_range_does_not_mask_later_hits(self) -> None:
        sid, message, text = "budget-mask", "根据附件写一份项目日报", filler("D", 2_000)
        meta = self.upload(sid, "短.txt", text)
        prepared = bare(message, [source(meta["id"], "短.txt", *span, text) for span in ((0, 900), (100, 300), (250, 500))])
        with patch.object(session_context, "MATERIAL_CHARS", 700 + session_context._NOTE_CHARS + len(REQUEST + message) + 4):
            out = session_context.draft_material(sid, [], message, prepared)
            self.assert_bounded(out, message)
            note = self.assert_note(out, message)
        self.assertEqual(blocks(out)[:2], ["【所选附件：短.txt · 字符 100–300】\n" + text[100:300],
                                           "【所选附件：短.txt · 字符 300–500】\n" + text[300:500]])
        self.assertEqual(prepared["material_omitted"], ["短.txt 字符 0–900"])
        self.assertTrue(note.endswith("未加入：短.txt 字符 0–900】"), note)

    def test_a_range_that_exactly_fills_the_budget_is_kept(self) -> None:
        sid, message, text = "budget-exact", "根据附件写一份项目日报", filler("E", 1_000)
        meta = self.upload(sid, "整.txt", text)
        block = "【所选附件：整.txt · 字符 0–300】\n" + text[:300]
        exact = session_context._NOTE_CHARS + len(REQUEST + session_context._tool_text(message)) + 4 + len(block)
        for delta, kept in ((0, True), (-1, False)):
            with self.subTest(delta=delta):
                prepared = bare(message, [source(meta["id"], "整.txt", 0, 300, text)])
                with patch.object(session_context, "MATERIAL_CHARS", exact + delta):
                    out = session_context.draft_material(sid, [], message, prepared)
                    self.assert_bounded(out, message)
                    if kept:
                        self.assertEqual(blocks(out)[0], block)
                        self.assertEqual(len(out), session_context.MATERIAL_CHARS - session_context._NOTE_CHARS - 2)
                    else:
                        self.assert_note(out, message)
                self.assertEqual(prepared["material_omitted"], [] if kept else ["整.txt 字符 0–300"])

    def test_prefix_without_room_for_body_text_is_skipped(self) -> None:
        sid, message = "budget-header", "根据附件写一份项目日报"
        names = ["一.txt", "二.txt", "第三份资料的文件名比较长.txt", "丁.txt"]
        texts = [filler("E0", 300), filler("E1", 300), filler("E2", 300), filler("E3", 50)]
        ids = [self.upload(sid, name, text)["id"] for name, text in zip(names, texts)]
        rendered = [uploads.read_upload(sid, identifier, limit=20_000) for identifier in ids]
        headers = [value.find("\n\n") + 2 for value in rendered]
        full = len(rendered[0]) + 2 + len(rendered[1]) + 2
        sources = [source(ids[2], names[2], 0, 300, texts[2]), source(ids[3], names[3], 0, 50, texts[3])]
        self.assertLess(headers[3] + 7, headers[2])
        for room, fourth in ((10, 0), (headers[3] + 7, 7)):
            with self.subTest(room=room), patch.object(uploads, "INJECT_CHARS", full + room):
                prepared = bare(message, sources)
                out = session_context.draft_material(sid, ids, message, prepared)
                self.assert_bounded(out, message)
                self.assert_prefixes_have_bodies(out)
                expected = [rendered[0], rendered[1], *([rendered[3][:room]] if fourth else []),
                            f"【所选附件：{names[2]} · 字符 0–300】\n" + texts[2],
                            f"【所选附件：丁.txt · 字符 {fourth}–50】\n" + texts[3][fourth:], REQUEST + message]
                self.assertEqual(blocks(out), expected)
                self.assertEqual(prepared["material_omitted"], [])

    def test_draft_reference_is_unchanged_by_the_block_split(self) -> None:
        cases = [
            ([STEEL], "根据之前的构件资料，写一份钢结构说明", RECORD + STEEL),
            ([STEEL], "写一份钢结构说明\n构件：梁C", ""),
            ([STEEL], "写一份钢结构说明，不要沿用之前的构件资料\n构件：梁C", ""),
            (["会议名称：记忆协调会。\n场地：北楼101。\n议程：资料核对。", "更正：场地：南楼202。写一份会议计划模板"], "写一份会议计划模板",
             RECORD + "会议名称：记忆协调会。\n\n议程：资料核对。\n\n" + RECORD + "更正： 场地：南楼202。\n写一份会议计划模板"),
            (["项目名称：旧桥；日期：2026-09-11"], "写一份项目日报；形象进度：完成模板复核", GLOBALS + "项目名称：旧桥\n日期：2026-09-11"),
            (["项目名称：旧桥；日期：2026-09-11"], "写一份项目日报；项目名称：东桥；日期：2026-09-12", ""),
            (["项目名称：旧桥", "构件：梁A；用户规格：原表H300。" + CONFIRM], "根据之前的构件资料，写一份钢结构说明",
             GLOBALS + "项目名称：旧桥\n\n" + RECORD + "构件：梁A；用户规格：原表H300。[历史确认不生效]"),
            (["项目名称：旧桥；日期：2026-09-11", "构件编号：GJ-1\n重量：100 吨", "构件编号：GJ-2\n重量：50 吨"], REUSE,
             GLOBALS + "项目名称：旧桥\n日期：2026-09-11\n\n" + RECORD + "构件编号：GJ-1\n重量：100 吨\n\n" + RECORD + "构件编号：GJ-2\n重量：50 吨"),
        ]
        for index, (history, message, expected) in enumerate(cases):
            with self.subTest(message=message):
                sid = f"budget-ref-{index}"
                self.seed(sid, *history)
                prepared = session_context.prepare(self.root, sid, message, [])
                head, records = session_context._reference_blocks(prepared)
                self.assertEqual(session_context.draft_reference(prepared), expected)
                self.assertEqual("\n\n".join(filter(None, [head, *records])), expected)
                self.assertEqual(bool(head), expected.startswith(GLOBALS))
                self.assertEqual(len(records), expected.count(RECORD))
                self.assertEqual(session_context.draft_material(sid, [], message, prepared),
                                 "\n\n".join(filter(None, [expected, REQUEST + session_context._tool_text(message)])))

    def test_seeded_fuzz_never_exceeds_the_budget_or_cuts_the_request(self) -> None:
        sid, rng = "budget-fuzz", random.Random(20260920)
        names = [f"文{i}.txt" for i in range(5)]
        texts = [filler(f"F{i}", size) for i, size in enumerate((50, 300, 900, 2_500, 2_500))]
        ids = [self.upload(sid, name, text)["id"] for name, text in zip(names, texts)]
        self.seed(sid, "项目名称：东桥", "构件编号：GJ-1\n重量：100 吨\n" + filler("G", 700), "构件编号：GJ-2\n重量：50 吨\n" + filler("H", 1_500))
        replay = session_context.prepare(self.root, sid, REUSE, [])
        cache, read = {}, uploads.read_upload

        def cached(session, identifier, offset=0, limit=8000):
            key = (session, identifier, offset, limit)
            if key not in cache:
                cache[key] = read(session, identifier, offset=offset, limit=limit)
            return cache[key]

        dropped = 0
        with patch.object(uploads, "read_upload", cached):
            for trial in range(500):
                sources = []
                for _ in range(rng.randint(0, 6)):
                    j = rng.randrange(5)
                    start = rng.randrange(len(texts[j]))
                    sources.append(source(ids[j], names[j], start, min(len(texts[j]), start + rng.randint(1, 900)), texts[j]))
                message = REUSE if rng.random() < 0.4 else "写" * rng.randint(1, 400)
                prepared = {**replay, "sources": sources} if message == REUSE else bare(message, sources)
                chosen = [ids[j] for j in rng.sample(range(5), rng.randint(0, 5))]
                with patch.object(session_context, "MATERIAL_CHARS", rng.randint(1_100, 9_000)), \
                        patch.object(uploads, "INJECT_CHARS", rng.randint(60, 3_000)):
                    out = session_context.draft_material(sid, chosen, message, prepared)
                    self.assert_bounded(out, message)
                    self.assert_prefixes_have_bodies(out)
                    self.assertEqual(bool(prepared["material_omitted"]), NOTE in out, trial)
                    if prepared["material_omitted"]:
                        self.assert_note(out, message)
                        dropped += 1
                for block in blocks(out):
                    span = re.match(r"【所选附件：.+? · 字符 (\d+)–(\d+)】\n", block)
                    if span:
                        self.assertEqual(len(block) - span.end(), int(span[2]) - int(span[1]), trial)
        self.assertTrue(50 < dropped < 450, dropped)


if __name__ == "__main__":
    unittest.main()
