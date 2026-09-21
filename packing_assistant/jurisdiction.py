"""Shared jurisdiction routing from explicit context, with no default country."""

from __future__ import annotations

import re

#: a code standing alone. Inside a document number it is not one: "LJZB-2026-SG-0418" - SG is 施工, and nearly
#: every Chinese construction tender number carries it.
_CODES = re.compile(r"(?<![A-Za-z0-9_\-/.])(CN|SG|EU|DUAL)(?![A-Za-z0-9_\-/])", re.IGNORECASE)
_CN_STANDARD = re.compile(r"(?<![A-Za-z])(?:JGJ(?:/T)?|GB(?:/T)?\s*\d{4,})", re.IGNORECASE)
_CN_ORDER = re.compile(r"37\s*号令")
_SG_AUTHORITY = re.compile(r"(?<![A-Za-z])(?:IRAS|PSSCOC|GeBIZ|BCA|MOM\s+WSH)(?![A-Za-z])", re.IGNORECASE)
_CN_NAMES = (
    "中国", "中国大陆", "中华人民共和国", "住建部", "国内定额", "配合比设计规程",
    "监理规范", "归档规范", "特种设备安全法", "劳动合同法", "就业促进法", "人力资源市场",
)


def infer_jurisdiction(text: str, previous: str = "") -> str:
    """Return CN, SG, EU, DUAL, or literal UNSPECIFIED.

    Explicit current signals take precedence over the saved session value.
    Standard/authority names retain the existing expert-router signals; this
    routing hint does not establish a regulation's applicability or validity.
    """
    blob = text or ""
    found = {match.upper() for match in _CODES.findall(blob)}
    if "DUAL" in found or "双辖区" in blob or "多辖区" in blob:
        return "DUAL"
    if any(name in blob for name in _CN_NAMES) or _CN_STANDARD.search(blob) or _CN_ORDER.search(blob):
        found.add("CN")
    if "新加坡" in blob or "singapore" in blob.casefold() or _SG_AUTHORITY.search(blob):
        found.add("SG")
    if "欧盟" in blob or "欧洲联盟" in blob or "european union" in blob.casefold() or "eurocode" in blob.casefold():
        found.add("EU")
    if len(found) > 1:
        return "DUAL"
    if found:
        return next(iter(found))
    saved = (previous or "").strip().upper()
    return saved if saved in {"CN", "SG", "EU", "DUAL"} else "UNSPECIFIED"
