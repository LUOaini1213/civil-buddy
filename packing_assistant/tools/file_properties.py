"""What a file says about who made it - the properties that travel WITH a bid file when it is handed in.

An evaluation committee may read them: bid files from different bidders that share an author, a company name or a
"last modified by" are one of the listed grounds for a finding of collusion ("投标文件制作机器码一致 / 文档属性雷同"), and a
bid file whose properties name ANOTHER company is how a borrowed template gives itself away. None of that is judged
here. The properties are read and laid side by side, literally, so that a person can see them before the files go out.

    read(path)      {"作者": …, "最后修改人": …, "公司": …, "软件": …, "创建时间": …, "修改时间": …} - only what the file holds
    differing(...)  the properties on which our own files do not agree, as sentences

Word / Excel / PowerPoint (OOXML: docProps/core.xml, docProps/app.xml) and PDF (/Info). No third-party reader is
needed for OOXML; PDF uses pypdf, which the project already depends on. A file that cannot be read gives {}.
"""
from __future__ import annotations

import re
import zipfile
from pathlib import Path
from typing import Dict, List, Mapping, Sequence, Tuple
from xml.etree import ElementTree

#: shown in this order; the key is what the draft prints
FIELDS: Tuple[str, ...] = ("作者", "最后修改人", "公司", "软件", "创建时间", "修改时间")
_WHO: Tuple[str, ...] = ("作者", "最后修改人", "公司")     # the ones that name somebody
_CORE = {"creator": "作者", "lastModifiedBy": "最后修改人", "created": "创建时间", "modified": "修改时间"}
_APP = {"Company": "公司", "Application": "软件"}
_PDF = {"/Author": "作者", "/Creator": "软件", "/Producer": "软件", "/CreationDate": "创建时间", "/ModDate": "修改时间", "/Company": "公司"}
_MAX_XML = 2_000_000
VERSION = re.compile(r"\s*(?:v|V|版本)?\s*\d[\d.]*(?:\s*\([^)]*\))?\s*$")


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _xml_values(raw: bytes, wanted: Mapping[str, str]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    if len(raw) > _MAX_XML or b"<!DOCTYPE" in raw[:2000] or b"<!ENTITY" in raw[:4000]:
        return out      # a properties part is a few hundred bytes; anything that declares entities is not read
    try:
        root = ElementTree.fromstring(raw)
    except ElementTree.ParseError:
        return out
    for node in root.iter():
        name = wanted.get(_local(node.tag))
        text = (node.text or "").strip()
        if name and text and name not in out:
            out[name] = text[:120]
    return out


def _pdf_date(value: str) -> str:
    """D:20300318093000+08'00' -> 2030-03-18 09:30:00"""
    found = re.match(r"D?:?(\d{4})(\d{2})(\d{2})(\d{2})?(\d{2})?(\d{2})?", value or "")
    if not found:
        return (value or "")[:40]
    year, month, day, hour, minute, second = found.groups()
    return f"{year}-{month}-{day}" + (f" {hour}:{minute or '00'}:{second or '00'}" if hour else "")


def read(path: Path) -> Dict[str, str]:
    """The properties the file holds, in ``FIELDS`` order; {} when it holds none or cannot be read."""
    path = Path(path)
    found: Dict[str, str] = {}
    suffix = path.suffix.lower()
    try:
        if suffix in (".docx", ".xlsx", ".pptx", ".docm", ".xlsm"):
            with zipfile.ZipFile(path) as archive:
                names = set(archive.namelist())
                if "docProps/core.xml" in names:
                    found.update(_xml_values(archive.read("docProps/core.xml"), _CORE))
                if "docProps/app.xml" in names:
                    found.update(_xml_values(archive.read("docProps/app.xml"), _APP))
        elif suffix == ".pdf":
            from pypdf import PdfReader

            info = PdfReader(str(path)).metadata or {}
            for key, name in _PDF.items():
                value = str(info.get(key) or "").strip()
                if not value:
                    continue
                if name in ("创建时间", "修改时间"):
                    value = _pdf_date(value)
                if name == "软件" and found.get("软件") and value not in found["软件"]:
                    value = f"{found['软件']} / {value}"
                found[name] = value[:120]
    except Exception:   # noqa: BLE001 - a damaged or protected file has no readable properties; that is all there is to say
        return {}
    for name in ("创建时间", "修改时间"):
        if name in found:
            found[name] = found[name].replace("T", " ").rstrip("Z")
    if "软件" in found:
        # the program, not its build: a version number is no quantity of the bid, and the draft holds no figure nobody wrote
        found["软件"] = " / ".join(part for part in (VERSION.sub("", piece).strip() for piece in found["软件"].split(" / ")) if part)
    return {name: found[name] for name in FIELDS if found.get(name)}


def differing(files: Sequence[Tuple[str, Mapping[str, str]]]) -> List[str]:
    """Sentences for the properties that name somebody and are not the same in all of our files - "作者：技术标.docx 写的是
    「张工」，商务标.docx 写的是「Administrator」". One file, or files that agree, give none."""
    out: List[str] = []
    for name in _WHO:
        said = [(title, props[name]) for title, props in files if props.get(name)]
        if len({value for _, value in said}) >= 2:
            out.append(f"{name}：" + "，".join(f"{title} 写的是「{value}」" for title, value in said))
    return out
