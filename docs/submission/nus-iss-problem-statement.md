> **For the team: read this before using the file.**
>
> - This file is in a public repository, so the partner is never named or described in a way that identifies it here. `{{SME_NAME}}` and `{{SME_CRS}}` are tokens. Their values live only in the untracked `docs/submission/sme.local.json`: copy `sme.local.example.json`, fill it with confirmed facts only, and never commit it.
> - `scripts/submission/build_nus_docs.py` fills tokens only in the two PDFs (Technical Document and Business Proposal). It does not build this file. The text pasted into the submission email must therefore come from a built output, or have every token replaced by hand with its value from `sme.local.json`.
> - Before pasting, resolve every `[TEAM TO FILL]` and `[TEAM TO VERIFY]`, and delete this box and the notes at the end. Never paste the filled-in text back into this file.
> - The SME track's problem is the partner's own. Write "SME" for the partner only if the organisers confirm that it qualifies for the SME track.

# civil-buddy: Problem Statement (SME track)

Team Mintang · Team Code PJ2U63AF · draft 2026-09-26, for the submission email on 2026-09-28

## Problem statement

{{SME_NAME}} is a Singapore curtain-wall SME, registered with BCA under {{SME_CRS}}. In three of its jobs, a wrong number or verdict is costly. In its own words: [TEAM TO FILL: the partner's own words, the same text as SME_FEEDBACK in sme.local.json, shortened to one sentence].

First, tender review: each façade enquiry must be read clause by clause for the workhead, duration, bonds, liquidated damages, retention, mock-ups, testing and PE-endorsed submissions, and a clause missed at tender still binds after award. Second, packing and shipping: factory-built unitised curtain-wall panels can weigh over 500 kg, sometimes 1,000 kg, so crate and container counts cannot be guessed from a spreadsheet. Third, installation paperwork: daily reports, method statements and, on a worksite where a person could fall more than 3 m, a permit-to-work for work at height. In 2025, falls from height were construction's leading cause of fatal and major injuries. [TEAM TO FILL: the partner's volumes — tenders per month, shipments per project, documents per week — only as it confirms them.]

How might an agent draft and check all three jobs from the firm's own files, with code computing every number, missing facts left blank, and a licensed person signing every high-risk document?

## One-line version

{{SME_NAME}}, a Singapore curtain-wall contractor, needs an agent that reviews façade tenders, plans panel crates and containers, and drafts installation paperwork from its own files: code computes every number, gaps stay blank, and a licensed person signs.

---

*Notes for the team (not part of the email text):*

- **Word count.** The problem statement above is about 165 words (164 by a whitespace count) with each token and placeholder counted as one word. Keep each of the two `[TEAM TO FILL]` fills to about 15 words and the whole stays between 120 and 200 words. The one-line version is 37 words.
- **The representative.** The statement does not name our team member's role at the partner, to keep within 200 words. The Business Proposal (§2.2 and §14) gives it through the `{{SME_REP_ROLE}}` token; if the email needs it too, add one short sentence by hand.
- **Sources for the facts.** Units over 500 kg, sometimes 1,000 kg: YKK AP's technical page on unitized curtain walls (a façade manufacturer's page, undated, accessed 26 Sep 2026). Permit-to-work on a worksite where a person could fall more than 3 m: the Workplace Safety and Health (Work at Heights) Regulations 2013 and MOM's factsheet on the 2014 amendment (the permit applies at workplaces defined as factories, which typically include construction worksites, unless effective edge protection removes the risk). Falls from height as construction's leading cause of fatal and major injuries in 2025 (43): MOM's *Workplace Safety and Health Report 2025* (national statistics, March 2026). The CR16 Curtain Walls workhead: BCA's CR registration requirements (June 2025). Full references are in `nus-iss-business.md`.
- **The clause list is generic.** Workhead, duration, bonds, liquidated damages, retention, mock-ups, testing and PE-endorsed submissions are topics a façade enquiry can carry; our synthetic enquiry carries them. No source says how often the partner meets them, so the statement does not say.
- **Deliberately not claimed.** Where the partner's panels are made, how it ships them, how façade packages are procured (the only source is a consultancy's opinion piece), and any volume, headcount or quote from the partner beyond what it confirms.
- **The partner's words.** The partner has confirmed the collaboration in writing. Fill the "own words" placeholder only with what it said and agreed to be quoted; otherwise delete that sentence.
