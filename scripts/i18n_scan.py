#!/usr/bin/env python3
"""Where the workbench shows Chinese, and which of it goes through the language switch.

A small JavaScript lexer (comments, the three string forms, template ``${}`` nesting, regex literals) that lists
every string literal with a Chinese character in the workbench's scripts, and every ``tr("…")`` message id. Used by
scripts/test_workbench_i18n.py (every message id has an English entry, no English entry is stale, no Chinese
literal is left unwrapped outside the allow-list) and, with ``--report``, prints the inventory counts.

    python scripts/i18n_scan.py --report
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "demo" / "static"
#: the workbench page (demo/static/index.html) and every script it loads; the sub-pages (/cad, /engineering,
#: /logistics and their planning / routing / schedule pages) are separate pages and are not switched yet
SCRIPTS = ("app.js", "i18n.js", "chat-stream.js", "fixcard.js", "docpreview.js", "voice.js", "studio.js",
           "modules/auth.js", "modules/deliverables.js", "modules/drafts.js", "modules/i18n.js",
           "modules/session-nav.js", "modules/session-watch.js", "modules/toast.js", "modules/turn-stream.js",
           "modules/uploads.js")
HAN = re.compile(r"[\u3400-\u9fff]")
_KEYWORDS_BEFORE_REGEX = {"return", "typeof", "case", "in", "of", "delete", "void", "throw", "new", "else", "do",
                          "yield", "await", "instanceof"}


def lex(src: str):
    """Yield (kind, start, end, text) for 'string', 'template', 'regex' tokens at the top level of ``src``.

    Template tokens carry their parts: text is the raw source between the backticks; nested code inside ``${}`` is
    lexed recursively by the caller through :func:`template_parts`."""
    i, n = 0, len(src)
    prev = ""   # last significant token class: "id", "num", "punct:<c>"
    while i < n:
        c = src[i]
        if c in " \t\r\n":
            i += 1
            continue
        if src.startswith("//", i):
            j = src.find("\n", i)
            i = n if j < 0 else j
            continue
        if src.startswith("/*", i):
            j = src.find("*/", i + 2)
            i = n if j < 0 else j + 2
            continue
        if c in "\"'":
            j = i + 1
            while j < n and src[j] != c:
                if src[j] == "\\":
                    j += 1
                elif src[j] == "\n":
                    break
                j += 1
            yield ("string", i, j + 1, src[i:j + 1])
            i = j + 1
            prev = "id"
            continue
        if c == "`":
            j = _template_end(src, i)
            yield ("template", i, j, src[i:j])
            i = j
            prev = "id"
            continue
        if c == "/":
            word = prev[3:] if prev.startswith("id:") else ""
            regex_ok = (prev == "" or prev.startswith("punct:") and prev[-1] not in ")]") or word in _KEYWORDS_BEFORE_REGEX
            if regex_ok:
                j = i + 1
                in_class = False
                while j < n:
                    ch = src[j]
                    if ch == "\\":
                        j += 2
                        continue
                    if ch == "[":
                        in_class = True
                    elif ch == "]":
                        in_class = False
                    elif ch == "/" and not in_class:
                        break
                    elif ch == "\n":
                        break
                    j += 1
                j += 1
                while j < n and (src[j].isalpha()):
                    j += 1
                yield ("regex", i, j, src[i:j])
                i = j
                prev = "id"
                continue
            i += 1
            prev = "punct:/"
            continue
        if c.isalpha() or c in "_$":
            j = i
            while j < n and (src[j].isalnum() or src[j] in "_$"):
                j += 1
            prev = "id:" + src[i:j]
            i = j
            continue
        if c.isdigit():
            j = i
            while j < n and (src[j].isalnum() or src[j] in "._"):
                j += 1
            prev = "num"
            i = j
            continue
        prev = "punct:" + c
        i += 1


def _template_end(src: str, i: int) -> int:
    j, n = i + 1, len(src)
    while j < n:
        ch = src[j]
        if ch == "\\":
            j += 2
            continue
        if ch == "`":
            return j + 1
        if src.startswith("${", j):
            j = _expr_end(src, j + 2)
            continue
        j += 1
    return n


def _expr_end(src: str, i: int) -> int:
    """Index just past the ``}`` closing a ``${`` expression that starts at ``i``."""
    depth, j, n = 1, i, len(src)
    while j < n:
        ch = src[j]
        if ch in "\"'":
            k = j + 1
            while k < n and src[k] != ch:
                k += 2 if src[k] == "\\" else 1
            j = k + 1
            continue
        if ch == "`":
            j = _template_end(src, j)
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return j + 1
        j += 1
    return n


def template_parts(text: str):
    """[('text', raw) | ('expr', code)] for a template literal's source (backticks included)."""
    parts, j, n, buf = [], 1, len(text) - 1, ""
    while j < n:
        if text[j] == "\\":
            buf += text[j:j + 2]
            j += 2
            continue
        if text.startswith("${", j):
            end = _expr_end(text, j + 2)
            parts.append(("text", buf))
            buf = ""
            parts.append(("expr", text[j + 2:end - 1]))
            j = end
            continue
        buf += text[j]
        j += 1
    parts.append(("text", buf))
    return parts


def han_literals(src: str):
    """Every literal holding a Chinese character, templates included (their static text, or a nested literal)."""
    out = []

    def walk(code: str, base: int):
        for kind, start, end, text in lex(code):
            if kind == "template":
                parts = template_parts(text)
                if any(k == "text" and HAN.search(v) for k, v in parts):
                    out.append(("template", base + start, base + end, text))
                else:
                    offset = 1
                    for k, v in parts:
                        if k == "expr":
                            walk(v, base + start + offset + 2)
                            offset += len(v) + 3
                        else:
                            offset += len(v)
            elif HAN.search(text):
                out.append((kind, base + start, base + end, text))

    walk(src, 0)
    return out


_WRAPPED = re.compile(r"(?<![\w$.])tr\(\s*$")
_SHOWN_KEY = re.compile(r"\b(?:ch|name|desc|badge):\s*$")


def _blocks(src: str, begin: str, end: str) -> list[tuple[int, int]]:
    """(start, end) offsets of the regions between a ``begin`` and an ``end`` marker comment."""
    out, at = [], 0
    while True:
        i = src.find(begin, at)
        if i < 0:
            return out
        j = src.find(end, i)
        j = len(src) if j < 0 else j
        out.append((i, j))
        at = j + 1


def message_ids(src: str) -> list[str]:
    """The literal first argument of every ``tr(...)`` call (plain strings only, as the wrapper writes them), and in
    an ``i18n: shown-begin`` / ``i18n: shown-end`` block the ``ch`` / ``name`` / ``desc`` / ``badge`` values: data
    that is also drawn, through tr() at the place it is drawn."""
    ids = []
    shown = _blocks(src, "i18n: shown-begin", "i18n: shown-end")
    for kind, start, end, text in lex(src):
        if kind != "string":
            continue
        before = src[max(0, start - 16):start]
        if _WRAPPED.search(before) or (any(a <= start < b for a, b in shown) and _SHOWN_KEY.search(before)):
            ids.append(json.loads(text) if text.startswith('"') else json.loads('"' + text[1:-1].replace('"', '\\"') + '"'))
    return ids


def unwrapped(src: str) -> list[tuple[int, str]]:
    """(line, literal) for every Chinese string or template literal that is not the message of a ``tr()`` call and
    is not kept on purpose: a line marked ``i18n: keep`` (data matched against what is typed or what the server
    wrote, the sign-off sentences), or a block between ``i18n: keep-begin`` and ``i18n: keep-end`` (or ``shown-``,
    whose drawn values are messages, see message_ids). Regex literals match text and are never messages."""
    kept_ranges = _blocks(src, "i18n: keep-begin", "i18n: keep-end") + _blocks(src, "i18n: shown-begin", "i18n: shown-end")
    kept_lines = {src.count("\n", 0, m.start()) + 1 for m in re.finditer(r"i18n: keep\b(?!-)", src)}
    out = []
    for kind, start, end, text in han_literals(src):
        if kind == "regex" or _WRAPPED.search(src[max(0, start - 16):start]):
            continue
        number = src.count("\n", 0, start) + 1
        if number not in kept_lines and not any(a <= start < b for a, b in kept_ranges):
            out.append((number, text))
    return out


def html_ids(html: str) -> list[str]:
    """Message ids the page's static markup asks for, in document order: the text of a data-i18n element (spaces
    collapsed, as i18n.js reads it), the inner HTML of a data-i18n="html" one, and each attribute named in
    data-i18n-attr."""
    from html.parser import HTMLParser

    inner = iter(m.group(2).strip() for m in re.finditer(r'<(\w+)\b[^>]*\bdata-i18n="html"[^>]*>(.*?)</\1>', html, re.S))
    void = {"input", "br", "img", "meta", "link", "hr", "source", "wbr", "col", "area", "base", "embed", "track"}
    ids: list[str] = []

    class Parser(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.stack = []

        def handle_starttag(self, tag, attrs):
            a = dict(attrs)
            for name in (a.get("data-i18n-attr") or "").split():
                if a.get(name):
                    ids.append(a[name])
            if tag in void:
                return
            if a.get("data-i18n") == "html":
                ids.append(next(inner))
                self.stack.append([tag, None])
            elif "data-i18n" in a:
                self.stack.append([tag, ""])
            elif self.stack:
                self.stack.append([tag, None])

        def handle_startendtag(self, tag, attrs):
            a = dict(attrs)
            for name in (a.get("data-i18n-attr") or "").split():
                if a.get(name):
                    ids.append(a[name])

        def handle_endtag(self, tag):
            if not self.stack or tag in void:
                return
            item = self.stack.pop()
            if item[1] is not None:
                ids.append(" ".join(item[1].split()))

        def handle_data(self, data):
            for item in reversed(self.stack):
                if item[1] is not None:
                    item[1] += data
                    break
                break

    Parser().feed(html)
    return ids


def html_uncovered(html: str) -> list[str]:
    """Chinese text in the page body that no data-i18n element carries (comments, scripts and the language
    buttons' own labels aside)."""
    from html.parser import HTMLParser

    body = html[html.index("<body"):]
    void = {"input", "br", "img", "meta", "link", "hr", "source", "wbr", "col", "area", "base", "embed", "track"}
    out: list[str] = []

    class Parser(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.stack = []

        def handle_starttag(self, tag, attrs):
            if tag in void:
                return
            a = dict(attrs)
            covered = "data-i18n" in a or "data-cb-lang" in a or tag in {"script", "style"}
            self.stack.append(covered or bool(self.stack and self.stack[-1]))

        def handle_endtag(self, tag):
            if self.stack and tag not in void:
                self.stack.pop()

        def handle_data(self, data):
            if HAN.search(data) and not (self.stack and self.stack[-1]):
                out.append(" ".join(data.split()))

    Parser().feed(body)
    return out


def english_dictionary() -> dict:
    text = (STATIC / "i18n" / "en.js").read_text(encoding="utf-8")
    body = text[text.index("{"):text.rindex("}") + 1]
    return json.loads(body)


def report() -> dict:
    rows = {}
    for name in SCRIPTS:
        src = (STATIC / name).read_text(encoding="utf-8")
        lits = han_literals(src)
        ids = message_ids(src)
        wrapped = sum(1 for kind, start, end, text in lits if _WRAPPED.search(src[max(0, start - 16):start]))
        regex = sum(1 for kind, *_ in lits if kind == "regex")
        rows[name] = {"chinese_literals": len(lits), "wrapped": wrapped, "regex_patterns": regex,
                      "kept_as_data": len(lits) - wrapped - regex - len(unwrapped(src)), "unwrapped": len(unwrapped(src)),
                      "message_ids": len(set(ids))}
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    rows["index.html"] = {"message_ids": len(html_ids(html))}
    return rows


if __name__ == "__main__":
    if "--report" in sys.argv:
        print(json.dumps(report(), ensure_ascii=False, indent=1))
    else:
        for name in sys.argv[1:]:
            src = Path(name).read_text(encoding="utf-8")
            for kind, start, end, text in han_literals(src):
                line = src.count("\n", 0, start) + 1
                print(f"{name}:{line}: {kind}: {text[:160]}")
