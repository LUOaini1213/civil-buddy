#!/usr/bin/env python3
"""T042: structured IT drafts, credential exclusion and real Markdown/Excel delivery."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packing_assistant.expert_roster import exclusive_tools
from packing_assistant.office_job import tables_from_md
from packing_assistant.post_drafts.it import build_draft

POSTS = ("it-ops", "it-data", "it-app")


def draft(post: str, text: str) -> str:
    value = build_draft(post, exclusive_tools(post)[0], text)
    assert isinstance(value, str)
    return value


def rows_for(markdown: str, title: str) -> list[list[str]]:
    return next(rows for name, rows in tables_from_md(markdown) if name.startswith(title))


def pem_marker(kind: str = "", *, end: bool = False) -> str:
    """A synthetic PEM armour line, assembled at runtime.

    The secret scanner (scripts/scan_tracked_secrets.py) fails the build on any
    tracked file that contains a private-key header, and it is right to: it
    cannot tell a fixture from a leak. So the fixtures below must not contain
    one on disk, only in memory.
    """
    return "-----" + ("END " if end else "BEGIN ") + kind + "PRIVATE KEY-----"


class ItDraftTests(unittest.TestCase):
    def test_exact_registered_tools(self) -> None:
        for post in POSTS:
            for tool in exclusive_tools(post):
                self.assertIsInstance(build_draft(post, tool, "请生成草稿"), str)
        self.assertIsNone(build_draft("it-ops", "it-data__backup", "test"))
        self.assertIsNone(build_draft("it-data", "unknown", "test"))
        self.assertIsNone(build_draft("admin-doc", "admin-doc__draft", "test"))

    def test_ops_role_permissions_and_contact_are_requested_not_granted(self) -> None:
        md = draft("it-ops", "系统：项目资料平台；范围：项目部；角色：资料员；权限：查询和导出本项目目录\n"
                   "申请事项：临时增加目录导出；申请人：张工；审批人：项目经理；生效时间：周一；到期日：周五\n"
                   "升级路径：值班台至平台负责人；联系人：陈工；升级条件：影响目录查询；故障现象：目录无法打开")
        self.assertEqual(["项目资料平台", "项目部", "资料员", "查询和导出本项目目录", ""], rows_for(md, "系统与权限申请矩阵")[1])
        self.assertIn("值班台至平台负责人", rows_for(md, "故障分级与升级路径")[1])
        self.assertIn("陈工", rows_for(md, "故障分级与升级路径")[1])
        self.assertIn(["拟生效时间", "周一"], rows_for(md, "权限变更与留痕"))
        self.assertIn(["实际生效记录", ""], rows_for(md, "权限变更与留痕"))

    def test_ops_multiple_roles_keep_system_without_inventing_permissions(self) -> None:
        md = draft("it-ops", "系统：OA\n角色：员工；权限：查看本人申请\n角色：审批人员")
        rows = rows_for(md, "系统与权限申请矩阵")
        self.assertEqual("OA", rows[2][0])
        self.assertEqual("审批人员", rows[2][2])
        self.assertTrue(rows[2][3].startswith("UNSPECIFIED"))
        self.assertTrue(rows_for(md, "故障分级与升级路径")[1][3].startswith("UNSPECIFIED"))

    def test_backup_targets_are_per_system_and_not_drill_results(self) -> None:
        md = draft("it-data", "系统：OA；数据对象：审批附件；数据分级：一般；RPO：1天；RTO：4小时；"
                   "备份周期：每天；介质：离线磁盘；保留期限：30天\n"
                   "系统：项目平台；数据对象：项目目录；数据分级：重要；RPO：2小时；备份周期：每两小时；介质：磁带")
        targets = rows_for(md, "业务恢复目标")
        self.assertEqual(["OA", "1天", "4小时", ""], targets[1])
        self.assertEqual("2小时", targets[2][1])
        self.assertTrue(targets[2][2].startswith("UNSPECIFIED"))
        self.assertEqual("离线磁盘", rows_for(md, "备份计划")[1][3])
        for row in rows_for(md, "恢复演练记录")[1:]:
            self.assertTrue(all(value.startswith("UNSPECIFIED") for value in row[1:]))
        self.assertNotIn("已具备恢复能力", md)

    def test_backup_transfers_supplied_drill_evidence_as_unverified(self) -> None:
        md = draft("it-data", "系统：测试OA；演练对象：审批附件；演练日期：2026-09-10；隔离环境：测试区；"
                   "业务拉起记录：人工核查可读取测试附件；实际恢复时长：38分钟；完整性检查：附件逐份核对；"
                   "检查人：周工；演练记录：演练记录A；失败原因：未提供")
        self.assertEqual("38分钟", rows_for(md, "恢复演练记录")[1][-1])
        self.assertIn("用户提供，未核验", md)
        self.assertEqual("演练记录A", rows_for(md, "恢复证据与核对")[1][3])
        self.assertEqual("", rows_for(md, "恢复证据与核对")[1][-1])
        self.assertTrue(rows_for(md, "业务恢复目标")[1][2].startswith("UNSPECIFIED"))

    def test_app_parses_roles_requirements_and_observable_acceptance(self) -> None:
        md = draft("it-app", "系统：项目日报；现状：手工汇总表格；目标：减少重复填报；现有流程：工地上交表格；"
                   "目标流程：施工员填报后项目经理复核\n"
                   "角色：施工员；场景：每日填报；功能：提交日报；对象：本项目日报；规则：日期必填；"
                   "异常：缺日期不提交；验收标准：缺日期时显示提示且保留草稿\n"
                   "角色：项目经理；功能：查询汇总；优先级：高\n期望交付时间：下月评审后安排")
        self.assertIn(["用户描述现状", "手工汇总表格"], rows_for(md, "现状、目标与范围"))
        self.assertEqual("每日填报", rows_for(md, "角色与功能需求")[1][2])
        self.assertEqual("缺日期时显示提示且保留草稿", rows_for(md, "可观察验收标准")[1][2])
        self.assertTrue(rows_for(md, "可观察验收标准")[2][2].startswith("UNSPECIFIED"))
        self.assertEqual("", rows_for(md, "可观察验收标准")[1][-1])
        self.assertIn("用户期望，未承诺", md)

    def test_app_reads_role_led_notes_and_repeated_functions(self) -> None:
        md = draft("it-app", "系统：资料平台\n资料员导出本项目目录\n项目经理审批借阅申请")
        rows = rows_for(md, "角色与功能需求")
        self.assertEqual(["资料员", "项目经理"], [row[1] for row in rows[1:]])
        self.assertEqual("导出本项目目录", rows[1][3])
        repeated = draft("it-app", "系统：OA；角色：员工；功能：提交申请；功能：查看本人记录")
        self.assertEqual(["员工", "员工"], [row[1] for row in rows_for(repeated, "角色与功能需求")[1:]])

    def test_unknown_jurisdiction_and_missing_values_are_not_defaulted(self) -> None:
        for post in POSTS:
            md = draft(post, "写内部草稿")
            self.assertIn("- 辖区：UNSPECIFIED\n", md)
            self.assertIn("UNSPECIFIED", md)
            self.assertIn("草稿声明", md)
            self.assertIn("- 辖区：SG\n", draft(post, "新加坡 写草稿"))
            self.assertIn("- 辖区：CN\n", draft(post, "CN 写草稿"))

    def test_sensitive_assignments_are_removed_before_all_post_field_extraction(self) -> None:
        assignments = (
            ('密码："quoted-secret-alpha"', "quoted-secret-alpha"),
            ("password=unquoted-secret-bravo other text", "unquoted-secret-bravo"),
            ('"api_key": "api-secret-charlie"', "api-secret-charlie"),
            ("API key 是 api-secret-delta", "api-secret-delta"),
            ("Authorization: Bearer auth-secret-echo", "auth-secret-echo"),
            ("用户名：actual-account-foxtrot", "actual-account-foxtrot"),
            ("连接串：Server=local;Password=connection-secret-golf", "connection-secret-golf"),
            ("口令=complex-secret-hotel;角色：secret-tail-india", "secret-tail-india"),
        )
        for post in POSTS:
            for assignment, secret in assignments:
                with self.subTest(post=post, assignment=assignment.split(":", 1)[0]):
                    md = draft(post, "系统：测试平台\n角色：用户\n功能：查询目录 " + assignment + "\n备份介质：磁带")
                    self.assertNotIn(secret, md)
                    self.assertIn("测试平台", md)
                    self.assertNotIn("## 用户原文", md)

    def test_private_key_blocks_and_quoted_multiline_secrets_never_reach_output(self) -> None:
        for post in POSTS:
            for secret in (
                pem_marker("RSA ") + "\nMII_SYNTHETIC_PRIVATE_ALPHA\n" + pem_marker("RSA ", end=True),
                pem_marker("OPENSSH ") + "\nSYNTHETIC_PRIVATE_BRAVO",
                '密码："multiline-secret-charlie\ncontinued-secret-delta"',
            ):
                with self.subTest(post=post):
                    md = draft(post, "系统：测试平台\n功能：查询\n" + secret + "\n")
                    for marker in ("MII_SYNTHETIC", "SYNTHETIC_PRIVATE", "multiline-secret", "continued-secret"):
                        self.assertNotIn(marker, md)
                    self.assertNotIn("PRIVATE KEY", md)

    def test_credentials_in_urls_tokens_and_addresses_are_removed_inside_fields(self) -> None:
        payloads = (
            ("https://fake-user:fake-url-password@example.invalid/path", "fake-url-password"),
            ("postgresql://fake-user:fake-db-password@host.invalid/db", "fake-db-password"),
            ("Bearer opaque-bearer-token", "opaque-bearer-token"),
            ("sk-synthetic-test-key-alpha", "sk-synthetic-test-key-alpha"),
            ("eyJhbGciOiJub25lIn0.eyJzdWIiOiJ0ZXN0In0.signature", "eyJhbGci"),
            ("10.99.98.0/24", "10.99.98"),
            ("api.example.invalid/v1/query", "api.example.invalid"),
        )
        for post in POSTS:
            for payload, marker in payloads:
                md = draft(post, f"系统：测试平台\n角色：用户\n功能：读取 {payload}\n数据对象：{payload}\n权限：查询 {payload}")
                self.assertNotIn(marker, md, (post, marker))

    def test_markdown_structure_does_not_accept_user_markup(self) -> None:
        md = draft("it-app", "系统：A|B<script>；角色：资料员；功能：查询目录")
        self.assertNotIn("<script>", md)
        self.assertEqual(7, len(rows_for(md, "角色与功能需求")[1]))

    def test_key_value_markdown_table_preserves_safe_fields(self) -> None:
        md = draft("it-ops", "| 字段 | 值 |\n| --- | --- |\n| 系统 | OA |\n| 角色 | 员工 |\n| 权限 | 查询本人记录 |\n| 联系人 | 李工 |")
        self.assertEqual(["OA", "员工", "查询本人记录"], [rows_for(md, "系统与权限申请矩阵")[1][i] for i in (0, 2, 3)])
        self.assertEqual("李工", rows_for(md, "故障分级与升级路径")[1][3])

    def test_column_backup_table_never_inherits_other_systems_target(self) -> None:
        md = draft("it-data", "| 系统 | RPO | RTO | 介质 |\n| --- | --- | --- | --- |\n"
                   "| OA | 1天 | 4小时 | 磁带 |\n| 项目平台 | 2小时 | | 离线磁盘 |")
        rows = rows_for(md, "业务恢复目标")
        self.assertEqual(["OA", "1天", "4小时", ""], rows[1])
        self.assertEqual("项目平台", rows[2][0])
        self.assertTrue(rows[2][2].startswith("UNSPECIFIED"))
        self.assertEqual("离线磁盘", rows_for(md, "备份计划")[2][3])

    def test_column_requirements_keep_empty_role_and_acceptance_unknown(self) -> None:
        md = draft("it-app", "系统：资料平台\n| 角色 | 功能 | 验收标准 |\n| --- | --- | --- |\n"
                   "| 资料员 | 导出目录 | 只导出本项目 |\n| | 查询日报 | |")
        rows = rows_for(md, "角色与功能需求")
        self.assertEqual(3, len(rows))
        self.assertEqual("资料平台", rows[2][0])
        self.assertTrue(rows[2][1].startswith("UNSPECIFIED"))
        self.assertTrue(rows_for(md, "可观察验收标准")[2][2].startswith("UNSPECIFIED"))

    def test_credential_columns_and_key_value_rows_are_never_read(self) -> None:
        sources = (
            "| 系统 | 密码 | API key | RPO |\n| --- | --- | --- | --- |\n| OA | table-secret-alpha | table-secret-bravo | 1天 |",
            "| 字段 | 值 |\n| --- | --- |\n| 系统 | OA |\n| 密码 | table-secret-alpha |\n| API key | table-secret-bravo |\n| 角色 | 员工 |",
        )
        for post in POSTS:
            for source in sources:
                md = draft(post, source)
                self.assertIn("OA", md)
                self.assertNotIn("table-secret-alpha", md)
                self.assertNotIn("table-secret-bravo", md)


class ItRuntimeTests(unittest.TestCase):
    def test_all_posts_deliver_real_markdown_and_excel_without_credentials(self) -> None:
        from packing_assistant import expert_turn
        from packing_assistant.runtime import memory
        import openpyxl

        with tempfile.TemporaryDirectory(prefix="civil-it-") as tmp:
            base = Path(tmp)
            with patch.dict(os.environ, {"CIVIL_JOB_ROOT": str(base / "job"), "CIVIL_SANDBOX_ROOTS": str(base), "PYTHON_DOTENV_DISABLED": "1"}), \
                 patch.object(expert_turn, "_OUT", base / "sessions"), patch.object(memory, "_OUT", base / "sessions"):
                cases = (
                    ("it-ops", "系统：测试运维；角色：资料员；权限：查询目录", "系统与权限申请矩阵", "查询目录"),
                    ("it-data", "系统：测试备份；数据对象：日报；RPO：一天；介质：离线磁盘", "备份计划", "离线磁盘"),
                    ("it-app", "系统：测试需求；角色：施工员；功能：登记日报；验收标准：缺日期时显示提示", "角色与功能需求", "登记日报"),
                    ("it-app", "系统：字符测试；角色：资料员；功能：判断 x < 10 且 a|b", "角色与功能需求", "判断 x < 10 且 a|b"),
                )
                credentials = "\n密码：runtime-password-secret\nAPI key：runtime-api-secret\n功能：https://fake:runtime-url-secret@example.invalid/a\n"
                credentials += pem_marker() + "\nruntime-pem-secret\n" + pem_marker(end=True) + "\n"
                for index, (post, text, table, expected) in enumerate(cases):
                    with self.subTest(post=post):
                        result = expert_turn.run_expert_turn(text + credentials, post, force_intent="run", session_id=f"it-draft-{index}")
                        self.assertTrue(result["ok"], result)
                        self.assertTrue(result["wrote"], result)
                        self.assertEqual("done", result["state"])
                        files = [Path(item["path"]) for item in result["files"]]
                        md = next(path for path in files if path.suffix == ".md")
                        self.assertTrue(md.is_relative_to(base))
                        content = md.read_text(encoding="utf-8")
                        self.assertIn(expected, str(rows_for(content, table)))
                        book = next(path for path in files if path.suffix == ".xlsx")
                        self.assertTrue(book.is_relative_to(base))
                        workbook = openpyxl.load_workbook(book)
                        try:
                            exported = "\n".join(str(value) for sheet in workbook for row in sheet.iter_rows(values_only=True) for value in row if value is not None)
                            self.assertIn(expected, exported)
                            for secret in ("runtime-password-secret", "runtime-api-secret", "runtime-url-secret", "runtime-pem-secret"):
                                self.assertNotIn(secret, content)
                                self.assertNotIn(secret, exported)
                        finally:
                            workbook.close()

    def test_questions_do_not_create_files(self) -> None:
        from packing_assistant.expert_turn import run_expert_turn

        for post in POSTS:
            result = run_expert_turn("这项工作需要哪些资料？", post, force_intent="chat", session_id=f"it-question-{post}")
            self.assertTrue(result["ok"], result)
            self.assertFalse(result["wrote"])
            self.assertEqual([], result["files"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
