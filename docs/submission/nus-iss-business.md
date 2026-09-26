---
title: "civil-buddy: Business Proposal"
subtitle: "NUS-ISS “Show Me Your Agents” Hackathon 2026"
author: "Team Mintang · Team Code PJ2U63AF"
date: "2026-09-26 · product facts as of main at a161251 (2026-09-26)"
---

<!-- Note for the team (an HTML comment, so it is not printed). This file is in a public repository. Never write the partner's name, owners, UEN, address, projects, clients or people here, not even as an example. The SME_… and TEAM_CONTACT tokens (in double braces) are filled only when scripts/submission/build_nus_docs.py builds the PDF, from the untracked docs/submission/sme.local.json (copy sme.local.example.json, fill it with confirmed facts only, never commit it). A token with no value prints as a highlighted TEAM TO FILL and is counted. Product facts follow the Technical Document (nus-iss-technical.md) and must not contradict it. Every façade number must match what python scripts/demo_facade.py prints at the commit named in the date line, or what examples/facade-demo/README.md states. Market and policy figures carry numbered references, each opened on or before 26 September 2026. The partner's problem is the one in its business-problem letter to the organisers (24 August 2026): tender response and outbound packing kept linked. Site paperwork is a secondary capability, never the partner's problem. There is still no pilot, letter of intent, price or user count; add one only if it is real and the partner has agreed. Documents for the judges link only the showcase repository, never the development repository. -->

## 1. Executive summary

**The partner's problem.** Our partner is {{SME_NAME}}, a Singapore curtain-wall contractor registered with BCA under {{SME_CRS}}, confirmed by the organisers as our SME-track partner. One of our team members works there and represents it in this entry with its written authorisation (§2.2). The partner supplies and installs façade packages. It describes a typical job as needing two things at once: an English tender response, and the packing and shipping of the panels to site, often in 40HQ containers, in crates and steel frames, under weight and lashing limits. The two live in separate files: the tender in Word or PDF, the packing list in Excel, the bookings in email. So the bid's statements on packing are often not tied to a loading plan, the container count is not tied to the clauses it should satisfy, first drafts take days, and the same scramble repeats on the next job. Qualifications and price remain human work. {{SME_FEEDBACK}}

**What we built for it: one linked run.** civil-buddy reads the tender's logistics clauses with their clause numbers, plans the real panel list under them, and writes each packing statement of the English bid tied to its clause and to a figure of the loading plan. A link record then says which statements must be confirmed again when the tender or the panel list changes. On synthetic façade files that anyone can rerun from our repository (§4.1), offline and with no model:

- in a tender whose specification section has 12 clauses, it finds the five logistics clauses (handling, container type, gross mass per container, cargo securing, delivery sequence), takes the container type, 40HQ, from Clause 4.8, and plans the 24-panel list in 6 × 40HQ containers, with 24 → 24 pieces and 10,800 → 10,800 kg conserved;
- it writes 7 statements: 1 covered by the plan (the container type); 2 partial (the container count, and the heaviest container at 6,472.8 kg gross against Clause 4.9's limit of 20,000 kg), because the A-frame stillages that Clause 4.7 asks for are not modelled; and 4 left to a named owner (lashing, handling, crate structure, delivery sequence). Nothing is marked covered that the plan cannot evidence;
- when a revised panel list arrives (30 panels, 13,920 kg), the same request plans 8 × 40HQ and names what changed: containers 6 → 8, statements S2, S3, S6 and S7 to confirm again, and the two earlier Word copies that must not be sent [5].

Qualifications and price stay `[TO FILL]` for people, as the partner's letter says they must. Nothing is booked or submitted: every link record is marked `submit_blocked`, and a person confirms the loading plan before any booking.

**The same workbench also does** what the link is built on: a tender check that lists each requirement with its clause, a bid-against-tender check, a packing planner for any list, and drafts of site paperwork, whose high-risk documents (work at height among them) wait for a licensed person's typed sign-off (§4.4). These come with the product; they are not the partner's stated problem.

**Why the partner can trust it.**

- **Code computes every number.** Container counts and masses come from the packing engine; a model never writes a statement. Every post also works with no model at all.
- **A person confirms, and the tool says what it cannot evidence.** A statement the plan cannot back reads "partial" or carries `[TO CONFIRM by <owner>]`; a plan that does not fit evidences nothing. The 19 high-risk posts write nothing until a person types a fixed sign-off sentence; since our security baseline (pull request #61, 142 of 142 release checks passing in CI), this holds over the web API and the MCP server too, and an approval flag sent by a program approves nothing [6][7].
- **The firm's files stay with the firm.** It runs on a laptop today. The target is one company server per firm. Our container image now starts, and refuses to start without an access token; CI checks this on every pull request (pull request #64). The first company server is not yet running (§5). In the default no-key mode nothing is sent to a model. No partner document is in our repository; every test file is synthetic.
- **We publish our weak spots.** A-frame stillages, lashing and delivery sequencing are not modelled, which is why four statements go to a person. Across 65 drafting posts, only 0.229 of stated facts land in the right field [6].

**Pilot and market.** We propose an 8–10-week pilot at the partner, from November 2026 once the partner agrees, on past and live jobs it chooses, with metrics it agrees (§6): time to a first draft of the logistics response, packing statements tied to a clause and a plan figure, and containers planned against containers shipped. Beyond the partner, 296 firms hold BCA's Curtain Walls workhead (CR16), 215 of them at the entry grade [8]. The same flows then reach the 2,450 general-building and civil-engineering contractors (§7).

**Why now.** The government has formed an Action Team on built-environment productivity, and the Minister for National Development called for the industry to "scale up the adoption of robotics and AI technologies" [9]. BCA's own list of AI use cases for the built environment includes tender and contract management [10]. From 30 September 2026 the EDGE grant offers up to 70% support for SMEs [11], and BCA's BETC grant co-funds technology for built-environment firms, sub-contractors included [12]. In SBF's survey of 526 businesses (83% SMEs), the top challenges of transforming a business were the cost of adopting new technology (47%), getting staff skilled (31%) and uncertain return (30%) [13]. civil-buddy needs no model spend and is used in a browser; its return has not been measured and would be measured in the pilot, not asserted.

**What is not ready yet.** No firm has used civil-buddy on live work, the partner included; the pilot has not started, and there is no customer or price. The linked run is started from the command line and the agent's turns, not yet from the browser workbench. The company server is not yet running; there are no user accounts yet, so a confirmation does not name its person; and the Bedrock path has never been run. The quality of model mode has not been measured. The interface and the sign-off sentence are in Chinese; the logistics statements of the English bid-book are in English, but its compliance chapter still shows Chinese titles for the other rows, and English tenders are reproducibly measured only on synthetic sets.

**What we ask for.** (1) AWS credits and an architecture review for the partner's pilot server on Lightsail; (2) SBF introductions to two or three other façade and cladding subcontractors, for a second round of pilots once the partner's pilot has run; (3) guidance on the EDGE route, which opens on 30 September 2026, on BCA's BETC grant, and on whether BCA's Built Environment PSG continues after Enterprise Singapore's PSG ends on 29 September.

| Judging criterion | Where this proposal answers it |
|---|---|
| SME readiness | §2 the partner · §3 its problem · §4.1 the linked run · §5 safe adoption · §6 pilot · §8 business model · §9 channels and grants |
| Best use of agents | §4.5, and the Technical Document [6] for engineering depth |
| Social impact | §11 |

## 2. Our partner

### 2.1 Who they are

{{SME_NAME}} (UEN {{SME_UEN}}) is a Singapore curtain-wall contractor, registered with BCA under {{SME_CRS}}. It supplies and installs façade packages in Singapore. The organisers have confirmed it as an eligible partner for the SME track.

CR16 "Curtain Walls" is BCA's workhead for the supply and installation of curtain walls [14]. Registration in BCA's Contractors Registration System (CRS) lets a firm bid for public-sector construction up to its grade's tender limit and work as a first-level subcontractor on public projects; since 1 June 2025 a firm must also be registered before it can hire construction Work Permit or S Pass holders [15].

This proposal gives no headcount, revenue, project, client or staff member of the partner: none has been confirmed to us in writing.

### 2.2 Our representative at the partner

One of our four team members works at the partner as {{SME_REP_ROLE}} and represents it in this entry with its written authorisation, as the SME track asks. That member carries the partner's questions to the team and takes our drafts back for its review. So far no partner document has been used: every file behind the measurements in this proposal is synthetic, and none of the partner's documents is in our repository.

### 2.3 What the partner told us

{{SME_FEEDBACK}}

The partner has confirmed the collaboration and its business problem in writing (§3.1). Its letter gives no volume, time or cost figure beyond saying that first drafts take days, and we give none.

## 3. The partner's problem

### 3.1 Two disconnected exercises

In the partner's letter, as we understand it:

- **One job, two responses.** A typical façade job needs an English tender response and the packing and shipping of the panels to site, often in 40HQ containers, in crates and steel frames, under weight and lashing limits.
- **Separate files.** The tender is in Word or PDF, the packing list in Excel, the bookings in email.
- **Statements with nothing behind them.** The bid's statements on packing are often not tied to a loading plan, and container counts are not tied to the clauses they should satisfy.
- **Slow, and repeated.** First drafts take days, and the same scramble repeats on the next job.
- **What stays human.** Qualifications and price remain human work.

The rest of this section adds sourced facts about the two sides of the problem. It does not describe the partner's own figures, which only the partner can give.

### 3.2 The tender side: what a clause binds

- **The tender arrives as a subcontract with design in it.** One Singapore contracts consultancy describes façade works as commonly let as nominated subcontracts, most of them design-and-build or partial design-and-build because façade contractors hold proprietary designs. It also warns that a main contractor with no design role can become jointly liable for the façade design once it signs. This is an opinion piece that cites no sources [16].
- **The grade limits the tender.** For CR workheads, the public tender limit runs from S$0.8M at grade L1 to unlimited at L6 [17]. Each grade needs a minimum paid-up capital and net worth, a track record and qualified staff: at L1, S$50,000 of each, a S$300,000 track record over three years and one diploma holder [14].
- **Tests and declarations sit in the clauses.** BCA's CONQUAS quality assessment for private housing samples 5% of the curtain-wall area for site water-tightness tests (10% or 20% at higher tiers). It also asks for the qualified person's declaration that the tempered glass at balconies, canopies and shower screens was 100% heat-soak tested, in line with SS 653:2020, the code of practice for glazing in buildings [18].
- **Logistics clauses bind too.** Our synthetic façade enquiry (`examples/facade-demo/`) carries the kind of logistics clauses the partner's letter describes: upright transport on A-frame stillages with no stacking (4.7), 40HQ containers (4.8), a gross mass per loaded container of at most 20,000 kg including tare (4.9), cargo secured to the IMO/ILO/UNECE CTU Code (4.10), and deliveries sequenced to the installation programme with 48 hours' notice (4.11) [5]. A statement that answers one of them binds the bidder after award, whether or not a loading plan stood behind it.

### 3.3 The packing side: why a count cannot be guessed

- **Heavy, glazed, factory-made units.** In a unitised curtain wall, the glass and boards are built into a unit in the factory, which removes glass work on site. Units can weigh over 500 kg, and 1,000 kg in some cases (a façade manufacturer's technical page) [1].
- **What is not published.** We found no official Singapore source on how façade units reach site, or on what share is made abroad. The partner's letter says that it often ships in 40HQ containers, in crates and steel frames, under weight and lashing limits; we describe nothing more of its logistics.
- **Why a guess is costly.** In the team's description, a salesperson guesses the container count from the spreadsheet, and a wrong guess means changing containers or cargo held at port. No time study was done [7].

### 3.4 Where the link breaks

These examples come from the team's own descriptions and from testing civil-buddy on synthetic tenders and test packing lists; none is partner data.

| Break | What we have seen |
|---|---|
| A plan in another container type | Our older tender-delivery route could return a 20GP plan when the tender asked for 40HQ. Its compliance matrix now leaves that clause to a person; the route itself is not fixed yet (§4.3) [7] |
| A plan that does not fit, read as evidence | In the independent review of the linked run, a 20GP tender first gave "covered" on a plan in which 9 × 20GP containers held only 18 of the 24 crates. It was fixed before merging: a plan that does not fit now evidences nothing, and the reply says so [7] |
| A revised panel list | Revision B of our synthetic list adds a floor and heavier panels: the plan moves from 6 to 8 containers, and four of the seven statements change [5] |
| Bid against tender | A construction plan says 560 calendar days where the tender allows 540, while our own bid letter says 540. The project manager's name is spelt two ways across our files [7] |
| Units on a packing list | Our own code once read "Gross Weight (t)" as kilograms, turning 1.35 t into 1.35 kg, until we fixed it on 13 September 2026 [7] |
| A model's verdict | A small local model (`qwen2.5:3b`) wrote that a bid bond "complies with the tender" when the tool had found only candidate matches. Its numbers were kept to the sources; the conclusion was invented (archived live-model observation, not rerun [7]) |

SME adoption of AI has been driven mainly by off-the-shelf generative-AI tools [22], and a general chat assistant can make exactly these mistakes, fluently.

### 3.5 The pressures every construction firm shares

- **Scarce people.** Manpower cost is businesses' top challenge (63%), and foreign-workforce policy is felt most by construction and civil-engineering firms (with hotels and restaurants) [19]. A construction firm may employ five Work Permit holders for each local employee earning the qualifying salary [20]. BCA expects the industry to need at least 1,000 new architects and engineers a year [21]: the people whose judgement matters are in demand.
- **Hard to adopt technology.** Cybersecurity and data-privacy risk rose to 36% of businesses naming it as a business challenge in 2025 [19]. SME adoption of AI reached 14.5% in 2024, mostly off-the-shelf generative AI, and construction is among the sectors with lower digital adoption intensity [22].

## 4. What we built for them

**What is measured, and on what.** The façade figures below come from our façade demo, which anyone can rerun from the repository: `python scripts/demo_facade.py` runs civil-buddy at `a161251` offline, in its default no-key mode, on the synthetic files in `examples/facade-demo/`. They are a Singapore façade subcontract enquiry (12 specification clauses in its section 4, five of them on logistics), a list of 24 unitised panels in English and in Chinese, a revision B of that list with 30 panels, and installation daily-report and work-at-height inputs [5]. The other figures are from the Technical Document [6] and the repository [7]. None is partner data. **We have not measured staff time saved.** Every time figure is machine time; time saved is a pilot metric. Each "before" line is the partner's letter or the team's understanding, not something observed at the partner.

### 4.1 The linked run: tender and packing, kept together

**Before.** The tender response and the packing plan are drafted apart, from separate files. A packing statement in the bid has no loading plan behind it, a container count is not tied to a clause, and when the panel list changes nobody is told which statements have gone stale.

**Works today** (merged on 26 September 2026 as pull request #65, commit `a161251`).

- **One request.** A request that names one tender and one panel list, in English ("Link the tender … to the packing list … and write the logistics response") or in Chinese, is routed by rules to the linked run; a question stays in chat. It writes the link report and the English bid-book (Markdown, Word and Excel), the loading plan and the link record.
- **The clauses, with their numbers.** It reads the tender's logistics clauses: container type, gross mass (with its basis: gross, cargo only, or unstated), cargo securing, handling (A-frame stillages, upright, no stacking, protection), crating and delivery sequence.
- **The container type comes from the tender.** If the tender names none, it plans in 40HQ and says so. If the tender names a type the planner cannot model (such as open-top), allows several, names only a size ("40-foot containers") or only refuses types, it makes no plan and hands the choice to a person. A type typed in the request is planned as asked, and a clause that names another type is then never "covered".
- **The real list, with the planner's gates.** The panel list is planned by the packing engine, which refuses a plan whose pieces or kilograms differ from the list and stops on rows without usable weight, size or quantity, naming each row (for example "P02 (missing_weight)").
- **Statements tied to a clause and a figure.** Each statement carries its clause, a status (covered, partial, gap, or for a person), an owner, a SHA-256 of the clause text and the plan figures behind it. The gross mass of the heaviest container is the engine's cargo in that container plus the container tare from our knowledge base (40HQ: 3,890 kg, approximate); dunnage and lashing are excluded, and the statement says so, because the signed VGM governs.
- **A plan that does not fit evidences nothing.** Given a 20GP tender, where 9 × 20GP containers hold only 18 of the 24 crates, the type and count statements become gaps with a `[TO CONFIRM]`, the mass statement goes to a person, and the reply says the plan does not fit [7].
- **The link record.** `tender-packing-link.json` records statement → clause → plan figures → SHA-256 of the tender, the panel list and the plan, with `confirmed_by_person` false and `submit_blocked` true. On a re-run it reports every earlier statement as changed, unchanged, new or withdrawn, names the inputs that changed, and names earlier Word copies that still hold the old statements (Word export never overwrites a file).
- **The English bid-book.** Its logistics chapter is written from the plan, each statement citing its clause and figure, and the clause-level rows are added to its deviation schedule; an annex gives the loading plan per container. Price and qualifications stay `[TO FILL]`.

**On the synthetic files** [5]:

| | First run (24 panels) | Revision B (30 panels) |
|---|---|---|
| Container type | 40HQ, taken from Clause 4.8 (covered) | Same |
| Plan | 6 × 40HQ, booking lower bound 6; 24 → 24 pieces; 10,800 kg net | 8 × 40HQ, lower bound 8; 30 → 30 pieces; 13,920 kg net |
| Heaviest container vs Clause 4.9 (20,000 kg gross) | 6,472.8 kg (2,582.8 cargo + 3,890 tare), margin 13,527.2 kg: partial | 6,752.8 kg (2,862.8 + 3,890), margin 13,247.2 kg: partial |
| Statements | 1 covered · 2 partial · 0 gap · 4 for a person | Same statuses; S2, S3, S6, S7 named to confirm again; S1, S4, S5 unchanged |
| Crate structure | 24 of 24 crates pending detailed design | 30 of 30 |
| Stale copies | None | The two earlier Word copies named: do not send |

The linked run has 18 automated tests in our release gate, which passed 146 of 146 checks in CI on the pull request (run 36230427585) and again on `main` after the merge (run 36231052332) [7].

**The person still** confirms the loading plan before any booking and confirms again every statement a re-run names; designs and signs the lashing to the CTU Code; sizes the A-frame stillages; sequences deliveries to the installation programme; writes the qualifications and the price; and signs and submits the bid outside the product.

**Shown by the demo as not done yet.**

- A-frame stillages, upright and no-stacking rules, lashing and delivery sequencing are not modelled. The count rests on the engine's own steel-frame crates (one panel per crate), so the count and mass statements read "partial", and securing, handling and sequence go to a person [5].
- The plan does not follow the installation programme: containers mix floors, and in revision B the heavier level-8 panels load in container 1 [7].
- The linked run is reached from `civil exec` and the agent's turns, not yet from the browser workbench or the packing gateway. Model mode was not run with it [7].
- In the English bid-book, the compliance chapter and the open-actions annex still show Chinese titles for rows outside logistics, and its scoring-point section says none was extracted, although the tender check finds 4 [7].
- When a tender asks for no packaging the planner cannot model, the mass statement can read "covered" with any margin; no safety margin is set yet [7].

**Pilot measures:** time from tender and panel list to a first draft of the logistics response; packing statements tied to a clause and a plan figure; containers planned against containers shipped; stale statements named when a list is revised.

### 4.2 The tender side it builds on

- The tool extracts the requirements it recognises, each with its exact quote and, where the layout allows, its clause number and page. A layout it has not seen can make it miss some.
- On the synthetic façade enquiry, the tender check lists, each with its clause, line or section reference: the tender reference, the closing date, the CR16 workhead, 420 calendar days, 90-day validity, a 10% performance bond by banker's guarantee, a 12-month defects-liability period, "alternative tenders not permitted", all 3 rejection clauses and the 4 weightings of Section 3. The 10 rows it could not find are marked "not found in the text" for a person. From the same hand-off, the technical-bid post drafts 4 chapters with 13 cells left for the bid team, and the compliance post lists 8 requirements with no response yet and the 3 rejection clauses to tick by hand [5].
- It compares each value in our response files with the tender, flags mismatches as "needs review" (naming the file), lists values that differ between our own files, lists document properties side by side, shows what changed since the last check, and never writes "can bid" or "confirmed compliant". On a 19-case development set that the rules were tuned on, linking scores precision 1.000 and recall 0.980, and all 14 planted number conflicts are found, with none false [6].
- The compliance schedule does not mark "No Deviation" on a clause a packing run cannot answer (since pull request #63): handling the planner does not model goes to a person, and a lashing clause reads at most "Partial Deviation" [7].

**Not done yet.** The tender check's review table shows none of the 12 specification clauses of section 4: the linked run reads the five logistics clauses, but the other seven (the two mock-ups, heat soak, site water test, PE-endorsed calculations and shop drawings, warranty, insurance) are not listed, nor are liquidated damages and retention; the qualification row is among the 10 left "not found", although the enquiry asks for bizSAFE Level 3; and the review table is in Chinese [5]. Façade tender topics are being added before the demo on 10 October 2026. **Not yet proven:** real English tenders. English parsing is reproducibly measured only on synthetic sets, and the one archived real English tender scored 0/13 fields on its first run [6].

### 4.3 The packing side it builds on

- Columns and units are mapped: "3 EA" reads as 3, and "10/12" is flagged rather than read as 1012. A row without usable weight, dimensions or a whole-number quantity stops the plan, with one plain sentence per row. PDF lists are read only in known layouts.
- On the 24-panel list (4,200 × 1,500 × 250 mm, 450 kg each), the engine puts each panel in its own crate and plans 6 × 40HQ that fit; the booking lower bound is also 6. The structure verdict for all 24 crates is "pending detailed design": without structural facts, the engine does not invent a pass. The plan is conservative: the six containers use 44% of their space and carry 9% of their rated payload, and handling notes ("glass, fragile, do not tip, transport upright, do not stack") change nothing, in either language [5].
- On the packing page it pauses for a person to confirm the crates (an API caller that does not ask for the pause skips it), then plans containers of one type with a 3D layout, centre of gravity and risk verdict. Drafts are marked not for booking; lashing and the VGM are signed separately.
- **Evidence beyond façades.** Pieces in equal pieces out on all 50 test lists (3,571 pieces). All 128 automated runs completed, but completing is not fitting: 71 produced a plan that fits [6].
- **The older tender-delivery route** now takes its container type from the request, else from the tender clause, else 40HQ, and labels whether it packed sample materials. It still packs through an older multi-agent path, which with the demo tender and no materials returned 1 × 20GP although the clause asks for 40HQ; its compliance matrix leaves that clause to a person, and the linked run does not use this path [7].

**Being added before 10 October:** English handling words (glass, fragile, upright, do not stack, A-frame), and fragile, upright or no-stack rows kept out of mixed crates. **Not planned yet:** A-frame or stillage crates, which need the partner's real stillage dimensions, tare and capacity (anything else would be invented numbers) [5]; 40-foot flat-rack and open-top containers (the engine plans only 20GP, 40GP, 40HQ and 45HQ) [7]; and more than one container type in a plan [5].

### 4.4 The same workbench also does: site paperwork

Beyond the partner's problem, the same workbench drafts site and office paperwork from a person's words and files, in Word and Excel, with gaps left as `[A001]`, `UNSPECIFIED` or `TBD`. On the demo's Chinese labelled lines for one façade installation day, the daily report puts each labelled fact in its own row, and leaves the preparer and reviewer blank. The high-risk posts, the work-at-height briefing among them, write nothing until a person types the sign-off sentence; the demo never types it [5]. A firm can add its own forms as plugins with no code [7]. The honest counterweight: across 65 posts, only 350 of 1,529 stated facts (0.229) land in the right field, and an English sentence still places almost nothing in a draft; for most of these posts today's draft is a correct skeleton, not a finished form [6]. The linked run does not depend on fact placement: its statements are written by code from the plan.

### 4.5 How the agent works

- **Rules, not a model, pick the post or workflow.** A fixed workflow runs before any open loop. The linked run is a registered, read-only tool of the tender post (`tender.packing_link`, 60-second limit), reading only files inside the job folder.
- **An optional model loop** (off by default) runs only when no workflow matches, with eight registered tools and at most ten steps.
- **A policy check runs before every registered tool call** on the default path, over MCP and through the packing gateway's tool route, and gives a reason for each refusal.
- **Two deterministic guards** check every reply in model mode. One lists numbers with no source; the other strikes verdicts the product may never state. `civil review` runs both on any document, with no model [6].

## 5. Why it is safe for the partner to adopt

| Property | What holds | Status |
|---|---|---|
| **A person confirms the link** | Every link record is marked `submit_blocked` with `confirmed_by_person` false. A statement the plan cannot evidence reads "partial" or carries `[TO CONFIRM by <owner>]`; a plan that does not fit evidences nothing; a re-run names the statements to confirm again and the stale Word copies | Live since pull request #65 (26 Sep 2026) |
| **Licensed sign-off** | 19 of 66 posts write nothing until a person types 我明白，将由持证人员签认 ("I understand; a licensed person will sign"). No setting removes this | Live |
| Sign-off over MCP and HTTP | The server accepts only the typed sentence. An approval flag sent over HTTP no longer approves, and the MCP server neither offers nor accepts one. In model mode an approval covers one turn. On the command line `--confirm` is still the operator's own assertion. Two separate Rust tools still accept a flag; neither is part of the deployed product | Live since the security baseline (pull request #61; 142 of 142 checks in CI) |
| Named approver | Accounts with the roles admin, engineer and licensed approver; each confirmation names its person. Today it says "local user" | Before the 10 Oct demo |
| **Model proposes, code writes** | Counts, masses and statements come from code. In the model loop the model cannot approve, and a sign-off sentence it copies is replaced | Live |
| **Local-first, no key needed** | No key, no model call. By default the apps listen only on the local machine. Each check records every input file's SHA-256 | Live |
| **One company, one server** | One AWS Lightsail instance per company, used in a browser, with job folders and the database on that instance. Our container image starts; without an access token it refuses to start (exit 3), and an API request without the token gets 401 (the health check stays open by design); CI builds it and checks this, and that a session survives a container re-create, on every pull request | Image checked in CI since pull request #64 (26 Sep 2026); the server is not yet running |
| Closed network by default | Without a token, the workbench and the packing gateway refuse to listen beyond the local machine. Once a token is set, every API request needs it, local ones included. Our deployment guide makes it mandatory on a server and serves the apps only through a TLS proxy, with ports 80 and 443 open | Live since pull request #61 |
| **Red lines** | No signed or statutory documents, no "can bid", no promised win rate, no submission to GeBIZ, no invented clause numbers, prices or coordinates | Live in the post rules and code writers; in model mode the guards check replies |

**At the partner.** Each statement the link leaves to a person names an owner: logistics, a competent person for lashing, the packing designer, the project manager. [TEAM TO FILL: which of the partner's roles hold these, and who types the sign-off sentence for high-risk documents — roles only, no names. If not answered, write: "The partner names these roles at the start of the pilot."] The partner's tenders and packing lists stay on its own machine or its own server; none goes into our repository, and our tests use synthetic files only. The partner is named only in the PDFs sent to the organisers.

The gaps that remain are listed in the Technical Document [6]. Three matter to an adopting firm: a server behind a proxy is safe only with its token set; the Rust tools named above, including old Rust-workbench trial builds, must not be deployed as if they were covered; and on the workbench's packing post, three packing lists in a row that need a person's fix currently switch that post's planning off for everyone until the server restarts.

**Model choice and data residency.** With a key, civil-buddy can be pointed at any OpenAI-compatible endpoint, such as OpenRouter or a local Ollama. Amazon Bedrock's OpenAI-compatible Chat Completions endpoint can be set in the same way, but it has never been run from our code, so whether it works is not yet known; a verification run is planned before the demo [6]. Lightsail is available in the Singapore Region [23]. There, AWS lists Bedrock's `bedrock-runtime` endpoint as supported and its `bedrock-mantle` endpoint as not supported, and its model table does not list the gpt-oss models for Singapore [24]. AWS says global cross-Region inference may process data in any commercial Region [24], so we do not claim that model calls stay in Singapore. The pilot runs in no-key mode, and the linked run needs no model at all.

## 6. Pilot at the partner

- **Who and how long:** the partner, for 8–10 weeks. Proposed start: November 2026, once the partner agrees; nothing has started.
- **Set-up:** one server for the partner behind TLS with accounts, or a laptop install. The pilot runs in no-key mode.
- **Data:** the partner chooses past and live jobs for which it has both the tender and the panel list, and, if it wishes, the shipping records. They stay on its machine or server, and none enters our repository.
- **Baseline:** [TEAM TO FILL: the partner's own volumes — tenders answered and shipments per month — only as the partner confirms them. If not answered, write: "The partner's volumes are recorded in weeks 1–2; none is given here."]
- **Schedule:** in weeks 1–2 the partner times its current process on at least three past jobs (tender and panel list each), and we check English readiness on its past tenders. In weeks 3–8 civil-buddy runs the link on live jobs alongside the usual process, with a person still confirming everything. Weeks 9–10 review the metrics below with the partner.

| Metric | Baseline | How measured | Target |
|---|---|---|---|
| Staff hours from receiving the tender and panel list to a first draft of the logistics response | Partner, pilot weeks 1–2 | The partner's time log, before against during the pilot | Proposed: at least 20% fewer than the weeks 1–2 baseline |
| Packing statements in the bid that cite their clause and a plan figure | Partner, pilot weeks 1–2, on past bids | Count in each draft, checked by the partner | Proposed: every statement the tool drafts, or a named `[TO CONFIRM]`; none "covered" without a plan figure |
| Logistics clauses found with the correct clause reference, on the partner's tenders | Partner, pilot weeks 1–2 | Against the partner's own check | Proposed: by weeks 9–10, at least 80% of the clauses the partner finds, and no clause reference that is not in the tender |
| Containers planned against containers actually shipped | Partner's shipping records, weeks 1–2 | Records the partner chooses to share | Proposed: the gap recorded for every shipment compared; by weeks 9–10, within one container of the count shipped on at least 80% of them |
| Statements named to confirm again when a tender or list is revised | Partner, weeks 1–2 (how it finds them today) | Each re-run against the person's own comparison | Proposed: every changed statement named; no stale copy sent |
| Pieces and kilograms conserved from packing list to plan | Built in | The plan's own conservation check | 100% |
| Conflicts between bid and tender found; false alarms | Partner, weeks 1–2 | Against the person's own check | Proposed: at least 90% of the conflicts the person finds; at most one false alarm per tender |
| Blocked verdicts or untraced numbers in delivered drafts | Built in | `civil review` on every draft | 0 |
| Productivity gain; satisfaction with price and quality | Partner, weeks 1–2 | Time log and a week-10 survey | Recorded as evidence for pre-approval (built-environment threshold: 20%) [25] |

Targets marked "Proposed" are ours and stay open until the partner agrees them. Baselines are measured by the partner in pilot weeks 1–2; none is given here.

## 7. From one façade contractor to the market

### 7.1 Singapore curtain-wall and façade subcontractors

| Measure | Figure | Ref. |
|---|---|---|
| Firms registered under CR16 Curtain Walls | 296: L1 215 · L2 14 · L3 11 · L4 12 · L5 25 · L6 19 | [8] |
| Adjacent registrations | CR17 Windows 56 · RW01 Window Contractors 278 (they may overlap with CR16) | [8] |
| Public tender limits, CR workheads | L1 S$0.8M · L2 S$1.6M · L3 S$5M · L4 S$8M · L5 S$16M · L6 unlimited | [17] |
| CR16 entry grade (L1) | S$50,000 paid-up capital and net worth; S$300,000 track record over 3 years; one diploma holder | [14] |

The counts are our own count of BCA's open dataset (snapshot last updated 12 January 2026). About 73% of CR16 firms (215 of 296) are at L1, whose public tender limit is S$0.8M. A grade reflects a firm's tender limit and finances, not its SME status, and no official count of SMEs among these firms is published; across the whole economy, 99% of enterprises are SMEs [26]. We have not counted cladding firms registered under other workheads.

**Why this segment first.** CR16 is the workhead for supplying and installing curtain walls [14], so its firms tender for façade packages, and those that use factory-made unitised panels also pack and ship them to site: the two exercises the partner wants linked. The segment is a known public list, and the partner's pilot gives the evidence a second firm will ask for. English comes first, since these firms tender in English: the linked statements are in English, while the interface and the sign-off sentence are still to come. We give no dollar market size until a price is chosen (§8); after that, the serviceable market is firms × annual price.

### 7.2 The wider construction market

| Measure | Figure | Ref. |
|---|---|---|
| Construction demand (contracts awarded) | 2026: S$47–53B projected; 2025: S$50.5B preliminary; 2027–30: S$39–46B a year. BCA says demand could moderate after Changi T5 | [27] |
| SMEs, all industries (2025) | 99% of 371,000 enterprises; no construction-only split is published | [26] |
| Construction firms | 9,396 taxable companies (YA2024) [28]; 25,700 resident-owned enterprises (2024) [29] | |
| BCA-registered contractors | 15,864 firms. General building (CW01): 2,049; civil engineering (CW02): 935; 2,450 hold either, and 2,085 hold them only in grades C1–C3 | [8] |
| Public tender limits, CW01/CW02 | C3 S$0.8M · C2 S$1.6M · C1 S$5M · B2 S$16M · B1 S$50M · A2 S$105M · A1 unlimited | [17] |

The 15,864 firms span every registry in the dataset, not only CRS construction workheads. General contractors tender for public work on GeBIZ, where purchases above S$90,000 are open tenders judged on published criteria that generally cover quality as well as price [30].

| Segment | Size | First flows |
|---|---|---|
| **Beachhead: curtain-wall contractors (CR16), starting with the partner** | 296 firms [8] | The linked tender and packing run; tender review |
| Window firms (CR17, RW01) | 56 and 278 registrations [8] | Tender review; the linked run where they ship |
| Small general-building and civil-engineering contractors (C1–C3 only) | 2,085 firms [8] | Bid-against-tender check; site paperwork with sign-off |
| Steel and precast suppliers that crate and ship cargo | Not sized: we found no official count | Packing plan, and the link where they tender |
| Other registered specialists and subcontractors | Up to 15,864 registered firms [8] | Office posts; the firm's own forms as plugins |

## 8. Business model and pricing

**Cost to serve one firm.**

- **Software:** MIT licence [7], so no licence fee.
- **Server:** one Lightsail instance in Singapore, on the 2 GB plan (2 vCPUs, 60 GB SSD, 3 TB transfer), listed at US$12 a month [31]; the pilot shows whether it needs a larger one.
- **Model:** zero in no-key mode, which is how the pilot runs (§6); the linked run needs no model. Usage is not metered yet [6].
- **Our time:** setup, TLS, backups, updates, support and plugins. Not measured yet; we log our hours per firm during the pilot.

| Option | For | Against |
|---|---|---|
| **A. Free self-host, paid managed server.** The MIT code is free on a laptop; we charge for one set-up, secured, backed-up server per firm, with support | Fits the one-company design; the firm keeps its data; no seat counting, so tender, logistics and site staff can all have accounts | Small revenue per firm; we carry server and support costs; needs a company to invoice |
| **B. Per-seat subscription** on the managed server | Familiar; grows with the firm | Penalises adding the people who confirm, whom the safety story needs; small firms have few seats |
| **C. Grant-eligible fixed package:** server, setup, training and plugins for a year | Answers cost, the top barrier [13]; EDGE pays up to 70% for SMEs [11] | Not open to us yet (§9.2) |
| **D. Setup and plugin service**, added to A or B | Answers the skills barrier: the firm's own tender formats, panel lists and forms | Does not scale; must not become custom code |

**The partner's pilot is free** (option A, with the server paid from credits if AWS grants them).

**Paying for the model.** For model use, the firm can bring its own key (its own Bedrock or OpenRouter account), or we pass the cost through. The default stays no key.

**Benchmarks, not our price.** On the GoBusiness PSG directory (total package cost, before any grant), Novade Safety-HSE (electronic permit-to-work) is listed at S$16,000 for one project for a year and S$29,000 for unlimited projects, and Glodon Cubicost packages start at S$3,226 [32].

> **Our choice:** option A during the partner's pilot, A + D afterwards, and C once we are eligible. We state no price until the pilot has measured our support hours and the value to the partner.

## 9. Go-to-market

### 9.1 Channels

1. **The partner as a reference.** Only with its written consent, and only in the words it approves. [TEAM TO FILL: whether the partner agrees to be a reference after the pilot, and in which form. If not answered, write: "Whether, and in which form, the partner acts as a reference is agreed with it after the pilot."]
2. **SBF network.** We will ask SBF which of its trade associations and chambers serve façade and construction firms, and seek introductions through them (our ask in §1).
3. **BCA's public registry** lists registered firms by workhead and grade, with an address and phone number [8], so the 296 CR16 firms can be found. Before any outreach we will check the dataset's terms of use and Singapore's personal-data and Do Not Call rules, and contact firms only through their published business contacts.
4. **Open source as the trial.** A firm can run the linked run and the tender check on its own files on a laptop, with no key and no contract; today the interface is in Chinese. A firm installs it from the repository; a packaged release of the current app is planned after the demo.
5. **AWS.** AWS Activate Founders starts at US$1,000 in credits, and select participants may qualify for up to US$5,000. Its listed conditions are self-funded, pre-Series B, founded in the last 10 years, and an AWS account on the paid tier [33]. We have not established whether a team with no company qualifies, so the pilot does not depend on these credits.

### 9.2 Grants: what the rules actually require

| Scheme | Offer | What it means for us |
|---|---|---|
| Enterprise Singapore PSG | Up to 50%, capped at S$30,000, for pre-approved solutions [34] | **Ceases 29 September 2026**, the day after this submission, together with EDG and MRA; from 30 September, business grant support is applied for under EDGE [11][34]. It closes before any pilot could start, so we do not plan on it |
| EDGE (from 30 Sep 2026) | Up to 70% for SMEs; S$100,000 a year, of which up to S$30,000 for single-function digital solutions. Whether a pre-approved vendor is needed depends on the activity, and the activity list appears from 30 Sep [11][35] | The activity list is published from 30 September, after this submission; we will then check which activity fits and whether it needs a pre-approved vendor |
| BCA Built Environment PSG (1 Apr 2026 – 31 Mar 2031) | Up to 50% for pre-approved digital solutions, capped at S$50,000 per firm over five years. This tranche adds more pre-approved solutions in areas such as digital contract management [36] | BCA's page for this grant, last updated 25 September 2026, still shows this tranche and says nothing about it ending with Enterprise Singapore's PSG [37]; we will confirm with BCA |
| BCA BETC Grant | Open to built-environment firms registered and operating in Singapore, naming developers, main builders, sub-contractors, consultants and prefabricators. Covers equipment, software, materials, consultancy and professional services. Up to 70% for SMEs and 50% for non-SMEs from 1 Apr 2025 to 31 Mar 2027, then 50% and 30% until 31 Mar 2030. An SME here has group annual turnover of no more than S$100M or group employment of no more than 200 [12] | It is the adopting firm's grant, not ours, and it names sub-contractors. BCA's AI page names it, with the Built Environment PSG, as funding for AI use cases [10]. Whether it covers software from a team with no company is not established, so the pilot does not rely on it |
| IMDA pre-approval (vendor side) | Vendor incorporated for at least 18 months, with at least 5 unaffiliated SME users of at least 6 months, 8 h × 5 weekday support, positive equity and a current ratio of at least 1. At least 5 SMEs must report a productivity gain of at least 15% (20% in the built environment) [25] | A four-student team with no company or customers cannot qualify today |

**Our plan.** The pilot does not depend on a grant, and it is built to collect what pre-approval asks for: consented users, six months of use, a measured gain and customer satisfaction. We decide whether to incorporate when the pilot ends, on its results. The earliest pre-approval is 18 months after incorporation.

## 10. Competitive landscape

No vendor below publishes a Singapore market share, so we state none; descriptions paraphrase their own pages.

| Category | Examples | How civil-buddy differs |
|---|---|---|
| General chat assistants | ChatGPT, Gemini, Copilot: the off-the-shelf tools behind most of the rise in SME AI adoption [22] | Statements tied to clauses and plan figures by code, visible gaps, blocked verdicts, a person's confirmation; also runs with no model |
| Construction management suites | Procore, Autodesk, Hubble, Novade: projects, documents, safety permits, inspections [38]. Hubble and Novade have permit-to-work packages in the PSG directory [32] | Not a project-management suite. It drafts and checks the tender response and the loading plan from the firm's own files, locally, and can sit beside a suite |
| AI tender analysis | Lucius AI reads a GeBIZ tender pack and returns requirements, deadlines, risk flags and a bid/no-bid recommendation [39] | Checks our response against the tender and ties the packing statements to a loading plan. It deliberately gives no bid/no-bid verdict, and in the default no-key mode the tender posts call no model |
| Load planning | EasyCargo, Cargo-Planner: cloud 3D load planning, not specific to construction [38] | We do not compete on solving. We tie the plan to the tender clauses it must satisfy, read messy lists safely, stop on bad rows, check conservation and name the statements a revised list makes stale |

**Where we are weaker.** Established vendors have customers, support teams, English interfaces, mobile apps and PSG listings; we have none yet. We have not searched specifically for software built for façade contractors, so we do not claim that none exists.

## 11. Social impact

**Fewer costly surprises for a small subcontractor.** A packing statement in a bid binds after award. When it is tied to a clause and a plan, and a revised list says which statements have gone stale, a small firm is less likely to commit to containers, masses or deliveries it cannot meet. The tool needs no model spend, runs on a laptop and is free under MIT, and it is meant to let scarce engineers and logistics staff spend their time judging rather than retyping [21].

**Work at height, on the same workbench.** In 2025, falls from height were the leading cause of fatal and major injuries in construction (43, after 44 in 2024) [4]. Under the Work at Heights Regulations 2013, work where a person could fall more than 3 m needs a fall prevention plan and a permit-to-work system [2], and MOM's factsheet says the permit applies at workplaces that typically include construction worksites [3]. Across construction, the rate of fatal and major injuries was 26.3 per 100,000 workers in 2025, and small-scale works accounted for more than 60% of the sector's fatal and major injuries [40]. Two briefing posts ship today [7]; like most non-bid posts, their drafts are still skeletons:

- **worker-brief** drafts a three-minute pre-shift talk in plain words: what we do today; where the danger is; three steps to do it; who calls stop; and a reminder to ask if anything is unclear. It is marked as not a signed briefing.
- **safety-brief** is for technicians and needs the typed sign-off. Its knowledge base names Singapore sources by title, and its rules forbid writing "briefing complete, work may start".

**Workers' rights, explained.** The hr-labor post drafts a contract checklist, and its knowledge base names MOM and TADM pages by title. Its rules say it explains the law, does not predict dispute outcomes and does not invent salary bands [7].

**Ideas, not delivered.** A phone briefing where three check questions replace the signature, because a signature proves you came and a quiz proves you understood (missing: mobile interface, speech output). Photo-based stop-work, where the model says what it sees and a rule engine decides (missing: vision model, hazard rules).

**We refuse to build** AI that signs on a worker's behalf, automatic "can start work" verdicts, emotion or behaviour scoring of workers, and fully unattended pipelines. In the team's words: however smart the model, it must stop and wait for a person to nod.

## 12. Risks and mitigations

| Risk | Mitigation today | Pilot or roadmap |
|---|---|---|
| **A packing statement with no plan behind it** | Each statement cites its clause and plan figure, or reads "partial" or `[TO CONFIRM]`; a plan that does not fit evidences nothing; the record stays `submit_blocked` | Measured on the partner's jobs (§6) |
| **A stale statement after a revised list** | The link record hashes the tender, the list and the plan; a re-run names the statements to confirm again and the Word copies not to send | Measured on revisions during the pilot |
| **Packaging the planner does not model** | A-frame stillages, lashing and delivery sequencing go to a named owner; mass excludes dunnage and lashing, and says so | Stillages only with the partner's real data |
| **Few partner figures** | The partner has confirmed the collaboration and its problem in writing, but no volume, time or cost figure has been agreed for publication, so none is used | The pilot measures them, and they are published only with the partner's consent |
| **Single-partner dependence** | MIT licence: the partner keeps a working copy whatever happens to us | The 296 CR16 firms are the next segment (§7.1) |
| **The partner's confidential data** | Local-first; no partner document in our repository; synthetic test files only; the partner named only in the PDFs sent to the organisers | One server for the partner; before any pilot data is used, a data-handling note agreed with the partner that sets out both sides' PDPA duties for personal data in its documents |
| **Liability for a wrong document** | Drafts only, `submit_blocked`, a person's confirmation, blocked verdicts. Since 26 September no API or MCP caller of the deployed apps can approve with a flag | Accounts that name the approver are planned before the demo. Before any paid use: a legal review of our terms and a liability cap |
| **Data privacy** | No model call without a key; the key stays on the host; the apps are closed to the network unless a token is set | Personal-data masking (roadmap); no claim of Singapore-only model calls |
| **Model errors** | No model by default, and none needed for the link; number and verdict guards | Model-mode quality is unmeasured, so the pilot measures it before the partner enables a model |
| **Fact placement at 0.229 on other posts** | Stated openly; the link's statements are written by code; the bid posts score 1.00; gaps stay blank | If the partner adds its own forms: proposed target 0.80 on those forms by the end of the pilot |
| **Not yet English-ready** | Chinese interface and sign-off sentence; English requests are routed (0.786 on a blind held-out set, 0 false runs) [6]; the link's statements are English; English tenders measured only on synthetic sets | Not yet scheduled (Technical Document [6]); we set a date with the partner once weeks 1–2 of its pilot have checked English readiness on its past tenders (§6) |
| **Adoption and skills** | Browser use; the firm's formats as plugins; free trial | Setup and training (option D); return measured, not promised |
| **Team continuity** | MIT licence: a pilot firm keeps a working copy | Our team lead (§14) maintains it at least until the pilot ends; the longer term is decided with incorporation (§9.2) |

## 13. Roadmap and milestones

| When | Milestone |
|---|---|
| 26 Sep 2026 (done) | Security baseline, pull request #61 (142 of 142 checks in CI): only the typed sentence approves, over MCP and HTTP too; token on every API request once set; no server listens beyond the local machine without one |
| 26 Sep 2026 (done) | Pull request #63 (145 of 145 checks in CI): the compliance schedule no longer marks clauses a packing run cannot answer "No Deviation"; English requests routed; the synthetic façade demo |
| 26 Sep 2026 (done) | Pull request #64 (`16316df`): the container image starts, refuses to start without a token, and is checked in CI on every pull request. Pull request #65 (`a161251`, 146 of 146 checks in CI on the pull request and on `main`): the linked tender and packing run, its link record and the English logistics chapter |
| Before the submission (28 Sep 2026) | One Lightsail server behind TLS, set up by the deployment guide. Not yet running when this PDF was exported; the URL follows in the submission email |
| By 10 Oct 2026 (demo) | Accounts and roles (admin, engineer, licensed approver) with named confirmations; a Bedrock verification run; façade tender topics (the seven other specification clauses, liquidated damages and retention); English handling words for packing lists, and fragile, upright or no-stack rows kept out of mixed crates |
| Not yet scheduled; set with the partner after weeks 1–2 of the pilot | English interface and sign-off sentence |
| From November 2026 (proposed, once the partner agrees) | Pilot at the partner, 8–10 weeks |
| Once the partner supplies stillage data | A-frame and stillage crates for glazed panels |
| Not yet scheduled | The linked run from the browser workbench; delivery sequencing to the installation programme |
| After the demo | Durable audit log, metering and budgets, admin console, single sign-on, personal-data masking, per-user sessions |
| Not planned yet | 40-foot flat-rack and open-top containers; more than one container type per plan |
| At least 18 months after incorporation | Earliest IMDA pre-approval application |

The platform rows follow the Technical Document [6], which also puts the audit log and metering after the demo. The façade rows come from our façade demo [5].

## 14. Team

- **Luo Wenjie:** team lead; architecture, agent runtime and security.
- **Cui Zixuan:** workbench interaction and front end; earlier tender and civil agent prototypes.
- **Dong Yufei:** business tools and acceptance tests (packing weight gate, tender review).
- **Liu Jingxuan:** team member.

- **Track:** SME track, with our partner {{SME_NAME}} (confirmed by the organisers).
- **Authorised representative:** the team member who works at the partner as {{SME_REP_ROLE}} (§2.2).
- **Contact for SBF and AWS follow-up:** Luo Wenjie (team lead), {{TEAM_CONTACT}}

## References

1. YKK AP. Technical page on unitized curtain walls (a façade manufacturer's page, undated). Accessed 26 Sep 2026. <https://www.ykkapglobal.com/en/technologies/pickup/pickup_11/>
2. Attorney-General's Chambers, Singapore Statutes Online. Workplace Safety and Health (Work at Heights) Regulations 2013 (amended by S 280/2014 and S 434/2024): definition of hazardous work at height, regs 5–12, Part III (permit-to-work, regs 20–28). Version current at 26 September 2026. <https://sso.agc.gov.sg/SL/WSHA2006-S223-2013>
3. MOM. Factsheet on the Workplace Safety and Health (Work at Heights) (Amendment) Regulations 2014 (undated; changes in force 1 May 2014). <https://www.mom.gov.sg/-/media/mom/documents/safety-health/factsheet-on-wahamendmentregulations.pdf>
4. MOM. *Workplace Safety and Health Report 2025* (national statistics). March 2026. <https://www.mom.gov.sg/-/media/mom/documents/safety-health/reports-stats/wsh-national-statistics/wsh-national-stats-2025.pdf>
5. Team Mintang. Façade demo in the civil-buddy repository at `a161251` (pull request #65, merged 26 September 2026, on the demo of pull request #63): `examples/facade-demo/` (synthetic fixtures: a Singapore façade subcontract ITT whose section 4 has 12 specification clauses, five of them on logistics (4.7–4.11); a list of 24 unitised panels as English and Chinese spreadsheets and its revision B with 30 panels; daily-report and work-at-height inputs; its README lists what the demo does not show yet) and `scripts/demo_facade.py`, which runs four flows, the linked tender and packing run first, through `civil exec`'s entry point offline, in the default no-key (steps) mode. Figures from our run on 26 September 2026; reproducible with `python scripts/demo_facade.py`. Every file is synthetic; none comes from the partner. <https://github.com/LUOaini1213/civil-buddy-sme>
6. Team Mintang. *civil-buddy: Technical Document* (NUS-ISS submission), 26 September 2026. <https://github.com/LUOaini1213/civil-buddy-sme>
7. Team Mintang. civil-buddy repository at `a161251` (26 September 2026), MIT licence: security baseline, pull request #61 (142/142 checks passed in CI runs 36170078042 on the pull request and 36171221472 on `main`), with operator settings in `docs/deploy-minimal.md`; pull request #63 (145/145 in runs 36222056643 and 36222613544): the compliance-schedule rules pinned by `scripts/test_facade_tender.py` and `scripts/test_tender_delivery_api.py`, and the container types the engine plans (`packing_assistant/knowledge.py`); pull request #64 (`16316df`; CI job docker-smoke in run 36227890649): `Dockerfile`, `scripts/docker_smoke.sh`; pull request #65 (`a161251`; 146/146 checks and all four CI jobs passed in runs 36230427585 on the pull request and 36231052332 on `main`): `packing_assistant/tender_packing_link.py`, `scripts/test_tender_packing_link.py` (18 tests), the review probe of a plan that does not fit, and the English bid-book `packing_assistant/bidbook/sg_facade.py`; `docs/civil-buddy/real-tender.md`, `plugins.md`, `civil-codex-eval-2026-09-19.md`; `test/benchmarks/verdicts/cases.json` (the recorded `qwen2.5:3b` sentence); `docs/submission/创意材料-工友侧.md` (worker-side material, 31 Aug 2026); `.agents/skills/{worker-brief,safety-brief,hr-labor}/SKILL.md` and `demo/kb/`; tonnes fix `53a550e` (13 Sep 2026). <https://github.com/LUOaini1213/civil-buddy-sme>
8. BCA. "Listing of Registered Contractors" (open dataset on data.gov.sg, last updated 12 January 2026; coverage 1 July 2025 to 31 January 2026). Counts by Team Mintang through the data.gov.sg API on 26 September 2026: 24,014 workhead registrations and 15,864 distinct UENs; CR16 Curtain Walls 296 registrations (296 UENs); CR17 Windows 56; RW01 Window Contractors 278. <https://data.gov.sg/datasets/d_dcda79be4aded5f9e769b8e23ff69b47/view>
9. BCA. Speech by the Minister for National Development at the BuildSG LEAD Summit 2026. 30 April 2026. Published in the BCA newsroom and by the Ministry of National Development.
10. BCA. "Artificial Intelligence (AI) for the Built Environment." Page updated 5 August 2026 (use-case list dated 20 July 2026). <https://www1.bca.gov.sg/growth-and-transformation/productivity/ai/>
11. Enterprise Singapore. "EDGE Grant." Accessed 26 Sep 2026. <https://www.enterprisesg.gov.sg/financial-support/edge-grant>
12. BCA. "Built Environment Technology and Capability (BETC) Grant." Page last updated 25 September 2026. <https://www1.bca.gov.sg/buildsg/buildsg-transformation-fund/built-environment-technology-and-capability-(betc)-grant>
13. Singapore Business Federation (SBF). *National Business Survey 2025: Singapore Budget 2025 Edition* (report; fieldwork 27 March–21 April 2025, 526 businesses, 83% SMEs). <https://www.sbf.org.sg/docs/default-source/about-us/sbf-national-business-survey-2025--singapore-budget-2025-edition-report-(final).pdf?sfvrsn=245daeac_1>
14. BCA. "Specific Registration Requirements for Construction-Related Workhead (CR)", June 2025 edition (CR16 Curtain Walls: definition and grade requirements), linked from the BCA CRS page. <https://isomer-user-content.by.gov.sg/338/791a4d62-df87-4320-b488-f22f8b6eb7d3/registration_cr.pdf>
15. BCA. "Contractors Registration System (CRS)." Accessed 26 Sep 2026. <https://www1.bca.gov.sg/growth-and-transformation/procurement/registration-of-built-environment-firms/contractors-registration-system-crs/>
16. Koon Tak Hong Consulting Pte Ltd. Blog post on building façade subcontract works and their contract and procurement risks (opinion; cites no sources). 10 December 2025. <https://koontakhong.com/2025/12/10/building-facade-subcontract-works-contract-and-procurement-risks/>
17. BCA. "CRS, FM and SY registries: tendering limits" (CW and CR grades; limits valid 1 July 2026 to 30 June 2027). Accessed 26 Sep 2026. <https://www1.bca.gov.sg/growth-and-transformation/procurement/registration-of-built-environment-firms/tendering-limits/crs-fm-and-sy-registries-tendering-limits/>
18. BCA. *CONQUAS (Private Residential) manual*, R1. 20 April 2026. <https://isomer-user-content.by.gov.sg/338/e4bbe202-d7f6-4458-b265-01d6fc91e783/CONQUAS%20(Private%20Residential)%20manual%20(R1).pdf>
19. SBF. "Business Confidence Continues to Slide with Cautious Outlook for 2026" (National Business Survey 2025, Annual Business Sentiments Edition). Press release, 27 November 2025. <https://www.sbf.org.sg/newsroom/media/press-releases/detail/business-confidence-continues-to-slide-with-cautious-outlook-for-2026>
20. Ministry of Manpower (MOM). "Construction sector: Work Permit requirements." Last updated 3 July 2026. <https://www.mom.gov.sg/passes-and-permits/work-permit-for-foreign-worker/sector-specific-rules/construction-sector-requirements>
21. BCA. "Strengthening Singapore's built environment: advancing built environment professions and improving liveability in private developments" (MND Committee of Supply 2026). 4 March 2026. <https://www1.bca.gov.sg/resources/newsroom/strengthening-singapore-s-built-environment--advancing-built-environment-professions-and-improving-liveability-in-private-developments/>
22. Infocomm Media Development Authority (IMDA). *Singapore Digital Economy Report 2025* (released October 2025). <https://www.imda.gov.sg/-/media/imda/files/about/resources/corporate-publications/annual-report/imda-sgde-report-fy2024-2025.pdf>
23. Amazon Web Services. Amazon Lightsail User Guide: "Regions and Availability Zones for Lightsail." Accessed 26 Sep 2026. <https://docs.aws.amazon.com/lightsail/latest/userguide/understanding-regions-and-availability-zones-in-amazon-lightsail.html>
24. Amazon Web Services. Amazon Bedrock User Guide: "Regional availability by endpoints" and "Regional availability by models." Accessed 26 Sep 2026. <https://docs.aws.amazon.com/bedrock/latest/userguide/endpoints-region-availability.html>; <https://docs.aws.amazon.com/bedrock/latest/userguide/models-region-compatibility.html>
25. IMDA. Pre-Approval ICM Vendor Guide: "Eligibility criteria." Accessed 26 Sep 2026. <https://preapproval-guide.imda.gov.sg/pre-approval-guide/eligibility-criteria>
26. Singapore Department of Statistics (SingStat). Table M600981, "Enterprise Landscape by SMEs and Non-SMEs, Annual." Data last updated 30 March 2026. <https://tablebuilder.singstat.gov.sg/table/TS/M600981>
27. Building and Construction Authority (BCA). "Steady construction demand in 2026 as Singapore steps up support for built environment firms through collaboration and innovation." Media release, 22 January 2026. <https://www1.bca.gov.sg/resources/newsroom/steady-construction-demand-in-2026-as-singapore-steps-up-support-for-built-environment-firms-through-collaboration-and-innovation/>
28. Inland Revenue Authority of Singapore, via SingStat. Table M130551, "Taxable Companies by Economic Sector, Annual." Data last updated 22 July 2026. <https://tablebuilder.singstat.gov.sg/table/TS/M130551>
29. SingStat. Table M602281, "Number of Resident-Owned Enterprises by Sex of Owner and Industry, Annual." Data last updated 30 April 2026. <https://tablebuilder.singstat.gov.sg/table/TS/M602281>
30. Ministry of Finance. "Procurement processes." Last updated 9 September 2026. <https://www.mof.gov.sg/policies/government-procurement/procurement-processes/>
31. Amazon Web Services. "Amazon Lightsail pricing" (Linux/Unix bundles with a public IPv4 address). Accessed 26 Sep 2026. <https://aws.amazon.com/lightsail/pricing/>
32. GoBusiness Singapore. PSG Solutions Directory: "CSG - Novade Safety-HSE", "Hubble Safety Management System" (both Built Environment, Smart Inspection and Management - e-PTW) and "CUBICOST 5D BIM Cost Management Solution Version 3" (Glodon International). Accessed 26 Sep 2026. <https://grants.gobusiness.gov.sg/support/productivity-solutions-grant/psg-directory/csg-novade-safety-hse>; <https://grants.gobusiness.gov.sg/support/productivity-solutions-grant/psg-directory/hubble-safety-management-system>; <https://grants.gobusiness.gov.sg/support/productivity-solutions-grant/psg-directory/cubicost-5d-bim-cost-management-solution-version-3>
33. Amazon Web Services. "AWS Activate: credits." Accessed 26 Sep 2026. <https://aws.amazon.com/startups/credits>
34. Enterprise Singapore. "Productivity Solutions Grant." Accessed 26 Sep 2026. <https://www.enterprisesg.gov.sg/financial-support/productivity-solutions-grant>
35. Enterprise Singapore. "EDGE Grant" FAQs. Accessed 26 Sep 2026. <https://www.enterprisesg.gov.sg/resources/all-faqs/edge-grant>
36. BCA. Circular, "Productivity Solutions Grant (PSG) for Built Environment" (tranche 1 April 2026 – 31 March 2031). 1 April 2026. <https://isomer-user-content.by.gov.sg/338/40140aed-8bdf-404c-8bb2-d894e1c5a83e/2026_Circular_Promotion%20of%20Productivity%20Solutions%20Grant%20Tranche%203%20(PSG).pdf>
37. BCA. "Built Environment Productivity Solutions Grant (PSG)." Page last updated 25 September 2026. Accessed 26 Sep 2026. <https://www1.bca.gov.sg/grants-and-funded-programmes/built-environment-productivity-solutions-grant/>
38. Vendor websites, no publication date, accessed 26 Sep 2026: Procore <https://www.procore.com/en-sg>; Autodesk <https://construction.autodesk.com/>; Hubble <https://hubble.build/>; Novade <https://www.novade.net/construction-project-management-software-singapore/>; EasyCargo <https://www.easycargo3d.com/en/>; Cargo-Planner <https://www.cargo-planner.com/>.
39. Lucius AI. "GeBIZ Singapore government tenders guide" (vendor blog). 30 July 2026, updated 23 September 2026. <https://ailucius.com/blog/gebiz-singapore-government-tenders-guide>
40. MOM. "Workplace Safety and Health Report 2025." Press release, 25 March 2026. <https://www.mom.gov.sg/newsroom/press-releases/2026/0325-wsh-report-2025>
