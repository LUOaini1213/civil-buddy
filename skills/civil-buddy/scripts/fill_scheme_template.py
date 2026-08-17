"""Fill scheme-cn-a4.docx via bundled replace_text.py --map --all-files."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from paths import (
    CHAPTER_HEADINGS,
    TEMPLATE_DEFAULT,
    TOKENS,
    docx_scripts,
    pack_py,
    slash,
    unpack_py,
    validate_py,
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _strip_md(text: str) -> str:
    lines = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("#"):
            s = re.sub(r"^#+\s*", "", s)
        lines.append(s.rstrip())
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines) if lines else "待填"


def _split_chapters(draft: str) -> dict[str, str]:
    parts: dict[str, list[str]] = {}
    current = None
    heading = re.compile(r"^##\s+(\d+)\s+(\S.*)$")
    for line in draft.splitlines():
        m = heading.match(line.strip())
        if m:
            num, title = m.group(1), m.group(2)
            current = None
            for token, (want_num, key) in CHAPTER_HEADINGS.items():
                if num == want_num or key in title:
                    current = token
                    parts[current] = []
                    break
            continue
        if current is not None:
            parts[current].append(line)
    out = {}
    for token in CHAPTER_HEADINGS:
        body = _strip_md("\n".join(parts.get(token, [])))
        out[token] = body or "待填"
    return out


def _split_citations(text: str) -> tuple[str, str]:
    verified_lines: list[str] = []
    unverified_lines: list[str] = []
    bucket = None
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("#"):
            title = re.sub(r"^#+\s*", "", line)
            if "已核实" in title:
                bucket = "v"
                continue
            if "未核实" in title or "未核" in title or "UNSPECIFIED" in title:
                bucket = "u"
                continue
        if not line or bucket is None:
            continue
        if bucket == "v":
            verified_lines.append(line)
        else:
            unverified_lines.append(line)
    verified = "\n".join(verified_lines).strip() or "（无）"
    header = "全名 | 年份 | 条款 | 状态"
    if not unverified_lines:
        unverified = header
    else:
        body = "\n".join(unverified_lines).strip()
        unverified = body if header in body else header + "\n" + body
    return verified, unverified


def _run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.stderr.write(proc.stdout or "")
        sys.stderr.write(proc.stderr or "")
        raise SystemExit(proc.returncode)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--template", type=Path, default=TEMPLATE_DEFAULT)
    p.add_argument("--draft", type=Path, required=True)
    p.add_argument("--assumptions", type=Path, required=True)
    p.add_argument("--citations", type=Path, required=True)
    p.add_argument("--jurisdiction", required=True, choices=("CN", "SG", "EU", "DUAL"))
    p.add_argument("--stamp", required=True)
    p.add_argument("--project-name", required=True)
    p.add_argument("--short-name", default="")
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()

    replace_mod = docx_scripts() / "replace_text.py"
    for tool in (unpack_py(), replace_mod, pack_py(), validate_py()):
        if not tool.is_file():
            sys.stderr.write(f"missing bundled tool: {tool}\n")
            return 2
    if not args.template.is_file():
        sys.stderr.write(f"missing template: {args.template}\n")
        return 2

    chapters = _split_chapters(_read(args.draft))
    cited_v, cited_u = _split_citations(_read(args.citations))
    assumptions = _strip_md(_read(args.assumptions))
    short = args.short_name or args.project_name

    mapping = {
        "{{PROJECT_NAME}}": args.project_name,
        "{{SHORT_NAME}}": short,
        "{{STAMP}}": args.stamp,
        "{{JURISDICTION}}": args.jurisdiction,
        "{{ASSUMPTIONS}}": assumptions,
        "{{CITED_VERIFIED}}": cited_v,
        "{{CITED_UNVERIFIED}}": cited_u,
        **chapters,
    }
    for token in TOKENS:
        mapping.setdefault(token, "待填")
        if not str(mapping[token]).strip():
            mapping[token] = "待填"

    out_dir = args.out.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    map_path = out_dir / "replacements.json"
    map_path.write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")

    with tempfile.TemporaryDirectory(prefix="civil-buddy-fill-") as tmp:
        tmp_path = Path(tmp)
        work = tmp_path / "work.docx"
        unpacked = tmp_path / "unpacked"
        shutil.copy2(args.template, work)
        _run([sys.executable, str(unpack_py()), str(work), str(unpacked)])
        # replace_text.py CLI uses SIGPIPE (missing on Windows). Import instead.
        if str(docx_scripts()) not in sys.path:
            sys.path.insert(0, str(docx_scripts()))
        from replace_text import find_xml_files, replace_text_in_file

        for xml_path in find_xml_files(unpacked, all_files=True):
            replace_text_in_file(xml_path, mapping)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        _run(
            [
                sys.executable,
                str(pack_py()),
                slash(unpacked) + "/",
                str(args.out),
                "--original",
                str(work),
            ]
        )
    _run([sys.executable, str(validate_py()), str(args.out)])
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
