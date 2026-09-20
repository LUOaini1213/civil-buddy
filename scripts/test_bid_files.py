#!/usr/bin/env python3
"""The files a bid check is pointed at: the ones that gave no text, the ones that are evidence, and
which version of everything a check was made against.

Before this file existed:

  a scanned 投标响应.pdf       was dropped without a word (``except Exception: continue``), and the draft
                               said "用户未提供投标响应资料" and 未响应 on every row - the same words it uses
                               when nobody gave a response at all
  a scanned 招标文件.pdf       made the run parse the sentence that named the file, find nothing, and answer
                               "招标协作未完成，请核对资料与输出目录"
  项目经理证书.txt             was passed along as a "reference" and never opened: "核对原件" was all the
                               draft could say, whether the certificate named the same person or not
  a check of yesterday's draft read exactly like a check of today's: nothing said which text was checked

Every assertion reads a table cell by its row and its column, or a field of the record on disk.
No model is involved anywhere in this file.
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Dict, List, Optional
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["PYTHON_DOTENV_DISABLED"] = "1"
for _key in ("DEEPSEEK_API_KEY", "OPENAI_API_KEY", "LLM_API_KEY", "CIVIL_API_KEY", "CIVIL_AGENT_MODE", "GOOGLE_API_KEY"):
    os.environ.pop(_key, None)

from packing_assistant import office_job  # noqa: E402
from packing_assistant.runtime import agent_loop, workspace  # noqa: E402
from packing_assistant.runtime.agent_loop import run_agent  # noqa: E402

TENDER = "第一章 投标人须知\n★工期60日历天。\n★投标保证金人民币20万元。\n项目经理须具备一级注册建造师资格。\n"
RESPONSE = "投标响应\n我方承诺工期60日历天。\n投标保证金人民币20万元已备妥。\n拟派项目经理李明，一级注册建造师。\n"
UNKNOWN = "未能判断·文件未读出"


def tables(md: str) -> List[List[Dict[str, str]]]:
    found: List[List[Dict[str, str]]] = []
    header: Optional[List[str]] = None
    for raw in md.splitlines():
        line = raw.strip()
        if not (line.startswith("|") and line.endswith("|")):
            header = None
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if all(re.fullmatch(r":?-{2,}:?", c) for c in cells):
            continue
        if header is None:
            header = cells
            found.append([])
            continue
        found[-1].append(dict(zip(header, cells)))
    return found


def rows(md: str, first: str) -> List[Dict[str, str]]:
    return [row for table in tables(md) for row in table if next(iter(row.values()), "") == first]


def blank_pdf(path: Path) -> None:
    """A PDF with a page and no text layer - what a scanner makes."""
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=300, height=300)
    with path.open("wb") as stream:
        writer.write(stream)


class JobFolder(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="civil-bidfiles-")
        self.addCleanup(temporary.cleanup)
        self.addCleanup(os.chdir, Path.cwd())
        self.addCleanup(workspace.deactivate)
        self.job = Path(temporary.name).resolve()
        (self.job / "CIVIL.md").write_text("- 项目：东桥改造工程\n", encoding="utf-8")
        (self.job / "招标文件.txt").write_text(TENDER, encoding="utf-8")
        os.chdir(self.job)
        with patch.object(Path, "home", return_value=self.job / "no-home"):
            workspace.activate(self.job)

    def draft(self, out: Dict, name: str) -> str:
        hit = [f["path"] for f in out["files"] if Path(f["path"]).name == name]
        self.assertEqual(len(hit), 1, [f["path"] for f in out["files"]])
        return Path(hit[0]).read_text(encoding="utf-8")


class Unreadable(JobFolder):
    def test_the_reader_says_why_and_never_echoes_the_parser(self) -> None:
        blank_pdf(self.job / "扫描件.pdf")
        (self.job / "坏的.docx").write_bytes(b"this is not a zip archive")
        (self.job / "空的.txt").write_text("  \n", encoding="utf-8")
        text, why = office_job.read_material_checked(self.job / "招标文件.txt")
        self.assertEqual((text, why), (TENDER, ""))
        self.assertIn("OCR", office_job.read_material_checked(self.job / "扫描件.pdf")[1])
        self.assertEqual(office_job.read_material_checked(self.job / "坏的.docx"), ("", "打不开，或内容与扩展名不符"))
        self.assertEqual(office_job.read_material_checked(self.job / "空的.txt"), ("", "里面几乎没有文字"))

    def test_a_named_file_that_gave_no_text_is_listed_not_dropped(self) -> None:
        blank_pdf(self.job / "投标响应.pdf")
        sources, unread = agent_loop._tender_materials("全面检查投标响应：招标文件.txt 投标响应.pdf")
        self.assertEqual([(s["role"], s["title"]) for s in sources], [("tender", "招标文件.txt")])
        self.assertEqual([(u["title"], u["role"]) for u in unread], [("投标响应.pdf", "response")])
        self.assertIn("OCR", unread[0]["reason"])

    def test_the_check_says_unknown_where_it_used_to_say_not_responded(self) -> None:
        blank_pdf(self.job / "投标响应.pdf")
        out = run_agent("全面检查投标响应：招标文件.txt 投标响应.pdf", session_id="civil-cli")
        self.assertTrue(out["ok"], out.get("reply"))
        self.assertIn("投标响应.pdf", out["reply"])
        self.assertIn("未能判断", out["reply"])
        md = self.draft(out, "bid-compliance.md")
        self.assertEqual({rows(md, first)[0]["三态"] for first in ("工期", "投标保证金", "项目经理")}, {UNKNOWN})
        self.assertIn("投标响应.pdf", rows(md, "工期")[0]["缺口"])
        self.assertIn("投标响应.pdf（响应侧）", rows(md, "未读出的文件")[0]["内容"])
        self.assertIn("给了但未读出", rows(md, "响应资料")[0]["内容"])
        self.assertNotIn("用户未提供投标响应资料", md)
        self.assertEqual([u["title"] for u in out["review"]["unreadable"]], ["投标响应.pdf"])
        self.assertEqual(out["quality"]["unreadable_files"], 1)
        self.assertIn("投标响应.pdf", self.draft(out, "collaboration-review.md"))
        parse = self.draft(out, "tender-extract.md")
        self.assertEqual(rows(parse, "未读出的文件")[0]["是否检出"], "未读出")
        snapshot = json.loads(Path([f["path"] for f in out["files"] if f["path"].endswith("handoff.json")][0]).read_text(encoding="utf-8"))
        self.assertEqual(snapshot["handoff"]["unreadable"][0]["title"], "投标响应.pdf", "inside the hashed handoff: the next post sees it too")

    def test_an_unreadable_tender_stops_the_run_and_says_which_file(self) -> None:
        (self.job / "招标文件.txt").unlink()
        blank_pdf(self.job / "招标文件.pdf")
        (self.job / "投标响应.txt").write_text(RESPONSE, encoding="utf-8")
        out = run_agent("全面检查投标响应：招标文件.pdf 投标响应.txt", session_id="civil-cli")
        self.assertFalse(out["ok"])
        self.assertEqual(out["error_code"], "tender_unreadable")
        self.assertIn("招标文件.pdf", out["reply"])
        self.assertIn("OCR", out["reply"])
        self.assertFalse(out["wrote"])
        self.assertEqual(out["files"], [])

    def test_an_unreadable_addendum_is_said_on_the_tender_side(self) -> None:
        blank_pdf(self.job / "补遗tender-addendum.pdf")
        (self.job / "投标响应.txt").write_text(RESPONSE, encoding="utf-8")
        out = run_agent("全面检查投标响应：招标文件.txt 补遗tender-addendum.pdf 投标响应.txt", session_id="civil-cli")
        self.assertTrue(out["ok"], out.get("reply"))
        md = self.draft(out, "bid-compliance.md")
        self.assertIn("补遗tender-addendum.pdf（招标侧）", rows(md, "未读出的文件")[0]["内容"])
        self.assertIn("招标侧文件未读出（补遗tender-addendum.pdf）：下表的招标要求可能不全", md)
        self.assertEqual(rows(md, "工期")[0]["三态"], "已响应·待核验", "the response was read: its rows keep their state")

    def test_everything_readable_reads_as_before(self) -> None:
        (self.job / "投标响应.txt").write_text(RESPONSE.replace("工期60", "工期999"), encoding="utf-8")
        out = run_agent("全面检查投标响应：招标文件.txt 投标响应.txt", session_id="civil-cli")
        md = self.draft(out, "bid-compliance.md")
        self.assertEqual(rows(md, "工期")[0]["三态"], "未响应·数值不符")
        self.assertNotIn("未读出", md)
        snapshot = json.loads(Path([f["path"] for f in out["files"] if f["path"].endswith("handoff.json")][0]).read_text(encoding="utf-8"))
        self.assertNotIn("unreadable", snapshot["handoff"], "an ordinary handoff is what it was")

    def test_one_post_alone_says_it_too(self) -> None:
        blank_pdf(self.job / "评标办法.pdf")
        blob = agent_loop._with_named_documents("解析招标 招标文件.txt 评标办法.pdf")
        self.assertIn("### 评标办法.pdf\n（读失败）PDF 没有文字层", blob)
        out = run_agent("解析招标 招标文件.txt 评标办法.pdf", session_id="civil-cli")
        self.assertTrue(out["ok"], out.get("reply"))
        md = self.draft(out, "tender.parse.md")
        self.assertEqual(rows(md, "未读出的文件")[0]["要求原文"], "评标办法.pdf")
        self.assertIn("只对读到的部分成立", md)
        self.assertEqual(rows(md, "工期")[0]["要求原文"], "60日历天", "what was read is still read")
        self.assertNotIn("读失败", "".join(r["要求原文"] for t in tables(md) for r in t if r.get("是否检出") == "已检出"),
                         "the marker is nobody's requirement")


class EvidenceFiles(JobFolder):
    """A file that is neither the tender nor the response is searched for our side's own wording."""

    def check(self, certificate: str, response: str = RESPONSE) -> str:
        (self.job / "投标响应.txt").write_text(response, encoding="utf-8")
        (self.job / "项目经理证书.txt").write_text(certificate, encoding="utf-8")
        out = run_agent("全面检查投标响应：招标文件.txt 投标响应.txt 项目经理证书.txt", session_id="civil-cli")
        self.assertTrue(out["ok"], out.get("reply"))
        self.assertEqual(out["review"]["evidence_files"], ["项目经理证书.txt"])
        return self.draft(out, "bid-compliance.md")

    def test_the_name_we_wrote_is_found_in_the_certificate(self) -> None:
        md = self.check("中华人民共和国一级注册建造师注册证书\n姓 名：李 明\n注册类别：一级注册建造师\n注册编号：京111060812345\n")
        found = {r["我方写的"]: r for r in rows(md, "项目经理")if "字样" in r}
        self.assertEqual(found["李明"]["字样"], "检出", "a text layer spells a name with a space in it")
        self.assertEqual(found["李明"]["证据文件"], "项目经理证书.txt")
        self.assertIn("只说明字样出现", found["李明"]["说明"])
        self.assertEqual(found["一级注册建造师"]["字样"], "检出")
        self.assertNotIn("未检出", rows(md, "项目经理")[0]["缺口"])
        self.assertIn("项目经理证书.txt", rows(md, "证据文件")[0]["内容"])

    def test_somebody_elses_certificate_is_said(self) -> None:
        md = self.check("一级注册建造师注册证书\n姓名：王强\n注册类别：一级注册建造师\n")
        found = {r["我方写的"]: r for r in rows(md, "项目经理") if "字样" in r}
        self.assertEqual(found["李明"]["字样"], "未检出")
        self.assertEqual(found["一级注册建造师"]["字样"], "检出")
        main = rows(md, "项目经理")[0]
        self.assertIn("证据文件里未检出「李明」字样", main["缺口"])
        self.assertEqual(main["三态"], "已响应·待核验", "a missing word is a gap to close, not a verdict")
        self.assertIn("项目经理：证据文件里未检出「李明」字样", md.split("## 7 澄清与补证")[1])

    def test_a_scanned_certificate_is_unknown_not_absent(self) -> None:
        (self.job / "投标响应.txt").write_text(RESPONSE, encoding="utf-8")
        (self.job / "营业执照.txt").write_text("营业执照\n统一社会信用代码 91110000100000000X\n", encoding="utf-8")
        blank_pdf(self.job / "项目经理证书.pdf")
        out = run_agent("全面检查投标响应：招标文件.txt 投标响应.txt 营业执照.txt 项目经理证书.pdf", session_id="civil-cli")
        md = self.draft(out, "bid-compliance.md")
        found = {r["我方写的"]: r for r in rows(md, "项目经理") if "字样" in r}
        self.assertEqual(found["李明"]["字样"], "未能判断")
        self.assertIn("项目经理证书.pdf", found["李明"]["证据文件"])
        self.assertNotIn("未检出「李明」", rows(md, "项目经理")[0]["缺口"])

    def test_no_evidence_files_no_section(self) -> None:
        (self.job / "投标响应.txt").write_text(RESPONSE, encoding="utf-8")
        out = run_agent("全面检查投标响应：招标文件.txt 投标响应.txt", session_id="civil-cli")
        md = self.draft(out, "bid-compliance.md")
        self.assertNotIn("证据文件字样核对", md)
        self.assertEqual(out["review"]["evidence_files"], [])

    def test_what_the_user_typed_is_never_an_evidence_file(self) -> None:
        from packing_assistant.runtime.tender_workflow import _evidence_files

        typed = {"source_id": "current-input", "title": "本轮用户要求", "text": "李明", "role": "reference", "kind": "user"}
        tender = {"source_id": "t", "title": "招标文件", "text": TENDER, "role": "tender", "kind": "attachment"}
        paper = {"source_id": "e", "title": "证书.pdf", "text": "李明", "role": "reference", "kind": "attachment"}
        self.assertEqual([e["title"] for e in _evidence_files([typed, tender, paper])], ["证书.pdf"])
        self.assertEqual(_evidence_files([typed, paper]), [], "with no declared tender a reference file is the tender text")


if __name__ == "__main__":
    unittest.main(verbosity=2)
