> **For the team: read this before using the file.**
>
> - This file is in a public repository, so the partner is never named or described in a way that identifies it here. `{{SME_NAME}}`, `{{SME_CRS}}` and `{{SME_FEEDBACK}}` are tokens. Their values live only in the untracked `docs/submission/sme.local.json`: copy `sme.local.example.json`, fill it with confirmed facts only, and never commit it.
> - `scripts/submission/build_nus_docs.py` fills tokens only in the two PDFs (Technical Document and Business Proposal). It does not build this file. The text pasted into the submission form is kept outside the repository, with every token replaced by hand with its value from `sme.local.json`. Never paste the filled-in text back into this file.
> - The problem is the partner's own, as its business-problem letter to the organisers (24 August 2026) states it: tender response and outbound packing kept linked. Site paperwork is a secondary capability of the product, not the partner's problem, and does not belong in this statement.

# civil-buddy: Problem Statement (SME track)

Team Mintang · Team Code PJ2U63AF · 2026-09-26

## Problem statement

{{SME_NAME}}, a Singapore curtain-wall contractor registered with BCA under {{SME_CRS}}, supplies and installs façade packages. A typical job needs both an English tender response and the packing and shipping of panels to site, often in 40HQ containers, crates and steel frames, under weight and lashing limits. These live in separate files: tender in Word or PDF, packing list in Excel, bookings in email. So packing statements in the bid are often not tied to a loading plan, and container counts are not tied to the clauses they should satisfy. First drafts take days, and the scramble repeats each job. Qualifications and price remain human work. {{SME_FEEDBACK}}

How might an agent keep the two linked: read the tender's logistics clauses, plan the real panel list under them, tie each packing statement to its clause and a plan figure, flag statements that go stale when either file changes, and leave qualifications, price and every confirmation to people?

## One-line version

{{SME_NAME}}, a Singapore façade contractor, needs its English tender response and its outbound packing kept linked: every packing statement in the bid tied to a tender clause and a loading-plan figure, with people confirming.

---

*Notes for the team (not part of the pasted text):*

- **Length.** The problem statement is 195 words by a whitespace count once the tokens are filled (the partner's sentence is 32 of them); keep it between 120 and 200. The submission form's own Problem Statement box takes at most 200 characters, so the form gets a short version kept with the private submission files.
- **Source.** Every fact in the statement is from the partner's business-problem letter to the organisers (24 August 2026), in our words. The partner's own sentence is the SME_FEEDBACK value, which the partner agreed to.
- **Deliberately not claimed.** Any volume, headcount, time or cost figure from the partner beyond "first drafts take days"; where its panels are made; its suppliers, projects or clients.
- **What answers it.** The linked tender and packing run (pull request #65, `a161251`), shown on synthetic files by `python scripts/demo_facade.py` (flow 1). The Business Proposal §1, §3 and §4.1 give the figures.
