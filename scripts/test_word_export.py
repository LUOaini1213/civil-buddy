#!/usr/bin/env python3
"""Real editable DOCX export: content fidelity, structure and truthful failures."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from xml.etree import ElementTree as ET
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["PYTHON_DOTENV_DISABLED"] = "1"

from packing_assistant.document_text import docx_document_text
from packing_assistant.office_job import export_md_to_docx
from packing_assistant.post_drafts import build_draft
from packing_assistant.sandbox import SandboxProfile
from packing_assistant.word_export import markdown_docx_bytes

NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
W = "{" + NS["w"] + "}"


def document(data: bytes) -> ET.Element:
    with ZipFile(BytesIO(data)) as package:
        if package.testzip() is not None:
            raise AssertionError("invalid DOCX archive")
        required = {"[Content_Types].xml", "_rels/.rels", "word/document.xml",
                    "word/styles.xml", "word/numbering.xml", "word/_rels/document.xml.rels"}
        if not required.issubset(package.namelist()):
            raise AssertionError("incomplete DOCX package")
        for name in package.namelist():
            ET.fromstring(package.read(name))
        return ET.fromstring(package.read("word/document.xml"))


def text(node: ET.Element) -> str:
    return "".join(child.text or "" for child in node.findall(".//w:t", NS))


def table_rows(doc: ET.Element) -> list[list[list[str]]]:
    return [[[text(cell) for cell in row.findall("w:tc", NS)] for row in table.findall("w:tr", NS)]
            for table in doc.findall(".//w:tbl", NS)]


class WordStructureTests(unittest.TestCase):
    def test_headings_paragraphs_quotes_and_editable_lists(self) -> None:
        source = ("# 设计说明 C#\n\n> AI 草稿；审批及签认：[A001] 待填。\n\n"
                  "段落中文，保留 **重点** 与 *斜体*。\n换行记录。\n\n## 待办 ###\n"
                  "- 资料收集\n  - 图纸核对\n3. 初核\n4. 复核\n7. 用户明确编号\n")
        data = markdown_docx_bytes(source)
        doc = document(data)
        body = doc.find("w:body", NS)
        paragraphs = body.findall("w:p", NS)
        self.assertEqual("设计说明 C#", text(paragraphs[0]))
        self.assertEqual("Heading1", paragraphs[0].find("w:pPr/w:pStyle", NS).get(W + "val"))
        self.assertEqual("Quote", paragraphs[1].find("w:pPr/w:pStyle", NS).get(W + "val"))
        heading = next(p for p in paragraphs if text(p) == "待办")
        self.assertEqual("Heading2", heading.find("w:pPr/w:pStyle", NS).get(W + "val"))
        self.assertTrue(doc.findall(".//w:rPr/w:b", NS))
        self.assertTrue(doc.findall(".//w:rPr/w:i", NS))
        self.assertTrue(doc.findall(".//w:br", NS))
        listed = [p for p in paragraphs if p.find("w:pPr/w:numPr", NS) is not None]
        self.assertEqual(["资料收集", "图纸核对", "初核", "复核", "用户明确编号"], [text(p) for p in listed])
        self.assertEqual("1", listed[1].find("w:pPr/w:numPr/w:ilvl", NS).get(W + "val"))
        with ZipFile(BytesIO(data)) as package:
            numbering = ET.fromstring(package.read("word/numbering.xml"))
            starts = [item.get(W + "val") for item in numbering.findall(".//w:startOverride", NS)]
            self.assertEqual(["3", "7"], starts)
            styles = ET.fromstring(package.read("word/styles.xml"))
            self.assertEqual(6, len(styles.findall(".//w:outlineLvl", NS)))
        self.assertIn("签认：[A001] 待填", docx_document_text(doc, 100_000))
        self.assertNotIn("已签认", text(doc))

    def test_tables_preserve_empty_cells_entities_formulas_and_escaped_pipes(self) -> None:
        source = ("# 草稿\n| 标记 | 名称 | 参数 |\n|---|---|---|\n||系统乙||\n"
                  "|公式|=HYPERLINK(\"https://example.invalid\",\"A\")|@SUM(A1)|\n"
                  "|原文|a&#124;b &amp; &lt; 10|&amp;lt;|\n"
                  "|转义|a\\|b|`x|y`|\n|多列|第二格|第三格|额外原文|\n")
        data = markdown_docx_bytes(source)
        doc = document(data)
        rows = table_rows(doc)[0]
        self.assertEqual(["", "系统乙", "", ""], rows[1])
        self.assertEqual('=HYPERLINK("https://example.invalid","A")', rows[2][1])
        self.assertEqual("@SUM(A1)", rows[2][2])
        self.assertEqual(["原文", "a|b & < 10", "&lt;", ""], rows[3])
        self.assertEqual(["转义", "a|b", "x|y", ""], rows[4])
        self.assertEqual("额外原文", rows[5][3])
        self.assertEqual(1, len(doc.findall(".//w:tblHeader", NS)))
        for forbidden in ("fldSimple", "instrText", "hyperlink", "object", "altChunk"):
            self.assertFalse(doc.findall(".//w:" + forbidden, NS))
        with ZipFile(BytesIO(data)) as package:
            self.assertFalse(any(name.endswith(".bin") for name in package.namelist()))
            for name in ("_rels/.rels", "word/_rels/document.xml.rels"):
                self.assertNotIn(b'TargetMode="External"', package.read(name))

    def test_code_and_link_destinations_stay_plain_document_content(self) -> None:
        source = "说明：[资料链接](https://example.invalid/report)；`&lt;原始代码&gt;`\n\n```text\n=1+1\n{ MERGEFIELD 原文 }\nA\tB\n```\n"
        doc = document(markdown_docx_bytes(source))
        self.assertIn("资料链接 (https://example.invalid/report)", text(doc))
        self.assertIn("&lt;原始代码&gt;", text(doc))
        self.assertIn("=1+1", text(doc))
        self.assertIn("{ MERGEFIELD 原文 }", text(doc))
        self.assertTrue(doc.findall(".//w:tab", NS))
        self.assertFalse(doc.findall(".//w:instrText", NS))

    def test_nonbordered_tables_and_document_readback(self) -> None:
        doc = document(markdown_docx_bytes("# 名册\n姓名 | 岗位\n--- | ---\n张三 | 资料员\n李四 | 运维\n"))
        self.assertEqual([["姓名", "岗位"], ["张三", "资料员"], ["李四", "运维"]], table_rows(doc)[0])
        readback = docx_document_text(doc, 10_000)
        for value in ("名册", "姓名", "岗位", "张三", "资料员", "李四", "运维"):
            self.assertIn(value, readback)


class WordExportTests(unittest.TestCase):
    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory(prefix="civil-word-export-")
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        env = patch.dict(os.environ, {"CIVIL_SANDBOX_ROOTS": str(self.root), "CIVIL_JOB_ROOT": "",
                                     "CIVIL_SANDBOX": "workspace-write", "PYTHON_DOTENV_DISABLED": "1"})
        env.start()
        self.addCleanup(env.stop)

    def source(self, content: str = "# AI 草稿\n\n审批：[A001] 待填。\n", filename: str = "说明.md") -> Path:
        path = self.root / filename
        path.write_text(content, encoding="utf-8")
        return path

    def test_actual_representative_post_drafts_export_and_read_back(self) -> None:
        cases = (
            ("admin-doc", "admin-doc__draft", "文种：请示；标题：会议设备采购请示；主送：行政部；请示事项：采购会议设备", ("会议设备采购请示", "行政部", "采购会议设备")),
            ("admin-doc", "admin-doc__draft", "文种：纪要；会议名称：项目协调会；决议：补齐原始记录；责任人：李测试；期限：周五", ("项目协调会", "补齐原始记录", "李测试", "周五")),
            ("admin-doc", "admin-doc__draft", "文种：用印；文件名称：原始申请表；印章种类：项目章；份数：2份", ("原始申请表", "项目章", "2份")),
            ("admin-office", "admin-office__list", "会议名称：资料交接会；场地：东楼301；议程：资料核对；与会人员：张测试", ("资料交接会", "东楼301", "资料核对", "张测试")),
            ("it-app", "it-app__srs", "系统：材料台账；角色：库管员；功能：登记收发；验收标准：按原始记录核对", ("材料台账", "库管员", "登记收发", "按原始记录核对")),
            ("hvac", "hvac__memo", "系统：空调甲；冷负荷：用户原表150kW；资料来源：现场 < 记录 | A&B", ("空调甲", "用户原表150kW", "现场 < 记录 | A&B", "UNSPECIFIED")),
        )
        for index, (post, tool, user, expected) in enumerate(cases):
            with self.subTest(post=post, user=user):
                md = build_draft(post, tool, user)
                self.assertIsInstance(md, str)
                path = self.source(md, f"{post}-{index}.md")
                original = path.read_bytes()
                exported = export_md_to_docx(path)
                self.assertIsNotNone(exported)
                self.assertTrue(exported.is_file())
                self.assertEqual(self.root, exported.parent)
                self.assertEqual(original, path.read_bytes())
                doc = document(exported.read_bytes())
                readback = docx_document_text(doc, 200_000)
                self.assertIn("草稿", readback)
                self.assertTrue(table_rows(doc))
                # Check parsed Word cell/paragraph values, not just archive names.
                for value in expected:
                    self.assertIn(value, text(doc))

    def test_existing_word_documents_and_repeated_exports_are_never_overwritten(self) -> None:
        path = self.source()
        owner = path.with_suffix(".docx")
        other = self.root / "说明-2.docx"
        owner.write_bytes(b"existing owner document")
        other.write_bytes(b"another owner document")
        result = export_md_to_docx(path)
        self.assertEqual("说明-3.docx", result.name)
        self.assertEqual(b"existing owner document", owner.read_bytes())
        self.assertEqual(b"another owner document", other.read_bytes())
        document(result.read_bytes())
        self.assertEqual("说明-4.docx", export_md_to_docx(path).name)

    def test_concurrent_exports_create_distinct_complete_files(self) -> None:
        path = self.source()
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: export_md_to_docx(path), range(4)))
        self.assertEqual(4, len(set(results)))
        for result in results:
            self.assertIn("AI 草稿", text(document(result.read_bytes())))

    def test_non_markdown_and_missing_paths_are_not_export_candidates(self) -> None:
        self.assertIsNone(export_md_to_docx(self.root / "missing.md"))
        self.assertIsNone(export_md_to_docx(self.source(filename="plain.txt")))
        self.assertFalse(list(self.root.glob("*.docx")))

    def test_empty_invalid_xml_and_invalid_utf8_fail_without_an_output(self) -> None:
        for index, content in enumerate((b" \n\t", b"# bad\x00content", b"# bad\x0bcontent", b"\xff\xfeinvalid")):
            with self.subTest(content=content):
                path = self.root / f"bad-{index}.md"
                path.write_bytes(content)
                with self.assertRaises(ValueError):
                    export_md_to_docx(path)
        self.assertFalse(list(self.root.glob("*.docx")))

    def test_oversized_document_and_table_fail_instead_of_dropping_content(self) -> None:
        path = self.root / "large.md"
        path.write_bytes(b"x" * (2 * 1024 * 1024 + 1))
        with self.assertRaises(ValueError):
            export_md_to_docx(path)
        columns = ["列" + str(index) for index in range(64)]
        path = self.source("|" + "|".join(columns) + "|\n|" + "|".join("---" for _ in columns) + "|\n")
        with self.assertRaises(ValueError):
            export_md_to_docx(path)
        self.assertFalse(list(self.root.glob("*.docx")))

    def test_read_only_and_forbidden_source_are_rejected(self) -> None:
        path = self.source()
        with patch.dict(os.environ, {"CIVIL_SANDBOX": "read-only"}), self.assertRaises(PermissionError):
            export_md_to_docx(path)
        blocked = self.source(filename="api_key_fixture.md")
        with self.assertRaises(PermissionError):
            export_md_to_docx(blocked)
        profile = SandboxProfile(allowed_write_roots=[self.root / "different-root"])
        with patch("packing_assistant.sandbox.default_profile", return_value=profile), self.assertRaises(PermissionError):
            export_md_to_docx(path)
        self.assertFalse(list(self.root.glob("*.docx")))

    def test_denied_output_is_a_failure_and_preserves_source(self) -> None:
        path = self.source()
        original = path.read_bytes()
        with patch("packing_assistant.sandbox.assert_write", side_effect=PermissionError("fixture output denied")), self.assertRaises(PermissionError):
            export_md_to_docx(path)
        self.assertEqual(original, path.read_bytes())
        self.assertFalse(list(self.root.glob("*.docx")))

    def test_partial_disk_write_failure_removes_only_its_new_incomplete_file(self) -> None:
        path = self.source()
        owner = path.with_suffix(".docx")
        owner.write_bytes(b"owner stays")
        original_open = Path.open

        class ShortWrite:
            def __init__(self, stream):
                self.stream = stream

            def __enter__(self):
                return self

            def __exit__(self, *args):
                self.stream.close()

            def write(self, data):
                self.stream.write(data[:10])
                return 10

        def fail_output(target, mode="r", *args, **kwargs):
            stream = original_open(target, mode, *args, **kwargs)
            return ShortWrite(stream) if mode == "xb" else stream

        with patch.object(Path, "open", fail_output), self.assertRaises(OSError):
            export_md_to_docx(path)
        self.assertEqual(b"owner stays", owner.read_bytes())
        self.assertEqual([owner], list(self.root.glob("*.docx")))


if __name__ == "__main__":
    unittest.main(verbosity=2)
