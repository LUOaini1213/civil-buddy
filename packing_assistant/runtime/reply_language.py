"""Which language a reply to this request is written in: English for an English request, Chinese otherwise.

A request is English when, once file names, quoted text and links are set aside, it has no Chinese character and
at least two Latin words. A mixed request ("按 facade_panels.xlsx 装柜, 40HQ") stays Chinese, as before. Only the
notes this system writes itself follow it (the link reply, the question note, approval and guard notices); the
posts' own templates are not translated. When the workbench page is switched to English (using_page_language),
those notes are English for every request on it.
"""
from __future__ import annotations

import re
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator

_SET_ASIDE = re.compile(r"```[\s\S]*?```|`[^`\n]*`|“[^”]*”|「[^」]*」|『[^』]*』|\"[^\"\n]*\"|https?://\S+"
                        r"|[\w.\-㐀-鿿]+\.(?:xlsx|xlsm|xls|csv|md|docx|doc|pdf|txt|json|dxf|dwg)\b", re.I)
_CJK = re.compile(r"[　-〿㐀-䶿一-鿿＀-￯]")
_WORD = re.compile(r"[A-Za-z]{2,}")


#: the language the workbench page is shown in ("en" / "zh" / "" when no page asked), set per request by the web
#: host (demo/ui_lang.py) and per turn by the thread that runs it. English on the page makes this system's own notes
#: English whatever the request is written in; Chinese on the page changes nothing (an English request still gets
#: English notes). It never changes what is routed, checked or approved.
_PAGE_LANGUAGE: ContextVar[str] = ContextVar("civil_page_language", default="")


def normalize_language(value: object) -> str:
    """"en" or "zh" for what a page may send ("en", "en-GB", "zh-CN", …); "" for anything else."""
    text = str(value or "").strip().lower()
    if re.fullmatch(r"en(?:[-_][a-z0-9]{1,8})*", text):
        return "en"
    if re.fullmatch(r"zh(?:[-_][a-z0-9]{1,8})*", text):
        return "zh"
    return ""


def page_language() -> str:
    return _PAGE_LANGUAGE.get()


@contextmanager
def using_page_language(value: object) -> Iterator[str]:
    token = _PAGE_LANGUAGE.set(normalize_language(value))
    try:
        yield _PAGE_LANGUAGE.get()
    finally:
        _PAGE_LANGUAGE.reset(token)


def english_request(text: object) -> bool:
    if _PAGE_LANGUAGE.get() == "en":
        return True
    if not isinstance(text, str) or not text.strip():
        return False
    rest = _SET_ASIDE.sub(" ", text)
    return not _CJK.search(rest) and len(_WORD.findall(rest)) >= 2
