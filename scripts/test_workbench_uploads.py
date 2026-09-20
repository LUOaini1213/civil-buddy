#!/usr/bin/env python3
"""Session attachment format, isolation, limits and rollback regressions."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "demo"))

import uploads


def _docx() -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr("word/document.xml", '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>这是附件正文的测试数据</w:t></w:r></w:p></w:body></w:document>')
    return buffer.getvalue()


def _pdf() -> bytes:
    stream = b"BT /F1 12 Tf 36 100 Td (Sample attachment text) Tj ET"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    content = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(content))
        content.extend(f"{index} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = len(content)
    content.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        content.extend(f"{offset:010d} 00000 n \n".encode())
    content.extend(f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return bytes(content)


class UploadTests(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory(prefix="civil-uploads-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        root_patch = patch.object(uploads, "UPLOAD_ROOT", self.root / "uploads")
        root_patch.start()
        self.addCleanup(root_patch.stop)
        env = patch.dict(os.environ, {"CIVIL_SANDBOX_ROOTS": str(self.root)})
        env.start()
        self.addCleanup(env.stop)

    def test_plain_upload_roundtrip_matches_rust_contract(self) -> None:
        raw = "项目：测试工程\n材料：钢筋\n数量：待填".encode()
        meta = uploads.save_upload("session-one", "C:\\folder\\清单.txt", raw)
        self.assertEqual(set(meta), {"id", "name", "kind", "bytes", "chars", "parse"})
        self.assertEqual(meta["name"], "清单.txt")
        self.assertEqual(meta["bytes"], len(raw))
        self.assertEqual(uploads.list_uploads("session-one"), [meta])
        directory = uploads.UPLOAD_ROOT / "session-one"
        self.assertEqual((directory / f"{meta['id']}.bin").read_bytes(), raw)
        text = uploads.read_upload("session-one", meta["id"], offset=3, limit=8)
        self.assertIn("offset=3 本段8字", text)
        self.assertEqual(meta["chars"], len((directory / f"{meta['id']}.txt").read_text(encoding="utf-8")))

    def test_readonly_listing_does_not_create_a_session(self) -> None:
        self.assertEqual(uploads.list_uploads("session-none"), [])
        self.assertFalse(uploads.UPLOAD_ROOT.exists())

    def test_invalid_sessions_are_rejected_without_normalization(self) -> None:
        for session in ("../session-one", "session/one", "session\\one", "_index", "ab", "a" * 33, "会话abcd"):
            with self.subTest(session=session), self.assertRaises(uploads.UploadError):
                uploads.list_uploads(session)
        self.assertFalse(uploads.UPLOAD_ROOT.exists())

    def test_unselected_and_other_session_attachments_never_enter_context(self) -> None:
        first = uploads.save_upload("session-one", "one.txt", b"first selected attachment")
        uploads.save_upload("session-one", "two.txt", b"second omitted attachment")
        self.assertEqual(uploads.bundle_for_prompt("session-one", [], "original request"), "original request")
        bundled = uploads.bundle_for_prompt("session-one", [first["id"]], "original request")
        self.assertIn("first selected attachment", bundled)
        self.assertNotIn("second omitted", bundled)
        with self.assertRaisesRegex(uploads.UploadError, "附件不存在"):
            uploads.read_upload("session-two", first["id"])
        with self.assertRaises(uploads.UploadError):
            uploads.read_upload("session-one", "../" + first["id"])

    def test_bad_batch_is_rejected_before_any_file_is_saved(self) -> None:
        with self.assertRaises(uploads.UploadError):
            uploads.save_uploads("session-one", [("good.txt", b"valid first attachment"), ("bad.exe", b"invalid executable")])
        self.assertFalse(uploads.UPLOAD_ROOT.exists())

    def test_write_failure_rolls_back_partial_attachment(self) -> None:
        actual = uploads.guarded_write_bytes
        calls = 0

        def fail_second(path, content):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("fixture disk failure")
            return actual(path, content)

        with patch.object(uploads, "guarded_write_bytes", side_effect=fail_second):
            with self.assertRaises(OSError):
                uploads.save_upload("session-one", "one.txt", b"valid attachment text")
        self.assertEqual(uploads.list_uploads("session-one"), [])
        self.assertEqual(list((uploads.UPLOAD_ROOT / "session-one").iterdir()), [])

    def test_size_limits_are_checked_before_writes(self) -> None:
        with patch.object(uploads, "MAX_BYTES", 10), self.assertRaises(uploads.UploadTooLarge):
            uploads.save_upload("session-one", "one.txt", b"longer than ten bytes")
        with patch.object(uploads, "MAX_REQUEST_BYTES", 20), self.assertRaises(uploads.UploadTooLarge):
            uploads.save_uploads("session-one", [("one.txt", b"first valid text"), ("two.txt", b"second valid text")])
        self.assertFalse(uploads.UPLOAD_ROOT.exists())

    def test_concurrent_uploads_enforce_session_file_limit(self) -> None:
        def save(index):
            try:
                return uploads.save_upload("session-one", f"{index}.txt", b"valid attachment text")
            except uploads.UploadError:
                return None

        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(save, range(16)))
        self.assertEqual(sum(result is not None for result in results), 12)
        self.assertEqual(len(uploads.list_uploads("session-one")), 12)

    def test_office_extractors_and_bad_files(self) -> None:
        import openpyxl

        kind, text, engine = uploads.extract_upload("draft.docx", _docx())
        self.assertEqual((kind, engine), ("docx", "builtin-docx"))
        self.assertIn("附件正文", text)
        workbook = openpyxl.Workbook()
        workbook.active.append(["物料名称", "数量待填"])
        workbook.active.append(["fixture steel", 12])
        buffer = BytesIO()
        workbook.save(buffer)
        workbook.close()
        kind, text, engine = uploads.extract_upload("table.xlsx", buffer.getvalue())
        self.assertEqual((kind, engine), ("xlsx", "openpyxl"))
        self.assertIn("fixture steel", text)
        empty = openpyxl.Workbook()
        empty.active.title = "Empty attachment worksheet"
        empty_buffer = BytesIO()
        empty.save(empty_buffer)
        empty.close()
        # The message names the kind: an empty workbook is not a scan, so it must not be told to OCR.
        with self.assertRaises(uploads.UploadError) as refused:
            uploads.extract_upload("empty.xlsx", empty_buffer.getvalue())
        self.assertIn("xlsx 文件里几乎没有文字内容", str(refused.exception))
        self.assertNotIn("OCR", str(refused.exception))
        for filename in ("bad.docx", "bad.xlsx"):
            with self.subTest(filename=filename), self.assertRaises(uploads.UploadError):
                uploads.extract_upload(filename, b"corrupted fixture")
        with patch.object(uploads, "MAX_ARCHIVE_BYTES", 20), self.assertRaises(uploads.UploadTooLarge):
            uploads.extract_upload("large.docx", _docx())

    def test_pdf_extraction_or_explicit_missing_dependency(self) -> None:
        try:
            import pypdf
        except ImportError:
            with self.assertRaisesRegex(uploads.UploadError, "依赖未安装"):
                uploads.extract_upload("fixture.pdf", _pdf())
            return
        kind, text, engine = uploads.extract_upload("fixture.pdf", _pdf())
        self.assertEqual((kind, engine), ("pdf", "pypdf"))
        self.assertIn("Sample attachment text", text)

    def test_empty_binary_and_truncated_text(self) -> None:
        for raw in (b"", b"tiny", b"binary\x00fixture"):
            with self.assertRaises(uploads.UploadError):
                uploads.extract_upload("text.txt", raw)
        with patch.object(uploads, "MAX_TEXT_CHARS", 30):
            _, text, _ = uploads.extract_upload("text.txt", b"A" * 100)
            self.assertEqual(len(text), 30)
        _, text, _ = uploads.extract_upload("text.txt", "中文附件测试：有效的内容".encode("gb18030"))
        self.assertIn("中文附件", text)

    def test_corrupt_and_incomplete_metadata_is_not_listed(self) -> None:
        directory = uploads.UPLOAD_ROOT / "session-one"
        directory.mkdir(parents=True)
        (directory / "abc123def456.json").write_text("not json", encoding="utf-8")
        (directory / "abcdef123456.json").write_text(json.dumps({"id": "abcdef123456", "name": "missing.txt"}), encoding="utf-8")
        self.assertEqual(uploads.list_uploads("session-one"), [])


if __name__ == "__main__":
    unittest.main()
