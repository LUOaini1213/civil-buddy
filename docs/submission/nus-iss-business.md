---
title: "civil-buddy: Business Proposal"
subtitle: "NUS-ISS “Show Me Your Agents” Hackathon 2026"
author: "Team Mintang · Team Code PJ2U63AF"
date: "DRAFT 2026-09-26 · product facts as of main at d3ada11 (2026-09-26)"
---

> **Draft for the team: delete this box before exporting to PDF.** This file is in a public repository. Never write the partner's name, owners, UEN, address, projects, clients or people here, not even as an example. The `{{SME_…}}` tokens are filled only when `scripts/submission/build_nus_docs.py` builds the PDF, from the untracked `docs/submission/sme.local.json` (copy `sme.local.example.json`, fill it with confirmed facts only, never commit it). A token with no value prints as a highlighted `[TEAM TO FILL: …]` and is counted. Resolve or delete every `[TEAM TO FILL]` and `[TEAM TO VERIFY]`. Product facts follow the Technical Document (`nus-iss-technical.md`) and must not contradict it; the façade measurements in §4 come from our façade study on synthetic files (reference list, "Façade study"). Market and policy figures carry numbered references, each opened on or before 26 September 2026. The partner's feedback is verbal so far; there is no pilot, letter of intent, price or user count. Add one only if it is real and the partner has agreed.

## 1. Executive summary

**Our partner and its three jobs.** Our partner is {{SME_NAME}}, a Singapore curtain-wall contractor registered with BCA under {{SME_CRS}} [TEAM TO VERIFY: SME-track eligibility — use "SME" for the partner only if the organisers confirm]. One of our team members works there and represents it in this entry (§2.2) [TEAM TO VERIFY: written authorisation]. Its work runs through three jobs, and each ends in numbers or verdicts that are expensive to get wrong:

1. **Reviewing façade tenders.** Each enquiry has to be read clause by clause for the workhead, duration, bonds, liquidated damages, retention, mock-ups, testing and PE-endorsed submissions. A clause missed at tender still binds after award.
2. **Crating and shipping unitised panels and glass.** A unitised curtain-wall unit is assembled in the factory and can weigh over 500 kg, and 1,000 kg in some cases [1]. Crate and container counts cannot be guessed from a spreadsheet.
3. **Installation paperwork, including work at height.** Daily reports, method statements and safety briefs; and on a worksite where a person could fall more than 3 m, a permit-to-work [2][3]. In 2025, falls from height were construction's leading cause of fatal and major injuries (43) [4].

What the partner told us is in §2.3. So far it is verbal; we are asking for a written confirmation [TEAM TO VERIFY: that the request was sent].

**What we built for them.** civil-buddy is an agent workbench with 66 job "posts" that turn a person's words and the firm's own files into internal drafts in Word, Excel and Markdown. Three of its flows match the partner's three jobs. On synthetic façade files (§4), with no model and no network:

- the tender check lists the CR16 workhead, the 420-day duration, the validity period, the performance bond, the defects-liability period, all 3 rejection clauses and the 4 evaluation weightings, each with its clause reference;
- a list of 24 unitised panels becomes 6 × 40HQ containers that fit, with 24 → 24 pieces and 10,800 → 10,800 kg conserved;
- the high-risk façade and safety posts write nothing until a person types the sign-off sentence [5].

The same study shows what is missing: the tender check still drops the façade testing and mock-up clauses without saying so, the packing plan ignores glass-handling notes, and English commands end as chat with no document. English commands, façade tender topics and glass-handling notes are being added before the demo on 10 October 2026. Stillages for glass and flat-rack containers are not planned yet (§4).

**Why the partner can trust it.**

- **Code computes every number.** A model may plan and phrase, but its text never reaches a deliverable. Every post also works with no model at all.
- **A licensed person signs.** The 19 high-risk posts write nothing until a person types a fixed sign-off sentence. Since our security baseline was merged on 26 September 2026 (pull request #61, 142 of 142 release checks passing in CI), this holds over the web API and the MCP server as well as in the desktop app, the terminal UI and the workbench page: an approval flag sent by a program no longer approves anything [6][7]. The exception is two separate Rust tools that are not part of the deployed product (§5). Every draft is marked `submit_blocked`: a person signs and submits outside the product.
- **The firm's files stay with the firm.** It runs on a laptop today. The target is one company server per firm; the first is not yet running, and we plan to set it up before submitting and give its URL in the submission email. In the default no-key mode nothing is sent to a model, and the tender check makes no network request unless the user gives it a public link to fetch. No partner document is in our repository; every test file is synthetic.
- **We publish our weak spots.** Tender-to-bid matching scores precision 1.000 and recall 0.980 on a 19-case development set that the rules were tuned on. Only 0.229 of stated facts land in the right field across 65 posts [6].

**Pilot and market.** We propose an 8–10-week pilot at the partner on documents it chooses, with metrics it agrees (§6). Beyond the partner, 296 firms hold BCA's Curtain Walls workhead (CR16), 215 of them at the entry grade [8]. The same flows then reach the 2,450 general-building and civil-engineering contractors (§7).

**Why now.** The government has formed an Action Team on built-environment productivity, and the Minister for National Development called for the industry to "scale up the adoption of robotics and AI technologies" [9]. BCA's own list of AI use cases for the built environment includes tender and contract management, and site documentation and reporting [10]. From 30 September 2026 the EDGE grant offers up to 70% support for SMEs [11], and BCA's BETC grant co-funds technology for built-environment firms, sub-contractors included [12]. In SBF's survey of 526 businesses (83% SMEs), the top challenges of transforming a business were the cost of adopting new technology (47%), getting staff skilled (31%) and uncertain return (30%) [13]. civil-buddy needs no model spend and is used in a browser; its return has not been measured and would be measured in the pilot, not asserted.

**What is not ready yet.** No firm has used civil-buddy on live work, the partner included; the pilot has not started, and there is no customer or price. The company server is not yet running; there are no user accounts yet, so a sign-off does not name its approver; and the Bedrock path has never been run. The quality of model mode has not been measured. The interface and sign-off sentence are in Chinese, English commands currently end as chat with no document, and English tenders are reproducibly measured only on synthetic sets.

**What we ask for.** [TEAM TO FILL: confirm. Suggested: (1) AWS credits and an architecture review for the partner's pilot server on Lightsail; (2) SBF introductions to two or three other façade and cladding subcontractors for a second round of pilots once the partner's has run; (3) guidance on the EDGE route, which opens on 30 September 2026, on BCA's BETC grant, and on whether BCA's Built Environment PSG continues after Enterprise Singapore's PSG ends on 29 September.]

| Judging criterion | Where this proposal answers it |
|---|---|
| SME readiness | §2 the partner · §4 value per job · §5 safe adoption · §6 pilot · §8 business model · §9 channels and grants |
| Best use of agents | §4.4, and the Technical Document [6] for engineering depth |
| Social impact | §11 |

## 2. Our partner

### 2.1 Who they are

{{SME_NAME}} ({{SME_NAME_ZH}}; UEN {{SME_UEN}}) is a Singapore curtain-wall contractor, registered with BCA under {{SME_CRS}}. [TEAM TO VERIFY: SME-track eligibility — use "SME" for the partner only if the organisers confirm]

CR16 "Curtain Walls" is BCA's workhead for the supply and installation of curtain walls [14]. Registration in BCA's Contractors Registration System (CRS) lets a firm bid for public-sector construction up to its grade's tender limit and work as a first-level subcontractor on public projects; since 1 June 2025 a firm must also be registered before it can hire construction Work Permit or S Pass holders [15].

[TEAM TO FILL: eligibility note per the organisers' answer. This file is public: keep the wording generic and name no company here.]

This proposal gives no headcount, revenue, project, client or staff member of the partner: none has been confirmed to us in writing.

### 2.2 Our representative at the partner

One of our four team members works at the partner as {{SME_REP_ROLE}} and represents it in this entry with its authorisation, as the SME track asks. [TEAM TO VERIFY: the authorisation is in writing and meets the organisers' SME-track rules.] That member carries the partner's questions to the team and takes our drafts back for its review. So far no partner document has been used: every file behind the measurements in this proposal is synthetic, and none of the partner's documents is in our public repository.

### 2.3 What the partner told us

{{SME_FEEDBACK}}

So far this feedback is verbal. We are asking the partner to confirm it in writing [TEAM TO VERIFY: that the request was sent, and when; replace this sentence with the date of the written confirmation once it arrives]. Until then, we quote the partner only as above and give no volume, time or cost figure from it.

## 3. The partner's problem

This section gives sourced facts about the work of a Singapore curtain-wall contractor. It does not describe the partner's own figures, which only the partner can give.

### 3.1 Job 1: reviewing façade tenders

- **The tender arrives as a subcontract with design in it.** One Singapore contracts consultancy describes façade works as commonly let as nominated subcontracts, most of them design-and-build or partial design-and-build because façade contractors hold proprietary designs. It also warns that a main contractor with no design role can become jointly liable for the façade design once it signs. This is an opinion piece that cites no sources [16].
- **The grade limits the tender.** For CR workheads, the public tender limit runs from S$0.8M at grade L1 to unlimited at L6 [17]. Each grade needs a minimum paid-up capital and net worth, a track record and qualified staff: at L1, S$50,000 of each, a S$300,000 track record over three years and one diploma holder [14].
- **Tests and declarations sit in the clauses.** BCA's CONQUAS quality assessment for private housing samples 5% of the curtain-wall area for site water-tightness tests (10% or 20% at higher tiers). It also asks for the qualified person's declaration that the tempered glass at balconies, canopies and shower screens was 100% heat-soak tested, in line with SS 653:2020, the code of practice for glazing in buildings [18].

The synthetic façade enquiry we wrote for our study carries clauses on these topics and more: performance and visual mock-ups, laboratory and site tests, heat soak, PE-endorsed calculations and shop drawings, liquidated damages, retention, warranties, insurance and panel handling. They are what the tender check has to find (§4.1).

### 3.2 Job 2: crating and shipping unitised panels and glass

- **Heavy, glazed, factory-made units.** In a unitised curtain wall, the glass and boards are built into a unit in the factory, which removes glass work on site. Units can weigh over 500 kg, and 1,000 kg in some cases (a façade manufacturer's technical page) [1].
- **What is not published.** We found no official Singapore source on how façade units reach site, whether in crates, stillages, A-frames or containers, and none on what share is made abroad. How the partner packs and ships is its own information: [TEAM TO FILL: in generic terms only, and only if the partner confirms it — crate or stillage type, container types; no factory location, supplier or project].
- **Why a guess is costly.** In the team's description, a salesperson guesses the container count from the spreadsheet, and a wrong guess means changing containers or cargo held at port. No time study was done [7].

### 3.3 Job 3: installation paperwork, including work at height

- **Work at height.** Under the Work at Heights Regulations 2013, "hazardous work at height" is work where a person could fall more than 3 m. The Regulations require a fall prevention plan, training, supervision and inspection, and a permit-to-work system that includes posting the permit and reviewing it daily [2]. MOM's factsheet says the permit applies at workplaces defined as factories, which typically include construction worksites, and that one permit runs for up to 7 days with daily review. The occupier's duty to run the permit system cannot be delegated by contract [3].
- **Lifting and records.** Lifting with a tower, mobile or crawler crane is high-risk construction work that needs a permit-to-work system [19]. Every employer must carry out a risk assessment, keep the records for at least three years and review it at least every three years [20].
- **Falls from height.** In 2025, falls from height were the leading cause of fatal and major injuries in construction (43, after 44 in 2024). Of the 7 fatal falls from height across all industries in 2025, 4 were in construction [4]. MOM does not publish a figure for façade or curtain-wall work.
- **Skilled trades.** BCA's CoreTrade scheme lists "Cladding & Curtain Wall Installation" and "Glazing Works" among its architectural trades [21].
- **The record outlives the job.** Since 1 January 2022 [22], BCA's Periodic Façade Inspection (PFI) regime has required the owner of every building over 13 m (landed homes and temporary buildings excepted) to have a Competent Person inspect its façade once the building is more than 20 years old, and again from the 7th year after each BCA notice. Curtain walls are explicitly in scope. The defects listed for them include loose gaskets and seals, misaligned transoms, broken panels, corroded brackets and failed joints, and the report must include the façade's as-built drawings and maintenance history [23]. BCA expected about 30,000 buildings to be inspected in the first seven-year cycle [22], and says that on average more than 20 incidents of fallen façade elements are reported to it every year [24]. civil-buddy has no PFI post; we cite the regime only because it shows how long façade records stay in use.

### 3.4 The pressures every construction firm shares

- **Scarce people.** Manpower cost is businesses' top challenge (63%), and foreign-workforce policy is felt most by construction and civil-engineering firms (with hotels and restaurants) [25]. A construction firm may employ five Work Permit holders for each local employee earning the qualifying salary [26]. BCA expects the industry to need at least 1,000 new architects and engineers a year [27]: the people whose sign-off matters are in demand.
- **Hard to adopt technology.** Cybersecurity and data-privacy risk rose to 36% of businesses naming it as a business challenge in 2025 [25]. SME adoption of AI reached 14.5% in 2024, mostly off-the-shelf generative AI, and construction is among the sectors with lower digital adoption intensity [28].

### 3.5 Where the expensive mistakes hide

These examples come from the team's own descriptions and from testing civil-buddy on synthetic tenders and test packing lists; none is partner data.

| Work | What we have seen |
|---|---|
| Bid against tender | A construction plan says 560 calendar days where the tender allows 540, while our own bid letter says 540. The project manager's name is spelt two ways across our files [7]. |
| Rejection clauses | They are scattered and phrased many ways. The tool lists each clause with an empty box, but the list "is not a licence to skip reading" [7]. |
| Packing lists | Our own code once read "Gross Weight (t)" as kilograms, turning 1.35 t into 1.35 kg, until we fixed it on 13 September 2026 [7]. |
| A model's verdict | A small local model (`qwen2.5:3b`) wrote that a bid bond "complies with the tender" when the tool had found only candidate matches. Its numbers were kept to the sources; the conclusion was invented (archived live-model observation, not rerun [7]). |
| Safety briefs | In the team's words, "the foreman reads a page of regulation text aloud; workers sign and leave" [7]. |

SME adoption of AI has been driven mainly by off-the-shelf generative-AI tools [28], and a general chat assistant can make exactly these mistakes, fluently.

## 4. What we built for them

**What is measured, and on what.** The façade figures below come from running civil-buddy at `d3ada11` offline, in its default no-key mode, on synthetic files written for this purpose: a Singapore façade subcontract enquiry, a 24-panel and a 140-piece packing list, and installation daily-report, work-at-height and method-statement inputs [5]. The other figures are from the Technical Document [6]. None is partner data. **We have not measured staff time saved.** Every time figure is machine time; time saved is a pilot metric. Each "before" line is the team's understanding of current practice, not something observed at the partner.

### 4.1 Flow 1: façade tender review

**Before.** Staff read the enquiry and every response file line by line and compare numbers by eye.

**Works today.**

- The tool extracts the requirements it recognises, each with its exact quote and, where the layout allows, its clause number and page. A layout it has not seen can make it miss some.
- On the synthetic façade enquiry (four sections and an appendix table), the tender check lists, each with its clause reference: the tender reference, the closing date, the CR16 workhead, 420 calendar days, 90-day validity, a 10% performance bond by banker's guarantee, a 12-month defects-liability period, "alternative tenders not permitted", all 3 rejection clauses, and the Price-Quality Method with its 4 weightings [5].
- It compares each value it finds in our response files with the tender, flags mismatches as "needs review" (naming the file), lists values that differ between our own files, lists the rejection clauses as a checklist with one empty box each, lists document properties (author, company) side by side, shows what changed since the last check, and does not write "can bid" or "confirmed compliant".
- It can also draft an English Singapore façade "Contractor's Proposal" in which every price, UEN and track-record cell stays `[TO FILL]` for a person [5].
- **Evidence beyond façades.** On a 19-case development set that the rules were tuned on, linking scores precision 1.000 and recall 0.980; all 14 planted number conflicts are found, with none false. On a bundled synthetic tender with three bid files, the tool locates 72 requirements, raises 3 conflicts and writes 14 files in 1.6 seconds, offline, with no model call [6].

**Found in the façade study, and being fixed before 10 October.**

- None of the eight façade-specification clauses (laboratory mock-up, visual mock-up, heat soak, site hose test, PE-endorsed calculations and shop drawings, warranties, panel delivery, insurance) reaches the review table, and nothing warns that they were left out. Liquidated damages and retention in the appendix table are dropped too, and the bizSAFE and track-record requirements are missed [5]. **Being added:** façade tender topics in English and Chinese, measured on a held-out façade enquiry written before the first run.
- The English proposal's compliance schedule can mark a clause "No Deviation" when it is not met. A pattern meant for cargo securing matched the letters "CTU" inside "structural", and the clause asking for upright A-frame delivery was marked covered although the plan used steel frames [5]. **Being fixed;** until then the pilot does not use that schedule.
- The review table is in Chinese, and English commands end as chat with no document. **Being added:** English commands.

**The person still** checks every candidate response (none is marked verified), ticks each rejection clause, reads the evaluation method, instructions and every addendum in full, and signs outside the product [7].

**Not yet proven:** real English tenders. English parsing is reproducibly measured only on synthetic sets, and the one archived real English tender scored 0/13 fields on its first run [6]. **Pilot measures:** hours per tender review, and façade clauses found against those the partner finds by hand.

### 4.2 Flow 2: packing and shipping unitised panels

**Before.** Container count and stowage are estimated from experience and a supplier spreadsheet.

**Works today.**

- Columns and units are mapped: "3 EA" reads as 3, and "10/12" is flagged rather than read as 1012. A row without usable weight, dimensions or a whole-number quantity stops the plan, with one plain sentence per row. PDF lists are read only in known layouts.
- On a synthetic list of 24 unitised panels (4,200 × 1,500 × 250 mm, 450 kg each, 10,800 kg in all), the engine puts each panel in a 4 m steel frame and plans 6 × 40HQ containers that fit. Conservation holds: 24 → 24 pieces and 10,800 → 10,800 kg. The structure verdict for all 24 crates is "pending detailed design": without structural facts, the engine does not invent a pass. Lashing stays unspecified [5].
- On the packing page it pauses for a person to confirm the crates (an API caller that does not ask for the pause skips it), then plans containers of one type with a 3D layout, centre of gravity and risk verdict. It refuses to return a plan if the piece count differs between input and plan, or the mass differs beyond a small rounding tolerance. Drafts are marked not for booking; lashing and the VGM are signed separately.
- **Evidence beyond façades.** A long-frame list of 23,800 kg becomes 9 crates and, after a person confirms, 3 × 40HQ containers that fit, with the same mass in and out. Pieces in equal pieces out on all 50 test lists (3,571 pieces). All 128 automated runs completed, but completing is not fitting: 71 produced a plan that fits, and 84 ended with the plan marked for revision by a person [6].

**Found in the façade study.**

- The plan is conservative: one panel per frame uses about a fifth of each crate, and the six containers carry 9% of their rated payload [5].
- Handling notes change nothing: the plan is the same with the Chinese note "glass, fragile, do not tip, transport upright, do not stack", with English notes to the same effect, and with no note. On a mixed list, bracket cartons were packed into two glass-panel crates, and canopy glass with aluminium sheets [5].

**Being added before 10 October:** English handling words (glass, fragile, upright, do not stack, A-frame), notes read from the job's own packing list, and fragile, upright or no-stack rows kept out of mixed crates.

**Not planned yet:** A-frame or stillage crates, which need the partner's real stillage dimensions, tare weight and capacity (anything else would be invented numbers); 40-foot flat-rack and open-top containers, which the engine refuses today; and more than one container type in a plan [5]. **Pilot measures:** containers planned against containers actually shipped, and pieces and kilograms conserved from list to plan.

### 4.3 Flow 3: installation paperwork with a licensed sign-off

**Before.** Daily reports, safety briefs and permit paperwork are typed by hand, and gaps are filled from memory.

**Works today.**

- A person picks a post (for example, the daily report) or just types, attaches files, and downloads editable Word and Excel. Gaps stay `[A001]` / `UNSPECIFIED` / `TBD`.
- The high-risk façade post, and the safety-brief, method-statement and hazard posts, write nothing until a person types the sign-off sentence; in the façade study each replied that nothing was written, and wrote only after the sentence [5]. This holds in the desktop app, the terminal UI and the workbench page, and, since 26 September 2026, over the web API and the MCP server too.
- From Chinese "label: value" lines, the daily-report post placed 7 of 10 façade-installation facts by our scorer (about 9 of 10 by eye) [5].
- A firm can add its own report or site-instruction format as a plugin: a procedure, form fields and a template, with no code. A plugin is treated as high-risk until the firm trusts it [7].
- **Evidence beyond façades.** One daily-report request placed all 6 stated facts. On the command line, the safety-brief post wrote nothing without the operator's confirmation and 3 files with it [6].

**Found in the façade study.**

- English requests produced no document: all 7 English command-line requests ended as chat. English daily-report input placed 0 of 8 facts [5].
- The work-at-height brief's body is generic (edges, openings, confined spaces), with nothing about façades; the method-statement post returns 11 empty chapters; and the hazard post does not mention the work-at-height permit [5].
- **The honest counterweight.** Across 65 posts, only 350 of 1,529 stated facts (0.229) land in the right field. The three bid posts and the warehouse post score 1.00, and the other 61 place fewer than half. For most non-bid posts, today's draft is a correct skeleton that keeps the user's words, not a finished form [6].

**Being added before 10 October:** English commands, then an English façade plugin with three forms: a Façade Installation Daily Report, a Work-at-Height Toolbox Briefing and a Panel Installation Method Statement outline. Its knowledge will hold only sourced facts, such as BCA's CR16 workhead and MOM's 3 m permit threshold. As a plugin it asks for the sign-off sentence on every write until the firm trusts it. **Pilot measures:** fields placed on the partner's own daily-report and permit forms.

### 4.4 How the agent works

- **Rules, not a model, pick the post or workflow.** A fixed workflow runs before any open loop; tender review parses the tender, then runs two checkers in parallel on a frozen, hashed handoff.
- **An optional model loop** (off by default) runs only when no workflow matches, with eight registered tools and at most ten steps.
- **A policy check runs before every registered tool call** on the default path, over MCP and through the packing gateway's tool route, and gives a reason for each refusal.
- **Two deterministic guards** check every reply in model mode. One lists numbers with no source; the other strikes verdicts the product may never state. `civil review` runs both on any document, including a colleague's or another AI's, with no model [6].

## 5. Why it is safe for the partner to adopt

| Property | What holds | Status |
|---|---|---|
| **Licensed sign-off** | 19 of 66 posts write nothing until a person types 我明白，将由持证人员签认 ("I understand; a licensed person will sign"). No setting removes this. Every draft carries `submit_blocked` | Live; over MCP and HTTP since 26 Sep 2026 (next row) |
| Sign-off over MCP and HTTP | The server accepts only the typed sentence. An approval flag sent over HTTP no longer approves, and the MCP server neither offers nor accepts one: a high-risk request returns `approval_required`. In model mode an approval covers one turn, not the whole session. On the command line `--confirm` is still the operator's own assertion. The separate Rust MCP binary and Rust workbench still accept a flag; neither is part of the deployed product | Live since the security baseline (pull request #61, merged 26 Sep 2026; 142 of 142 checks in CI) |
| Named approver | Accounts with the roles admin, engineer and licensed approver; each sign-off names its approver. Today it says "local user" | Before the 10 Oct demo |
| **Model proposes, code writes** | The writer receives only the user's words and named files. In civil-buddy's model loop the model cannot approve, and a sign-off sentence it copies is replaced | Live |
| **Local-first, no key needed** | No key, no model call. By default the workbench listens only on the local machine. With no key, the tender posts go to the network only to fetch a public link the user supplies, and each check records every input file's SHA-256 | Live |
| **One company, one server** | One AWS Lightsail instance per company, used in a browser. Job folders and the database stay on that instance; the database is backed up automatically (the last 7 kept), job folders not yet. There is no shared multi-tenant store. Our deployment guide serves both apps only through a TLS proxy, with only ports 80 and 443 open | Not yet running at `d3ada11`; planned before the submission, with its URL in the submission email |
| Closed network by default | Without a token, the workbench, the packing gateway and its container refuse to listen beyond the local machine, and only a genuinely local request is served. Once a token is set, every API request needs it, local ones included; only the page shells and the health check are open. A server behind a proxy must set one, and our deployment guide makes it mandatory. The only way round this is an explicit opt-out setting, which the guide forbids on a server | Live since pull request #61 |
| **Red lines** | No signed or statutory documents, no "can bid" or "can start work", no promised win rate, no submission to GeBIZ, no invented clause numbers, prices or coordinates | Live in the post rules and code writers; in model mode the number and verdict guards check replies |

**At the partner.** The person who types the sign-off sentence is [TEAM TO FILL: the partner's licensed or authorised role for each high-risk document, role only, no name]. The partner's tenders and packing lists stay on its own machine or its own server; none goes into our public repository, and our tests use synthetic files only. The partner is named only in the PDFs sent to the organisers.

The gaps that remain after the baseline are listed in the Technical Document §4.4. Three matter to an adopting firm: a server behind a proxy is safe only with its token set; the Rust tools named above, including the old Rust-workbench trial builds on GitHub Releases, must not be deployed as if they were covered; and on the workbench's packing post, three packing lists that need a person's fix in a row currently switch that post's planning off for everyone until the server restarts.

**Model choice and data residency.** With a key, civil-buddy can be pointed at any OpenAI-compatible endpoint, such as OpenRouter or a local Ollama. Amazon Bedrock's OpenAI-compatible Chat Completions endpoint can be set in the same way, but it has never been run from our code, so whether it works is not yet known; a verification run is planned before the demo [6]. Model-mode quality has not been measured. Lightsail is available in the Singapore Region [29]. There, AWS lists Bedrock's `bedrock-runtime` endpoint as supported and its `bedrock-mantle` endpoint as not supported, and its model table does not list the gpt-oss models for Singapore [30]. A call to Bedrock in the Singapore Region would therefore have to use the `bedrock-runtime` URL of the Technical Document §6.3, and it is not established that Chat Completions works there with a model we could use; the path has not been exercised. AWS says global cross-Region inference may process data in any commercial Region [30], so we do not claim that model calls stay in Singapore. The pilot runs in no-key mode, and firms with sensitive files can keep it or use a local model; masking personal data before cloud calls is on the roadmap.

## 6. Pilot at the partner

- **Who and how long:** the partner, for 8–10 weeks. [TEAM TO FILL: start date and length, once the partner agrees; nothing has started.]
- **Set-up:** one server for the partner behind TLS with accounts, or a laptop install. The pilot runs in no-key mode; a model is added only if the partner asks, after model mode has been measured.
- **Data:** the partner chooses which past tenders, packing lists and daily reports to use. They stay on its machine or server, and none enters our repository.
- **Baseline:** [TEAM TO FILL: the partner's own volumes — tenders reviewed per month, shipments per project, daily reports and permits per week — only as the partner confirms them.]
- **Schedule:** in weeks 1–2 the partner times its current process on [TEAM TO FILL: number] past documents of each kind, and we check English readiness on its past tenders. In weeks 3–8 civil-buddy runs on live documents alongside the usual process, with a person still checking everything. Weeks 9–10 review the metrics below with the partner.

| Metric | How measured | Target |
|---|---|---|
| Staff hours per façade tender review | The partner's time log, before against during the pilot | [TEAM TO FILL] |
| Façade clauses found with the correct clause reference, on the partner's real tenders | Against the partner's own check | [TEAM TO FILL] |
| Conflicts found; false alarms | Against the person's own check | [TEAM TO FILL] |
| Containers planned against containers actually shipped | Shipping records the partner chooses to share | [TEAM TO FILL] |
| Pieces and kilograms conserved from packing list to plan | The plan's own conservation check | 100% |
| Fields placed correctly on the partner's daily-report and permit forms | Our fact-placement benchmark rerun on those forms (0.229 across 65 posts today) | [TEAM TO FILL] |
| High-risk drafts with a named sign-off | The accounts log | 100% |
| Blocked verdicts or untraced numbers in delivered drafts | `civil review` on every draft | 0 |
| Productivity gain; satisfaction with price and quality | Time log and a week-10 survey | Recorded as evidence for pre-approval (built-environment threshold: 20%) [31] |

All targets marked `[TEAM TO FILL]` stay open until the partner agrees them.

## 7. From one façade contractor to the market

### 7.1 Singapore curtain-wall and façade subcontractors

| Measure | Figure | Ref. |
|---|---|---|
| Firms registered under CR16 Curtain Walls | 296: L1 215 · L2 14 · L3 11 · L4 12 · L5 25 · L6 19 | [8] |
| Adjacent registrations | CR17 Windows 56 · RW01 Window Contractors 278 (they may overlap with CR16) | [8] |
| Public tender limits, CR workheads | L1 S$0.8M · L2 S$1.6M · L3 S$5M · L4 S$8M · L5 S$16M · L6 unlimited | [17] |
| CR16 entry grade (L1) | S$50,000 paid-up capital and net worth; S$300,000 track record over 3 years; one diploma holder | [14] |

The counts are our own count of BCA's open dataset (snapshot last updated 12 January 2026). About 73% of CR16 firms (215 of 296) are at L1, whose public tender limit is S$0.8M. A grade reflects a firm's tender limit and finances, not its SME status, and no official count of SMEs among these firms is published; across the whole economy, 99% of enterprises are SMEs [32]. We have not counted cladding firms registered under other workheads.

**Why this segment first.** [TEAM TO FILL: confirm.] CR16 is the workhead for supplying and installing curtain walls [14], so its firms tender for façade work and install at height, and those that use unitised panels also crate and ship them: the partner's three jobs. The segment is a known public list, and the partner's pilot gives the evidence a second firm will ask for. English commands come first, since these firms tender in English. We give no dollar market size until a price is chosen (§8); after that, the serviceable market is firms × annual price. The PFI regime, with about 30,000 buildings expected in its first cycle [22], brings inspection and repair work on existing façades; civil-buddy has no post for it, and we list it only as a later possibility.

### 7.2 The wider construction market

| Measure | Figure | Ref. |
|---|---|---|
| Construction demand (contracts awarded) | 2026: S$47–53B projected; 2025: S$50.5B preliminary; 2027–30: S$39–46B a year. BCA says demand could moderate after Changi T5 | [33] |
| SMEs, all industries (2025) | 99% of 371,000 enterprises; no construction-only split is published | [32] |
| Construction firms | 9,396 taxable companies (YA2024) [34]; 25,700 resident-owned enterprises (2024) [35] | |
| BCA-registered contractors | 15,864 firms. General building (CW01): 2,049; civil engineering (CW02): 935; 2,450 hold either, and 2,085 hold them only in grades C1–C3 | [8] |
| Public tender limits, CW01/CW02 | C3 S$0.8M · C2 S$1.6M · C1 S$5M · B2 S$16M · B1 S$50M · A2 S$105M · A1 unlimited | [17] |

The 15,864 firms span every registry in the dataset, not only CRS construction workheads. General contractors tender for public work on GeBIZ, where purchases above S$90,000 are open tenders judged on published criteria that generally cover quality as well as price [36].

| Segment | Size | First flows |
|---|---|---|
| **Beachhead: curtain-wall contractors (CR16), starting with the partner** | 296 firms [8] | All three: façade tender review, panel packing, installation paperwork with sign-off |
| Window firms (CR17, RW01) | 56 and 278 registrations [8] | Tender review; installation paperwork |
| Small general-building and civil-engineering contractors (C1–C3 only) | 2,085 firms [8] | Bid-against-tender check; daily report and safety brief with sign-off |
| Steel and precast suppliers that crate and ship cargo | [TEAM TO VERIFY: no official count found] | Packing and shipping plan |
| Other registered specialists and subcontractors | Up to 15,864 registered firms [8] | Office posts; the firm's own forms as plugins |

## 8. Business model and pricing

**Cost to serve one firm.**

- **Software:** MIT licence [7], so no licence fee.
- **Server:** one Lightsail instance in Singapore. [TEAM TO VERIFY: plan size and monthly price, from the dated Lightsail pricing page.]
- **Model:** zero in no-key mode. With a key, the tender check in the workbench adds one optional call per checker. [TEAM TO VERIFY: price per million tokens of any chosen model.] Usage is not metered yet [6].
- **Our time:** setup, TLS, backups, updates, support and plugins. [TEAM TO FILL: hours per firm per month.]

| Option | For | Against |
|---|---|---|
| **A. Free self-host, paid managed server.** The MIT code is free on a laptop; we charge for one set-up, secured, backed-up server per firm, with support | Fits the one-company design; the firm keeps its data; no seat counting, so the approver and site staff can all have accounts | Small revenue per firm; we carry server and support costs; needs a company to invoice |
| **B. Per-seat subscription** on the managed server | Familiar; grows with the firm | Penalises adding the approver and foremen, whom the safety story needs; small firms have few seats |
| **C. Grant-eligible fixed package:** server, setup, training and plugins for a year | Answers cost, the top barrier [13]; EDGE pays up to 70% for SMEs [11] | Not open to us yet (§9.2) |
| **D. Setup and plugin service**, added to A or B | Answers the skills barrier and improves fact placement on the firm's own forms, such as the façade daily report and permit forms | Does not scale; must not become custom code |

**The partner's pilot is free** (option A, with the server paid from credits if AWS grants them).

**Paying for the model.** For model use, the firm can bring its own key (its own Bedrock or OpenRouter account), or we pass the cost through. The default stays no key.

**Benchmarks, not our price.** On the GoBusiness PSG directory (total package cost, before any grant), Novade Safety-HSE (electronic permit-to-work) is listed at S$16,000 for one project for a year and S$29,000 for unlimited projects, and Glodon Cubicost packages start at S$3,226 [37].

> **[TEAM TO FILL: chosen model and price.]** A suggestion for discussion only: option A during the partner's pilot, A + D afterwards, and C once eligible. Do not state a price until the team has agreed it and knows the server cost.

## 9. Go-to-market

### 9.1 Channels

1. **The partner as a reference.** Only with its written consent, and only in the words it approves. [TEAM TO FILL: whether the partner agrees to be a reference, and in which form.]
2. **SBF network.** [TEAM TO VERIFY: which SBF associations or programmes serve façade and construction firms, so the ask can name them.]
3. **BCA's public registry** lists registered firms by workhead and grade, with an address and phone number [8], so the 296 CR16 firms can be found. [TEAM TO VERIFY: a PDPA and terms-of-use check before using it for outreach.]
4. **Open source as the trial.** A firm can run the tender check on its own files on a laptop, with no key and no contract; today the interface is in Chinese. [TEAM TO FILL: publish a packaged release of the current app on GitHub Releases before 10 Oct? The Releases page holds only four early Rust-workbench trial builds (v0.1.0 to v0.4.0-workbench, the last on 31 Aug 2026). They predate the security baseline and still accept an approval flag, so they should be marked superseded. The last packaged build of the current app was 0.5.1-preview (never published), and `pyproject.toml` is now at 0.7.0.]
5. **AWS.** AWS Activate Founders starts at US$1,000 in credits, and select participants may qualify for up to US$5,000. Its listed conditions are self-funded, pre-Series B, founded in the last 10 years, and an AWS account on the paid tier [38]. [TEAM TO VERIFY: whether a team with no company qualifies.]

### 9.2 Grants: what the rules actually require

| Scheme | Offer | What it means for us |
|---|---|---|
| Enterprise Singapore PSG | Up to 50%, capped at S$30,000, for pre-approved solutions [39] | **Ceases 29 September 2026**, the day after this submission, together with EDG and MRA; from 30 September, business grant support is applied for under EDGE [11][39]. It closes before any pilot could start, so we do not plan on it |
| EDGE (from 30 Sep 2026) | Up to 70% for SMEs; S$100,000 a year, of which up to S$30,000 for single-function digital solutions. Whether a pre-approved vendor is needed depends on the activity, and the activity list appears from 30 Sep [11][40] | [TEAM TO VERIFY after 30 Sep: our activity, and whether it needs a pre-approved vendor] |
| BCA Built Environment PSG (1 Apr 2026 – 31 Mar 2031) | Up to 50% for pre-approved digital solutions, capped at S$50,000 per firm over five years. This tranche adds more pre-approved solutions in areas such as digital contract management [41] | [TEAM TO VERIFY with BCA: whether it continues after 29 Sep] |
| BCA BETC Grant | Open to built-environment firms registered and operating in Singapore, naming developers, main builders, sub-contractors, consultants and prefabricators. Covers equipment, software, materials, consultancy and professional services. Up to 70% for SMEs and 50% for non-SMEs from 1 Apr 2025 to 31 Mar 2027, then 50% and 30% until 31 Mar 2030. An SME here has group annual turnover of no more than S$100M or group employment of no more than 200 [12] | It is the adopting firm's grant, not ours, and it names sub-contractors. BCA's AI page names it, with the Built Environment PSG, as funding for AI use cases [10]. [TEAM TO VERIFY: whether software from a team with no company qualifies] |
| IMDA pre-approval (vendor side) | Vendor incorporated for at least 18 months, with at least 5 unaffiliated SME users of at least 6 months, 8 h × 5 weekday support, positive equity and a current ratio of at least 1. At least 5 SMEs must report a productivity gain of at least 15% (20% in the built environment) [31] | A four-student team with no company or customers cannot qualify today |

**Our plan.** The pilot does not depend on a grant, and it is built to collect what pre-approval asks for: consented users, six months of use, a measured gain and customer satisfaction. [TEAM TO FILL: whether and when to incorporate.] The earliest pre-approval is 18 months after incorporation.

## 10. Competitive landscape

No vendor below publishes a Singapore market share, so we state none; descriptions paraphrase their own pages.

| Category | Examples | How civil-buddy differs |
|---|---|---|
| General chat assistants | ChatGPT, Gemini, Copilot: the off-the-shelf tools behind most of the rise in SME AI adoption [28] | Fixed fields per post, numbers computed by code, visible gaps, blocked verdicts, licensed sign-off; also runs with no model |
| Construction management suites | Procore, Autodesk, Hubble, Novade: projects, documents, safety permits, inspections [42]. Hubble and Novade have permit-to-work packages in the PSG directory [37] | Not a project-management suite. It drafts and checks documents from the firm's own files, locally, and can sit beside a suite |
| AI tender analysis | Lucius AI reads a GeBIZ tender pack and returns requirements, deadlines, risk flags and a bid/no-bid recommendation [43] | Checks our response against the tender: numbers, internal consistency and document properties. It deliberately gives no bid/no-bid verdict, and in the default no-key mode the tender posts call no model |
| Load planning | EasyCargo, Cargo-Planner: cloud 3D load planning, not specific to construction [42] | We do not compete on solving. We cover both ends: safe reading of messy lists, a stop on bad rows, a person's confirmation and a conservation check |

**Where we are weaker.** Established vendors have customers, support teams, English interfaces, mobile apps and PSG listings; we have none yet. We have not searched specifically for software built for façade contractors [TEAM TO VERIFY: search before claiming that none exists].

## 11. Social impact

**Work at height, briefed so people understand it.** In 2025, falls from height were the leading cause of fatal and major injuries in construction (43) [4], and on a construction worksite a permit-to-work is needed wherever a person could fall more than 3 m [3]. Across construction, the rate of fatal and major injuries was 26.3 per 100,000 workers in 2025, and small-scale works (addition and alteration works, and renovations) accounted for more than 60% of the sector's fatal and major injuries [44]. Two briefing posts ship today [7]. Like most non-bid posts, their drafts are still skeletons that do not yet place most stated facts, and the technician brief is not yet specific to façades (§4.3):

- **worker-brief** drafts a three-minute pre-shift talk in plain words: what we do today; where the danger is; three steps to do it; who calls stop; and a reminder to ask if anything is unclear. It is marked as not a signed briefing.
- **safety-brief** is for technicians and needs the typed sign-off. Its knowledge base names Singapore sources by title: the WSH Council's toolbox-meeting guide and the WSH (Construction) Regulations 2007. Its rules forbid writing "briefing complete, work may start".

The English Work-at-Height Toolbox Briefing planned for the façade plugin (§4.3) is meant for installation crews, and like every high-risk draft it waits for a person's sign-off.

**Fewer errors, open to small firms.** Numbers trace to a source, gaps stay blank and verdicts are blocked. It needs no model spend, runs on a laptop and is free under MIT, and it is meant to let the scarce licensed engineer spend time judging rather than retyping [27].

**Workers' rights, explained.** The hr-labor post drafts a contract checklist, and its knowledge base names MOM and TADM pages by title (Employment Act, salary payment, TADM mediation). Its rules say it explains the law, does not predict dispute outcomes and does not invent salary bands [7].

**Ideas, not delivered.** A phone briefing where three check questions replace the signature, because a signature proves you came and a quiz proves you understood (missing: mobile interface, speech output). Photo-based stop-work, where the model says what it sees and a rule engine decides (missing: vision model, hazard rules). [TEAM TO VERIFY: a MOM or BCA source before claiming anything about workers' languages.]

**We refuse to build** AI that signs on a worker's behalf, automatic "can start work" verdicts, emotion or behaviour scoring of workers, and fully unattended pipelines. In the team's words: however smart the model, it must stop and wait for a person to nod.

## 12. Risks and mitigations

| Risk | Mitigation today | Pilot or roadmap |
|---|---|---|
| **SME-track eligibility of the partner** | We are asking the organisers whether the partner qualifies for the SME track, and we do not call the partner an SME until they confirm. [TEAM TO VERIFY: that the question was sent, and the answer] | If the answer is no, the team decides the track with the organisers, and the proposal says so plainly |
| **Feedback only verbal** | The partner is quoted only as it said it; no volume, time or cost from it is used | Written confirmation to be requested [TEAM TO VERIFY: that the request was sent]; update §2.3 when it arrives |
| **Single-partner dependence** | MIT licence: the partner keeps a working copy whatever happens to us | The 296 CR16 firms are the next segment (§7.1) |
| **The partner's confidential data** | Local-first; no partner document in our public repository; synthetic test files only; the partner named only in the PDFs sent to the organisers | One server for the partner; [TEAM TO VERIFY: PDPA duties for pilot data] |
| **Liability for a wrong document** | Drafts only, `submit_blocked`, licensed sign-off, blocked verdicts. Since 26 September no API or MCP caller of the deployed apps can approve with a flag | Accounts that name the approver are planned before the demo. [TEAM TO VERIFY: legal review of terms and a liability cap before any paid use] |
| **Façade gaps found in our study** | Stated in §4: dropped façade clauses, a compliance schedule that can over-state, handling notes ignored, no stillages | Fixes before 10 Oct (§4, §13); stillages only with the partner's real data |
| **Data privacy** | No model call without a key; the key stays on the host and is never sent to the browser, and moving the model endpoint requires the key to be entered again; the apps are closed to the network unless a token is set | Personal-data masking (roadmap); no claim of Singapore-only model calls |
| **Model errors** | No model by default; number and verdict guards | Model-mode quality is unmeasured, so the pilot measures it before the partner enables a model |
| **Fact placement at 0.229** | Stated openly; the bid posts score 1.00; gaps stay blank | Start with the bid posts and the partner's two or three most-used forms, rebuilt as plugins; re-measure and fix those writers first. [TEAM TO FILL: target] |
| **Not yet English-ready** | Chinese interface and sign-off sentence; English commands end as chat; English tenders measured only on synthetic sets | English commands before 10 Oct; [TEAM TO FILL: English interface and sign-off sentence by when?] |
| **Adoption and skills** | Browser use; forms as plugins; free trial | Setup and training (option D); return measured, not promised |
| **Team continuity** | MIT licence: a pilot firm keeps a working copy | [TEAM TO FILL: who maintains it after the hackathon] |

## 13. Roadmap and milestones

| When | Milestone |
|---|---|
| 26 Sep 2026 (done) | Security baseline, pull request #61 (142 of 142 checks in CI): only the typed sentence approves, over MCP and HTTP too; once a token is set, every API request needs it, local ones included, and without one no server listens beyond the local machine unless an operator explicitly opts out; key lock; packing reads files only inside the sandbox folders |
| Before the submission (28 Sep 2026) | One Lightsail server behind TLS, set up by the deployment guide; its URL goes in the submission email. The partner's written confirmation and the organisers' answer on SME-track eligibility. [TEAM TO VERIFY: server running, URL in the email; both answers received] |
| By 10 Oct 2026 (demo) | Accounts and roles (admin, engineer, licensed approver) with named sign-off; a Bedrock verification run. For the partner's three jobs: English commands; façade tender topics and a compliance schedule that no longer over-states; glass-handling notes and no fragile goods in mixed crates; the English façade plugin (daily report, work-at-height briefing, method-statement outline) |
| [TEAM TO FILL] | English interface and sign-off sentence |
| [TEAM TO FILL: start date agreed with the partner] | Pilot at the partner, 8–10 weeks |
| Once the partner supplies stillage data | A-frame and stillage crates for glazed panels |
| After the demo | Durable audit log, metering and budgets, admin console, single sign-on, personal-data masking, per-user sessions |
| Not planned yet | 40-foot flat-rack and open-top containers (need a sourced carrier specification); more than one container type per plan |
| At least 18 months after incorporation | Earliest IMDA pre-approval application |

The platform rows match the Technical Document §7, which also puts the audit log and metering after the demo. The façade rows come from our façade study [5] and are not in the Technical Document.

## 14. Team

| Name | Role | Contact |
|---|---|---|
| [TEAM TO FILL] | [TEAM TO FILL] | [TEAM TO FILL] |
| [TEAM TO FILL] | [TEAM TO FILL] | [TEAM TO FILL] |
| [TEAM TO FILL] | [TEAM TO FILL] | [TEAM TO FILL] |
| [TEAM TO FILL] | [TEAM TO FILL] | [TEAM TO FILL] |

- **Track:** SME track, with our partner {{SME_NAME}}. [TEAM TO VERIFY: SME-track eligibility — use "SME" for the partner only if the organisers confirm]
- **Authorised representative:** the team member who works at the partner as {{SME_REP_ROLE}} (§2.2).
- **Contact for SBF and AWS follow-up:** [TEAM TO FILL]

## References

1. YKK AP. Technical page on unitized curtain walls (a façade manufacturer's page, undated). Accessed 26 Sep 2026. <https://www.ykkapglobal.com/en/technologies/pickup/pickup_11/>
2. Attorney-General's Chambers, Singapore Statutes Online. Workplace Safety and Health (Work at Heights) Regulations 2013 (amended by S 280/2014 and S 434/2024): definition of hazardous work at height, regs 5–12, Part III (permit-to-work, regs 20–28). Version current at 26 September 2026. <https://sso.agc.gov.sg/SL/WSHA2006-S223-2013>
3. MOM. Factsheet on the Workplace Safety and Health (Work at Heights) (Amendment) Regulations 2014 (undated; changes in force 1 May 2014). <https://www.mom.gov.sg/-/media/mom/documents/safety-health/factsheet-on-wahamendmentregulations.pdf>
4. MOM. *Workplace Safety and Health Report 2025* (national statistics). March 2026. <https://www.mom.gov.sg/-/media/mom/documents/safety-health/reports-stats/wsh-national-statistics/wsh-national-stats-2025.pdf>
5. Team Mintang. Façade study of civil-buddy at `d3ada11`, run offline in the default no-key (steps) mode on synthetic files written for it: a Singapore façade subcontract enquiry (short text and document form), a 24-panel and a 140-piece packing list, and installation daily-report, work-at-height and method-statement inputs, scored with the functions of the repository's `scripts/eval_post_content.py`. 26 September 2026. Internal notes; the synthetic files are not yet in the repository.
6. Team Mintang. *civil-buddy: Technical Document* (NUS-ISS submission), code baseline `main` at `d3ada11`, 26 September 2026. <https://github.com/LUOaini1213/civil-buddy>
7. Team Mintang. civil-buddy repository at `d3ada11` (26 September 2026), MIT licence: security baseline, pull request #61, merged 26 September 2026 (GitHub Actions: 142/142 checks passed in run 36170078042 on the pull request and again in run 36171221472 on `main`), with operator settings in `docs/deploy-minimal.md`; `docs/civil-buddy/real-tender.md`, `plugins.md`, `civil-codex-eval-2026-09-19.md`; `test/benchmarks/verdicts/cases.json` (the recorded `qwen2.5:3b` sentence); `创意材料-工友侧.md` (worker-side material, 31 Aug 2026); `.agents/skills/{worker-brief,safety-brief,hr-labor}/SKILL.md` and `demo/kb/`; tonnes fix `53a550e` (13 Sep 2026). <https://github.com/LUOaini1213/civil-buddy>
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
19. Attorney-General's Chambers, Singapore Statutes Online. Workplace Safety and Health (Construction) Regulations 2007, Part III (permit-to-work system, regs 10–19; high-risk construction work listed in reg 10). Version current at 26 September 2026. <https://sso.agc.gov.sg/SL/WSHA2006-S663-2007?ProvIds=P1III->
20. Attorney-General's Chambers, Singapore Statutes Online. Workplace Safety and Health (Risk Management) Regulations, regs 3, 5 and 7. Version current at 26 September 2026. <https://sso.agc.gov.sg/SL/WSHA2006-RG8?WholeDoc=1>
21. BCA. "CoreTrade Scheme." 6 March 2026. <https://www1.bca.gov.sg/growth-and-transformation/manpower/built-environment-firms/workforce-development/upskilling-of-pmet-workforce/coretrade-scheme/>
22. BCA. "New regulations for periodic inspection of building façades to start from 1 January 2022." Media release, 21 October 2021. <https://www1.bca.gov.sg/resources/newsroom/new-regulations-for-periodic-inspection-of-building-fa-ades-to-start-from-1-january-2022/>
23. BCA. *Guidelines on Periodic Façade Inspection*, Version 1.3. September 2026. <https://isomer-user-content.by.gov.sg/338/51a06852-15e6-4a07-936c-2fa211f8c928/PFI%20Guidelines_V1.3.pdf>
24. BCA. *Periodic Façade Inspection (PFI) FAQs*, Q35 (fallen façade statistics). Undated; linked from BCA's PFI page. Accessed 26 Sep 2026. <https://isomer-user-content.by.gov.sg/338/4f099ad5-3a38-434f-9b81-0a52da31ba91/pfi-frequently-asked-questions.pdf>
25. SBF. "Business Confidence Continues to Slide with Cautious Outlook for 2026" (National Business Survey 2025, Annual Business Sentiments Edition). Press release, 27 November 2025. <https://www.sbf.org.sg/newsroom/media/press-releases/detail/business-confidence-continues-to-slide-with-cautious-outlook-for-2026>
26. Ministry of Manpower (MOM). "Construction sector: Work Permit requirements." Last updated 3 July 2026. <https://www.mom.gov.sg/passes-and-permits/work-permit-for-foreign-worker/sector-specific-rules/construction-sector-requirements>
27. BCA. "Strengthening Singapore's built environment: advancing built environment professions and improving liveability in private developments" (MND Committee of Supply 2026). 4 March 2026. <https://www1.bca.gov.sg/resources/newsroom/strengthening-singapore-s-built-environment--advancing-built-environment-professions-and-improving-liveability-in-private-developments/>
28. Infocomm Media Development Authority (IMDA). *Singapore Digital Economy Report 2025* (released October 2025). <https://www.imda.gov.sg/-/media/imda/files/about/resources/corporate-publications/annual-report/imda-sgde-report-fy2024-2025.pdf>
29. Amazon Web Services. Amazon Lightsail User Guide: "Regions and Availability Zones for Lightsail." Accessed 26 Sep 2026. <https://docs.aws.amazon.com/lightsail/latest/userguide/understanding-regions-and-availability-zones-in-amazon-lightsail.html>
30. Amazon Web Services. Amazon Bedrock User Guide: "Regional availability by endpoints" and "Regional availability by models." Accessed 26 Sep 2026. <https://docs.aws.amazon.com/bedrock/latest/userguide/endpoints-region-availability.html>; <https://docs.aws.amazon.com/bedrock/latest/userguide/models-region-compatibility.html>
31. IMDA. Pre-Approval ICM Vendor Guide: "Eligibility criteria." Accessed 26 Sep 2026. <https://preapproval-guide.imda.gov.sg/pre-approval-guide/eligibility-criteria>
32. Singapore Department of Statistics (SingStat). Table M600981, "Enterprise Landscape by SMEs and Non-SMEs, Annual." Data last updated 30 March 2026. <https://tablebuilder.singstat.gov.sg/table/TS/M600981>
33. Building and Construction Authority (BCA). "Steady construction demand in 2026 as Singapore steps up support for built environment firms through collaboration and innovation." Media release, 22 January 2026. <https://www1.bca.gov.sg/resources/newsroom/steady-construction-demand-in-2026-as-singapore-steps-up-support-for-built-environment-firms-through-collaboration-and-innovation/>
34. Inland Revenue Authority of Singapore, via SingStat. Table M130551, "Taxable Companies by Economic Sector, Annual." Data last updated 22 July 2026. <https://tablebuilder.singstat.gov.sg/table/TS/M130551>
35. SingStat. Table M602281, "Number of Resident-Owned Enterprises by Sex of Owner and Industry, Annual." Data last updated 30 April 2026. <https://tablebuilder.singstat.gov.sg/table/TS/M602281>
36. Ministry of Finance. "Procurement processes." Last updated 9 September 2026. <https://www.mof.gov.sg/policies/government-procurement/procurement-processes/>
37. GoBusiness Singapore. PSG Solutions Directory: "CSG - Novade Safety-HSE", "Hubble Safety Management System" (both Built Environment, Smart Inspection and Management - e-PTW) and "CUBICOST 5D BIM Cost Management Solution Version 3" (Glodon International). Accessed 26 Sep 2026. <https://grants.gobusiness.gov.sg/support/productivity-solutions-grant/psg-directory/csg-novade-safety-hse>; <https://grants.gobusiness.gov.sg/support/productivity-solutions-grant/psg-directory/hubble-safety-management-system>; <https://grants.gobusiness.gov.sg/support/productivity-solutions-grant/psg-directory/cubicost-5d-bim-cost-management-solution-version-3>
38. Amazon Web Services. "AWS Activate: credits." Accessed 26 Sep 2026. <https://aws.amazon.com/startups/credits>
39. Enterprise Singapore. "Productivity Solutions Grant." Accessed 26 Sep 2026. <https://www.enterprisesg.gov.sg/financial-support/productivity-solutions-grant>
40. Enterprise Singapore. "EDGE Grant" FAQs. Accessed 26 Sep 2026. <https://www.enterprisesg.gov.sg/resources/all-faqs/edge-grant>
41. BCA. Circular, "Productivity Solutions Grant (PSG) for Built Environment" (tranche 1 April 2026 – 31 March 2031). 1 April 2026. <https://isomer-user-content.by.gov.sg/338/40140aed-8bdf-404c-8bb2-d894e1c5a83e/2026_Circular_Promotion%20of%20Productivity%20Solutions%20Grant%20Tranche%203%20(PSG).pdf>
42. Vendor websites, no publication date, accessed 26 Sep 2026: Procore <https://www.procore.com/en-sg>; Autodesk <https://construction.autodesk.com/>; Hubble <https://hubble.build/>; Novade <https://www.novade.net/construction-project-management-software-singapore/>; EasyCargo <https://www.easycargo3d.com/en/>; Cargo-Planner <https://www.cargo-planner.com/>.
43. Lucius AI. "GeBIZ Singapore government tenders guide" (vendor blog). 30 July 2026, updated 23 September 2026. <https://ailucius.com/blog/gebiz-singapore-government-tenders-guide>
44. MOM. "Workplace Safety and Health Report 2025." Press release, 25 March 2026. <https://www.mom.gov.sg/newsroom/press-releases/2026/0325-wsh-report-2025>
