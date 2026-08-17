"""Assemble an English Singapore façade bid-book draft from parse + matrix + packing."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from packing_assistant.bidbook import templates_en as T

DEMO_BIDDER: Dict[str, str] = {
    "legal_name": "Harbourline Facade Pte. Ltd.",
    "tag": "DEMO",
    "address": "[TO FILL] · Singapore",
    "uen": "[TO FILL]",
    "workhead": "[TO FILL]",
}

REQUIRED_HEADINGS: List[str] = [
    "1. Cover & Form of Tender",
    "2. Executive Summary",
    "3. Compliance & Deviation Schedule",
    "4. Technical Approach",
    "5. Method Statement & Programme",
    "6. Logistics & Packing Evidence",
    "7. WSH, Quality & Environment",
    "8. Resources, Track Record & Commercial",
    "Annex A",
    "Annex B",
]

_DEV = {
    "covered": "No Deviation",
    "partial": "Partial Deviation",
    "gap": "Negative Deviation",
    "human_required": "Pending SME",
    "review": "Pending review",
    "pending": "To confirm",
}


def infer_project_title(text: str) -> str:
    """Prefer a short Latin/title line; otherwise the demo default."""
    for raw in (text or "").splitlines():
        s = raw.strip().strip("#").strip()
        if not s:
            continue
        if re.match(r"^[一二三四五六七八九十\d]+[、.\s]", s):
            continue
        if len(s) < 8 or len(s) > 140:
            continue
        if re.search(r"[A-Za-z]", s):
            return s[:140]
    return "Sample Singapore Façade Tender"


def _fmt_mid50(mid: Any) -> str:
    if mid is None or mid == "":
        return "—"
    try:
        n = float(mid)
    except (TypeError, ValueError):
        return str(mid)
    return f"{n * 100:.1f}%" if n <= 1.0 else f"{n:.1f}%"


def _schedule_block(requirements: List[Dict[str, Any]]) -> str:
    for r in requirements or []:
        if r.get("id") == "delivery_time" or r.get("category") == "schedule":
            snips = r.get("snippets") or []
            quoted = "; ".join(str(s) for s in snips[:3]) if snips else "(schedule clause captured)"
            return (
                "**Programme note from the invitation (unverified):**\n\n"
                f"> {quoted}\n\n"
                "Contractual completion dates remain `[TO FILL]` after planner review."
            )
    return (
        "No explicit delivery-period clause was extracted. "
        "Milestone dates remain `[TO FILL]`."
    )


def _deviation_table(matrix: Dict[str, Any]) -> str:
    rows = list((matrix or {}).get("rows") or [])
    lines = [
        "## 3. Compliance & Deviation Schedule",
        "",
        "Deviation codes: **No Deviation** (covered by tools or stated compliance) · "
        "**Partial Deviation** · **Negative Deviation** · **Pending SME**.",
        "",
        "| Ref | Requirement | Type | Status | Deviation | Owner | Proposal location |",
        "|-----|-------------|------|--------|-----------|-------|-------------------|",
    ]
    if not rows:
        lines.append("| — | (no clauses extracted) | — | — | To confirm | — | — |")
        return "\n".join(lines) + "\n"
    for r in rows:
        title = str(r.get("title") or r.get("req_id") or "").replace("|", "/")
        ref = str(r.get("requirement_ref") or r.get("req_id") or "—").replace("|", "/")
        rtype = str(r.get("requirement_type") or "—")
        st = str(r.get("status") or "pending")
        dev = _DEV.get(st, "To confirm")
        loc = str(r.get("proposal_location") or "—").replace("|", "/")
        owner = str(r.get("owner") or "—")
        lines.append(f"| {ref} | {title} | {rtype} | {st} | {dev} | {owner} | {loc} |")
    return "\n".join(lines) + "\n"


def _logistics_chapter(packing_summary: Optional[Dict[str, Any]]) -> str:
    pack = packing_summary or {}
    lines = [
        "## 6. Logistics & Packing Evidence",
        "",
        "Numbers below come from the packing **tools** (Team A/B), not from a language model.",
        "",
    ]
    if not pack:
        lines += [
            "Delivery packing was **not run** for this draft. Chapter 6 has no can_fit / mid50.",
            "",
        ]
        return "\n".join(lines)
    lines += [
        f"- **can_fit:** {pack.get('can_fit')}",
        f"- **container type:** {pack.get('container_type') or '—'}",
        f"- **containers used:** {pack.get('containers_used')}",
        f"- **N0* (tool lower bound):** {pack.get('n0')}",
        f"- **ship_ok:** {pack.get('ship_ok')}",
        f"- **mid50 (CTU mid-length mass share):** {_fmt_mid50(pack.get('mid50'))}",
        f"- **phase:** {pack.get('phase') or '—'}",
        "",
        "Lashing design, VGM declaration and bill of lading remain `[TO FILL]`.",
        "",
    ]
    return "\n".join(lines)


def _annex_a(packing_summary: Optional[Dict[str, Any]]) -> str:
    pack = packing_summary or {}
    lines = ["## Annex A — Packing summary", ""]
    if not pack:
        lines.append("No packing_summary attached.")
        return "\n".join(lines) + "\n"
    for k in (
        "can_fit",
        "container_type",
        "containers_used",
        "n0",
        "ship_ok",
        "mid50",
        "phase",
    ):
        v = pack.get(k)
        if k == "mid50":
            v = _fmt_mid50(v)
        lines.append(f"- `{k}`: {v}")
    return "\n".join(lines) + "\n"


def _annex_b(open_actions: List[Dict[str, Any]]) -> str:
    lines = [
        "## Annex B — Human / SME open actions",
        "",
        "These rows are **not** auto-closed. Directors must complete them before any submission.",
        "",
    ]
    if not open_actions:
        lines.append("- None listed (commercial / legal sign-off still required).")
        return "\n".join(lines) + "\n"
    for a in open_actions:
        lines.append(
            f"- **[{a.get('risk')}]** {a.get('title')} · {a.get('owner')} · "
            f"`{a.get('status')}` — {a.get('action')}"
        )
    return "\n".join(lines) + "\n"


def _scoring_map(handoff: Optional[Dict[str, Any]]) -> str:
    """List extracted scoring points only. Do not invent PQM weights."""
    ho = handoff or {}
    points = list(ho.get("scoring_points") or [])
    env = ho.get("envelope")
    lines = [
        "## 4b. Scoring-point map (extracted)",
        "",
        "Each row is copied from the invitation. Weights are **not** taken from the "
        "BCA PQM Framework published bands (portal title *Price Quality Method (PQM) Framework*, "
        "page last updated 26 January 2026; public CW01/CW02 construction). "
        "This ITT's scores stay `[UNSPECIFIED]` unless quoted below.",
        "",
    ]
    if env:
        lines.append(f"- **Envelope scheme in ITT:** `{env}` (verbatim detect; not invented).")
        lines.append("")
    if not points:
        lines += [
            "No scoring-point lines were extracted. Technical chapters stay a generic "
            "skeleton and must be aligned to the ITT evaluation table by a person.",
            "",
        ]
        return "\n".join(lines)
    lines += [
        "| Ref | Extracted scoring line | Response chapter | Status |",
        "|-----|------------------------|------------------|--------|",
    ]
    for p in points:
        ref = str(p.get("requirement_ref") or "—").replace("|", "/")
        text = str(p.get("text") or "").replace("|", "/")[:160]
        lines.append(f"| {ref} | {text} | §4 / tech outline | [UNSPECIFIED] |")
    lines.append("")
    return "\n".join(lines)


def build_sg_facade_bidbook(
    *,
    tender_text: str = "",
    parsed: Optional[Dict[str, Any]] = None,
    matrix: Optional[Dict[str, Any]] = None,
    packing_summary: Optional[Dict[str, Any]] = None,
    open_actions: Optional[List[Dict[str, Any]]] = None,
    project_title: Optional[str] = None,
    p0_confirmed: bool = False,
) -> Dict[str, Any]:
    """Deterministic English bid-book. Returns markdown + meta."""
    parsed = parsed or {}
    matrix = matrix or {}
    bidder = DEMO_BIDDER
    reqs = list((parsed.get("requirements") or []))
    sm = (matrix.get("summary") or {})
    title = (project_title or "").strip() or infer_project_title(tender_text)
    actions = list(open_actions or [])
    ho = parsed.get("handoff") if isinstance(parsed, dict) else None
    ctx = {
        "legal_name": bidder["legal_name"],
        "tag": bidder["tag"],
        "address": bidder["address"],
        "uen": bidder["uen"],
        "workhead": bidder["workhead"],
        "project_title": title,
        "n_req": sm.get("n", len(reqs)),
        "n_covered": sm.get("covered", 0),
        "readiness": sm.get("readiness_score", "—"),
        "n_open": len(actions),
        "schedule_block": _schedule_block(reqs),
    }
    parts = [
        f"# Contractor's Proposal (Draft) — {title}",
        "",
        "> " + T.WATERMARK.format(**ctx),
        "",
        (
            "> P0 noted by operator — still a draft, not for GeBIZ."
            if p0_confirmed
            else "> P0 qualification / reject / star items are **unconfirmed**. Not a bid decision."
        ),
        "",
        T.FORM_OF_TENDER.format(**ctx).rstrip(),
        "",
        T.EXEC_SUMMARY.format(**ctx).rstrip(),
        "",
        _deviation_table(matrix).rstrip(),
        "",
        T.TECHNICAL.format(**ctx).rstrip(),
        "",
        _scoring_map(ho).rstrip(),
        "",
        T.METHOD.format(**ctx).rstrip(),
        "",
        _logistics_chapter(packing_summary).rstrip(),
        "",
        T.WSH.format(**ctx).rstrip(),
        "",
        T.RESOURCES.format(**ctx).rstrip(),
        "",
        _annex_a(packing_summary).rstrip(),
        "",
        _annex_b(actions).rstrip(),
        "",
    ]
    markdown = "\n".join(parts)
    return {
        "schema": "tender.bidbook.sg_facade.v1",
        "jurisdiction": "SG",
        "sector": "facade_curtain_wall",
        "language": "en",
        "bidder": dict(bidder),
        "project_title": title,
        "watermark": T.WATERMARK.format(**ctx),
        "headings": list(REQUIRED_HEADINGS),
        "markdown": markdown,
        "n_chars": len(markdown),
    }
