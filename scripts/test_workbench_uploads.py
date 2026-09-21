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
        directory = uploads.session_uploads_dir("session-one")
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
        self.assertEqual(list(uploads.session_uploads_dir("session-one").iterdir()), [])

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
        directory = uploads.session_uploads_dir("session-one")
        directory.mkdir(parents=True)
        (directory / "abc123def456.json").write_text("not json", encoding="utf-8")
        (directory / "abcdef123456.json").write_text(json.dumps({"id": "abcdef123456", "name": "missing.txt"}), encoding="utf-8")
        self.assertEqual(uploads.list_uploads("session-one"), [])

    def test_a_refused_unreadable_attachment_is_remembered_and_nothing_else_changes(self) -> None:
        from pypdf import PdfWriter

        scan = BytesIO()
        writer = PdfWriter()
        writer.add_blank_page(width=300, height=300)
        writer.write(scan)
        with self.assertRaises(uploads.UploadUnreadable) as caught:
            uploads.save_uploads("session-one", [("招标文件.txt", "工期60日历天，投标保证金20万元。".encode()), ("投标文件.pdf", scan.getvalue())])
        self.assertIsInstance(caught.exception, uploads.UploadError, "still a 400 for the upload route")
        self.assertIn("OCR", str(caught.exception))
        self.assertEqual(uploads.list_uploads("session-one"), [], "nothing of a refused batch is saved")
        self.assertEqual(uploads.strict_documents("session-one"), [], "the note is not an attachment record")
        noted = uploads.unreadable_uploads("session-one")
        self.assertEqual([(n["name"], n["kind"]) for n in noted], [("投标文件.pdf", "pdf")])
        self.assertIn("OCR", noted[0]["reason"])
        self.assertEqual(uploads.unreadable_uploads("session-two"), [], "one task's note is not another's")
        # the session's attachments live in <session>/uploads since 4afef4a; the note lies beside them
        self.assertEqual(sorted(path.name for path in uploads.session_uploads_dir("session-one").iterdir()), [uploads.UNREADABLE_LOG])

    def test_the_note_goes_when_the_same_name_is_attached_readable(self) -> None:
        with self.assertRaises(uploads.UploadUnreadable):
            uploads.save_upload("session-one", "投标文件.docx", b"not a zip archive at all")
        self.assertEqual([n["name"] for n in uploads.unreadable_uploads("session-one")], ["投标文件.docx"])
        uploads.save_upload("session-one", "投标文件.docx", _docx())
        self.assertEqual(uploads.unreadable_uploads("session-one"), [])

    def test_a_wrong_type_is_not_an_unreadable_file(self) -> None:
        with self.assertRaises(uploads.UploadError) as caught:
            uploads.save_upload("session-one", "bad.exe", b"invalid executable")
        self.assertNotIsInstance(caught.exception, uploads.UploadUnreadable)
        self.assertFalse(uploads.UPLOAD_ROOT.exists())
        self.assertEqual(uploads.unreadable_uploads("session-one"), [])

    def test_the_note_is_bounded_and_never_holds_parser_output(self) -> None:
        for index in range(uploads.MAX_UNREADABLE + 6):
            with self.assertRaises(uploads.UploadUnreadable):
                uploads.save_upload("session-one", f"坏{index}.xlsx", b"SECRET-BYTES-OF-THE-DOCUMENT")
        log = (uploads.session_uploads_dir("session-one") / uploads.UNREADABLE_LOG).read_text(encoding="utf-8")
        self.assertEqual(len(log.splitlines()), uploads.MAX_UNREADABLE)
        self.assertNotIn("SECRET", log)
        self.assertEqual(len(uploads.unreadable_uploads("session-one")), uploads.MAX_UNREADABLE)

    def test_the_workflow_is_told_with_a_role_read_off_the_name(self) -> None:
        import workflow_service

        with self.assertRaises(uploads.UploadUnreadable):
            uploads.save_upload("session-one", "投标文件.docx", b"not a zip archive at all")
        with self.assertRaises(uploads.UploadUnreadable):
            uploads.save_upload("session-one", "项目经理证书.pdf", b"%PDF-1.4 broken")
        told = workflow_service.unreadable_attachments("session-one")
        self.assertEqual(sorted((t["title"], t["role"]) for t in told), [("投标文件.docx", "response"), ("项目经理证书.pdf", "reference")])
        self.assertTrue(all(t["reason"] for t in told))


class _Site:
    """A web server on this machine for the fetch tests: what it serves is decided per path."""

    def __init__(self, routes: dict) -> None:
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        from threading import Thread

        site = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                status, headers, body = site.routes.get(self.path.split("?")[0], (404, {}, b"no"))
                self.send_response(status)
                for key, value in headers.items():
                    self.send_header(key, value)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args) -> None:  # noqa: ANN002
                return

        self.routes = routes
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"
        Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()


class UrlTests(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory(prefix="civil-uploads-")
        self.addCleanup(temp.cleanup)
        root_patch = patch.object(uploads, "UPLOAD_ROOT", Path(temp.name) / "uploads")
        root_patch.start()
        self.addCleanup(root_patch.stop)
        env = patch.dict(os.environ, {"CIVIL_SANDBOX_ROOTS": temp.name})
        env.start()
        self.addCleanup(env.stop)

    def test_a_fetch_never_goes_to_this_machine_or_the_local_network(self) -> None:
        for url in ("http://127.0.0.1:8765/api/health", "http://localhost/a.pdf", "http://192.168.1.5/a.pdf", "http://10.0.0.8/a.pdf",
                    "http://169.254.169.254/latest/meta-data", "http://[::1]/a.pdf", "file:///etc/passwd", "ftp://example.org/a.pdf",
                    "http://user:pw@example.org/a.pdf", ""):
            with self.assertRaises(uploads.UploadError, msg=url):
                uploads.check_public_url(url)
        with self.assertRaises(uploads.UploadError):
            uploads.fetch_upload("session-one", "http://127.0.0.1:9/招标文件.pdf")
        self.assertEqual(uploads.list_uploads("session-one"), [], "nothing was fetched, nothing was saved")

    def test_a_fetched_document_goes_the_way_an_uploaded_one_does(self) -> None:
        page = "<html><head><style>p{}</style><script>x()</script></head><body><h1>某某工程招标公告</h1><p>工期：90日历天</p></body></html>"
        site = _Site({"/files/tender.docx": (200, {"Content-Type": "application/octet-stream"}, _docx()),
                      "/download": (200, {"Content-Type": "application/pdf", "Content-Disposition": 'attachment; filename="bid notice.pdf"'}, _pdf()),
                      "/notice/123": (200, {"Content-Type": "text/html; charset=utf-8"}, page.encode("utf-8")),
                      "/big": (200, {"Content-Type": "application/pdf"}, b"%PDF-" + b"0" * 64)})
        self.addCleanup(site.close)
        with patch.object(uploads, "check_public_url", side_effect=lambda url: url):      # the guard has its own test; here the site is local
            first = uploads.fetch_upload("session-one", site.base + "/files/tender.docx")
            second = uploads.fetch_upload("session-one", site.base + "/download?id=7")
            third = uploads.fetch_upload("session-one", site.base + "/notice/123")
            with patch.object(uploads, "MAX_BYTES", 32), self.assertRaises(uploads.UploadTooLarge):
                uploads.fetch_upload("session-one", site.base + "/big")
        self.assertEqual([f["name"] for f in first["files"] + second["files"] + third["files"]], ["tender.docx", "bid_notice.pdf", "123.txt"], "named by the server, made safe like any upload's name")
        listed = {f["name"]: f for f in uploads.list_uploads("session-one")}
        self.assertEqual(sorted(listed), ["123.txt", "bid_notice.pdf", "tender.docx"], "the oversize one left nothing behind")
        texts = {d["name"]: d["text"] for d in uploads.extracted_documents("session-one", [f["id"] for f in listed.values()])}
        self.assertIn("这是附件正文的测试数据", texts["tender.docx"])
        self.assertIn("工期：90日历天", texts["123.txt"])
        self.assertNotIn("x()", texts["123.txt"], "a page is kept as its text: no script, no style")

    def test_a_redirect_is_checked_like_the_first_address(self) -> None:
        site = _Site({"/moved": (302, {"Location": "http://127.0.0.1:9/inside.pdf"}, b"")})
        self.addCleanup(site.close)
        real = uploads.check_public_url
        calls = []

        def first_hop_only(url: str) -> str:
            calls.append(url)
            return url if len(calls) == 1 else real(url)      # the test site is local; where it SENDS us is checked for real

        with patch.object(uploads, "check_public_url", side_effect=first_hop_only), self.assertRaises(uploads.UploadError) as caught:
            uploads.fetch_document(site.base + "/moved")
        self.assertIn("内网", str(caught.exception))
        self.assertEqual(len(calls), 2)


class ScanTests(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory(prefix="civil-uploads-")
        self.addCleanup(temp.cleanup)
        root_patch = patch.object(uploads, "UPLOAD_ROOT", Path(temp.name) / "uploads")
        root_patch.start()
        self.addCleanup(root_patch.stop)
        env = patch.dict(os.environ, {"CIVIL_SANDBOX_ROOTS": temp.name})
        env.start()
        self.addCleanup(env.stop)

    @staticmethod
    def scan(pages: int = 1) -> bytes:
        from pypdf import PdfWriter

        writer = PdfWriter()
        for _ in range(pages):
            writer.add_blank_page(width=300, height=300)
        out = BytesIO()
        writer.write(out)
        return out.getvalue()

    def test_an_uploaded_scan_is_read_by_ocr_and_says_so(self) -> None:
        from packing_assistant.tools import ocr

        lines = [["第二章 投标人须知", "投标有效期：90日历天"]]
        with patch.object(ocr, "available", return_value=True), patch.object(ocr, "pdf_page_lines", return_value=lines) as read:
            meta = uploads.save_upload("session-one", "招标文件.pdf", self.scan())
        self.assertEqual(read.call_count, 1)
        text = uploads.extracted_documents("session-one", [meta["id"]])[0]["text"]
        self.assertTrue(text.startswith(ocr.MARK), "every draft made from it has to be able to say it is an OCR reading")
        self.assertIn("投标有效期：90日历天", text)

    def test_more_pages_than_an_upload_waits_for_says_where_it_stopped(self) -> None:
        from packing_assistant.tools import ocr

        lines = [[f"第{n}页的一行文字，足够长以便保留下来"] for n in range(1, uploads.OCR_UPLOAD_PAGES + 2)]
        with patch.object(ocr, "available", return_value=True), patch.object(ocr, "pdf_page_lines", return_value=lines):
            meta = uploads.save_upload("session-one", "招标文件.pdf", self.scan())
        text = uploads.extracted_documents("session-one", [meta["id"]])[0]["text"]
        self.assertIn(f"只识别了前 {uploads.OCR_UPLOAD_PAGES} 页", text)
        self.assertNotIn(f"第{uploads.OCR_UPLOAD_PAGES + 1}页的一行文字", text)

    def test_without_the_ocr_packages_a_scan_is_refused_as_before(self) -> None:
        from packing_assistant.tools import ocr

        with patch.object(ocr, "available", return_value=False), self.assertRaises(uploads.UploadUnreadable) as caught:
            uploads.save_upload("session-one", "招标文件.pdf", self.scan())
        self.assertIn("OCR", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
