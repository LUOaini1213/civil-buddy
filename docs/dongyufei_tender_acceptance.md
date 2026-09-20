# Tender Review Representative Acceptance Record

## Owner

Dong Yufei

## Scope

Business tools and expert skills - tender review representative case.

## Objective

Verify that the post-draft tender review can:

1. detect forbidden assertive language;
2. identify missing or pending requirement-matrix items;
3. preserve the packing result `can_fit`;
4. avoid inventing project achievements.

## Representative Input

The representative tender draft contains the forbidden phrase:

- `已具备报审条件`

The requirement matrix contains three rows:

- `REQ-001`: covered
- `REQ-002`: missing
- `REQ-003`: pending

Packing input:

- `can_fit: true`

## Expected Result

- forbidden phrases detected: 1
- matrix gaps detected: 2
- gap IDs: `REQ-002`, `REQ-003`
- `can_fit` remains `true`
- `mutated_can_fit` remains `false`
- no project achievements are automatically filled

## Automated Acceptance Test

Test file:

`scripts/test_tender_review_acceptance.py`

Command:

`python -m pytest scripts/test_tender_review_acceptance.py -v`

Result:

`1 passed`

## Acceptance Conclusion

PASS

The representative tender-review case successfully verifies forbidden-language detection, requirement-gap detection, packing-result preservation, and prevention of fabricated project achievements.

## Full Workflow Acceptance

A representative end-to-end tender workflow was executed using:

### Tender Requirements

- Business license copy is required.
- Technical proposal is worth 20 points and requires a construction-specific plan.
- Required project duration is 60 calendar days.

### Bid Response

- Business license copy was stated as attached.
- Construction-plan material was marked as pending.
- Supplier stated a duration of 999 calendar days.

### Workflow Result

The workflow completed successfully:

- `ok: true`
- `submit_blocked: true`

The tender requirement remained:

- project duration: `60` calendar days

The supplier's stated `999` calendar days did not replace or modify the original tender requirement.

### Compliance Review Result

The generated compliance workbook reported:

- project duration requirement: `conflict_requires_review` — the response's 999 calendar days is pointed out against the tender's 60 ("工期：响应 999日历天 超过招标 60日历天，待人工核验"); it is stated, not judged
- construction-specific plan requirement: `not_matched`
- business-license evidence: `candidate_requires_review`
- unresolved compliance items: `3` — one per tender line

_Updated 2026-09-20. When this record was first written the duration row read `not_matched` and there were `5` unresolved items: the same requirement was listed three times and numeric mismatches were not compared. Both changed in #32. The values above are now asserted at the end of `scripts/run_dongyufei_tender_case.py`, which CI runs through `scripts/test_acceptance_cases.py` — if the workflow changes again, this record fails instead of going stale._

The workflow therefore preserves the distinction between tender requirements and supplier response evidence and keeps uncertain matches subject to human review.

### Generated Artifacts

The workflow generated actual review artifacts including:

- `handoff.json`
- `tender-extract.md`
- `tender-extract.docx`
- `worker-bid-tech/bid-tech.md`
- `worker-bid-tech/bid-tech.docx`
- `worker-bid-compliance/bid-compliance.md`
- `worker-bid-compliance/bid-compliance.docx`
- `worker-bid-compliance/bid-compliance.xlsx`
- `collaboration-review.md`
- `collaboration-review.docx`
- `collaboration-review.xlsx`

### Full Workflow Conclusion

PASS

The end-to-end workflow successfully generated review documents and compliance workbooks, preserved the original 60-day tender requirement, did not treat the supplier's 999-day statement as a tender requirement, identified unresolved compliance items, and retained human review before submission.