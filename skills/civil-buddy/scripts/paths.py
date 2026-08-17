"""Locate this skill and bundled docx tools."""

from __future__ import annotations

import os
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DEFAULT = SKILL_ROOT / "references" / "templates" / "scheme-cn-a4.docx"

HEADER_STOCK = "AI 草稿 · 内部讨论 · 不得作为法定专项方案 / 交底签认件"
DISCLAIMER = (
    "本文件由 Grok Civil Buddy 根据用户提供的项目包与输入生成，仅供内部讨论与起草。"
    "不构成设计文件、法定专项施工方案、交底签认件、监理指令、专家论证材料或开工/竣工验收依据。"
    "涉及结构安全、基坑、临边与洞口、高处作业、脚手架、模板支撑、起重、有限空间、交通导改、验收的内容，"
    "必须由具备相应资格的人员依据正式规范文本复核并签字后方可实施。"
)

TOKENS = (
    "{{PROJECT_NAME}}",
    "{{SHORT_NAME}}",
    "{{STAMP}}",
    "{{JURISDICTION}}",
    "{{ASSUMPTIONS}}",
    "{{SEC_OVERVIEW}}",
    "{{CITED_VERIFIED}}",
    "{{CITED_UNVERIFIED}}",
    "{{SEC_DEPLOY}}",
    "{{SEC_QUALITY}}",
    "{{SEC_SAFETY}}",
    "{{SEC_ENV}}",
    "{{SEC_RESOURCES}}",
    "{{SEC_ACCEPTANCE}}",
    "{{SEC_APPENDIX}}",
)

ALLOWED_OUT_NAMES = frozenset(
    {
        "draft.md",
        "assumptions.md",
        "citations.md",
        "replacements.json",
        "manifest.json",
        "专项施工方案-AI草稿.docx",
        "codes.md",
        "project.md",
    }
)

CHAPTER_HEADINGS = {
    "{{SEC_OVERVIEW}}": ("3", "工程概况"),
    "{{SEC_DEPLOY}}": ("5", "施工部署"),
    "{{SEC_QUALITY}}": ("6", "质量"),
    "{{SEC_SAFETY}}": ("7", "安全"),
    "{{SEC_ENV}}": ("8", "环保"),
    "{{SEC_RESOURCES}}": ("9", "资源"),
    "{{SEC_ACCEPTANCE}}": ("10", "验收"),
    "{{SEC_APPENDIX}}": ("11", "附录"),
}


def grok_home() -> Path:
    env = os.environ.get("GROK_HOME")
    if env:
        return Path(env)
    return Path.home() / ".grok"


def docx_scripts() -> Path:
    return grok_home() / "bundled" / "skills" / "docx" / "scripts"


def unpack_py() -> Path:
    return docx_scripts() / "office" / "unpack.py"


def pack_py() -> Path:
    return docx_scripts() / "office" / "pack.py"


def validate_py() -> Path:
    return docx_scripts() / "office" / "validate.py"


def replace_text_py() -> Path:
    return docx_scripts() / "replace_text.py"


def slash(path: Path | str) -> str:
    return str(path).replace("\\", "/")
