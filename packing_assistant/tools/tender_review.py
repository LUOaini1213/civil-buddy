"""成稿后再审一岗：禁语 + 矩阵缺项。不填业绩，不改 can_fit。

This is a second review step beyond write-scan scan_forbidden.
Pure function over (draft, matrix, packing_summary).
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

# Same assertive statutory phrases as skills/.../scan_forbidden_inventions.py
ASSERTIVE = (
    "可交差",
    "可报审",
    "报审通过",
    "可提交专家论证",
    "请专家论证",
    "请监理审核后开工",
    "请监理审核",
    "可以开工",
    "已具备报审条件",
)

GAP_STATUSES = frozenset(
    {"gap", "pending", "missing", "uncovered", "open", "partial"}
)


def forbidden_hits(text: str) -> List[str]:
    blob = text or ""
    return [p for p in ASSERTIVE if p in blob]


def gap_rows(matrix: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = (matrix or {}).get("rows") or []
    gaps: List[Dict[str, Any]] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        status = str(r.get("status") or "")
        missing = bool(r.get("missing"))
        if missing or status in GAP_STATUSES:
            gaps.append(
                {
                    "req_id": r.get("req_id") or r.get("id"),
                    "title": r.get("title"),
                    "status": status or ("missing" if missing else "gap"),
                    "exact_text": r.get("exact_text"),
                    "owner": r.get("owner"),
                }
            )
    return gaps


def review_draft(
    *,
    draft: str = "",
    matrix: Optional[Dict[str, Any]] = None,
    packing_summary: Optional[Dict[str, Any]] = None,
    tech_outline: Optional[Dict[str, Any]] = None,
    bidbook_markdown: str = "",
) -> Dict[str, Any]:
    """Second-pass compliance. Copies can_fit; never fills 业绩."""
    outline_md = ""
    if isinstance(tech_outline, dict):
        outline_md = str(tech_outline.get("markdown") or "")
    blob = "\n".join(x for x in (draft, outline_md, bidbook_markdown) if x)
    hits = forbidden_hits(blob)
    gaps = gap_rows(matrix)
    can_fit = None
    if isinstance(packing_summary, dict) and "can_fit" in packing_summary:
        can_fit = packing_summary.get("can_fit")
    return {
        "schema": "tender.review.v1",
        "ok": True,
        "product_mainline": "C_tender_delivery",
        "step": "post_draft_review",
        "beyond": "scan_forbidden",
        "forbidden_hits": hits,
        "gaps": gaps,
        "缺项": gaps,
        "can_fit": can_fit,
        "packing_summary": {"can_fit": can_fit} if packing_summary is not None else None,
        "mutated_can_fit": False,
        "achievements_filled": [],
        "业绩": [],
        "n_forbidden": len(hits),
        "n_gaps": len(gaps),
    }


def review_from_pipeline(pipe: Dict[str, Any]) -> Dict[str, Any]:
    """Drive review from a shipped tender pipeline result."""
    outline = pipe.get("tech_outline") or {}
    bid = pipe.get("bidbook") or {}
    package = pipe.get("response_package") or {}
    draft = "\n".join(
        [
            str(outline.get("markdown") or pipe.get("tech_outline_markdown") or ""),
            str(bid.get("markdown") or pipe.get("bidbook_markdown") or ""),
            str(package.get("markdown") or pipe.get("export_markdown") or ""),
        ]
    )
    return review_draft(
        draft=draft,
        matrix=pipe.get("matrix"),
        packing_summary=pipe.get("packing_summary"),
        tech_outline=outline,
        bidbook_markdown=str(bid.get("markdown") or ""),
    )
