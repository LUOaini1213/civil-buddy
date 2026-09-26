---
category: tender_delivery
subcategory: strategies
priority: high
type: strategy
tags: [singapore, facade, bidbook, PSSCOC, SS654]
source: internal
updated: "2026-09-26"
harness: ">=0.6.4"
status: active
---
# Singapore façade bid-book (draft only)

English Contractor's Proposal assembled for **Harbourline Facade Pte. Ltd. (DEMO)**.

## Volumes

1. Cover & Form of Tender (PSSCOC-style; sum = `S$ [TO FILL]`)
2. Executive Summary
3. Compliance & Deviation Schedule
4. Technical Approach — SS 654:2020 (unverified, see below), Green Mark 2021 (no fake test IDs)
5. Method Statement & Programme
6. Logistics — packing **tools** only
7. WSH / bizSAFE / QA (`[TO FILL]` certificate nos.)
8. Resources, track record, prices — all `[TO FILL]`
9. Annex A packing summary · Annex B SME actions

## Red lines

- Watermark: DRAFT · NOT FOR GeBIZ submission
- Never invent UEN, BCA workhead, SGD amounts, or lab reports
- Do not use a real employer's name as the demo bidder
- UNVERIFIED: `packing_assistant/bidbook/templates_en.py` states "SS 654:2020 Code of practice for curtain walls
  (supersedes SS 381 / CP 96)". The Singapore Standards page could not be opened on 2026-09-26, so the number,
  the year and the "supersedes" lineage are not checked. A person checks them before a bid-book leaves the firm.
- Sourced SG façade facts (BCA CR16 grades and tendering limits, PFI, MOM work-at-height PTW above 3 m) live in
  `demo/kb/design/facade/web-knowledge.md` and `demo/kb/hse/safety-brief/web-knowledge.md`, each with URL and date.
