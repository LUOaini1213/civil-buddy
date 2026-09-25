---
title: "civil-buddy: Business Proposal"
subtitle: "NUS-ISS “Show Me Your Agents” Hackathon 2026"
author: "Team Mintang · Team Code PJ2U63AF"
date: "DRAFT 2026-09-26 · product facts as of main at d3ada11 (2026-09-26)"
---

> **Draft for the team: delete this box before exporting to PDF.** Resolve or delete every `[TEAM TO FILL]` and `[TEAM TO VERIFY]`. Product facts follow the Technical Document (`nus-iss-technical.md`) and must not contradict it. Market and policy figures carry numbered references, each opened on or before 26 September 2026. This draft contains no customer, pilot, interview, letter of intent, price or user count. Add one only if it is real and the SME has agreed to be named.

## 1. Executive summary

**The problem.** BCA projects S$47–53 billion of construction contracts to be awarded in Singapore in 2026 [1]. Of the 2,450 firms registered with BCA for general building or civil engineering, 2,085 hold those registrations only in the smallest grades (C1–C3), which cap their public tenders at S$5 million [2][3]. In our assessment, a firm like this has a large contractor's paperwork and a handful of office staff to do it: tender responses, crating and shipping plans for steel and precast, daily reports, safety briefs. The costly mistakes are numbers and verdicts, such as a bid duration that contradicts the tender, a container count guessed from a spreadsheet, or a "compliant" that nobody checked. SME adoption of AI has been driven mainly by off-the-shelf generative-AI tools [4], and a general chat assistant can make exactly these mistakes, fluently.

**What civil-buddy does.** civil-buddy is an agent workbench for construction and civil-engineering SMEs. Its 66 job "posts" turn a person's words and the firm's own files into internal drafts in Word, Excel and Markdown. Three flows carry this proposal: checking a bid against the tender, planning how cargo is crated and containerised, and drafting site and office documents. A missing fact stays visibly blank; it is never guessed.

**Why an SME can trust it.**

- **Code computes every number.** A model may plan and phrase, but its text never reaches a deliverable. Every post also works with no model at all.
- **A licensed person signs.** The 19 high-risk posts write nothing until a person types a fixed sign-off sentence. Since our security baseline was merged on 26 September 2026 (pull request #61, 142 of 142 release checks passing in CI), this holds over the web API and the MCP server as well as in the desktop app, the terminal UI and the workbench page: an approval flag sent by a program no longer approves anything [5][17]. The exception is two separate Rust tools that are not part of the deployed product (§4). Every draft is marked `submit_blocked`: a person signs and submits outside the product.
- **The firm's files stay with the firm.** It runs on a laptop today. The target is one company server per firm; the first is not yet running, and we plan to set it up before submitting and give its URL in the submission email. In the default no-key mode nothing is sent to a model, and the tender check makes no network request unless the user gives it a public link to fetch.
- **We publish our weak spots.** Tender-to-bid matching scores precision 1.000 and recall 0.980 on a 19-case development set that the rules were tuned on. Only 0.229 of stated facts land in the right field across 65 posts [5].

**Why now.** The government has formed an Action Team on built-environment productivity, and the Minister for National Development called for the industry to "scale up the adoption of robotics and AI technologies" [6]. From 30 September 2026 the EDGE grant offers up to 70% support for SMEs [7]. In SBF's survey of 526 businesses (83% SMEs), the top challenges of transforming a business were the cost of adopting new technology (47%), getting staff skilled (31%) and uncertain return (30%) [8]. civil-buddy needs no model spend and is used in a browser; its return has not been measured and would be measured in a pilot, not asserted.

**What is not ready yet.** No SME has used civil-buddy on live work; there is no pilot, customer or price. The company server is not yet running; there are no user accounts yet, so a sign-off does not name its approver; and the Bedrock path has never been run. The quality of model mode has not been measured. The interface and sign-off sentence are in Chinese, and English tenders have been measured only on synthetic documents.

**What we ask for.** [TEAM TO FILL: confirm. Suggested: (1) SBF introductions to three to five construction SMEs for an 8–10-week pilot on their own documents; (2) AWS credits and an architecture review for one Lightsail server per pilot firm; (3) guidance on the EDGE route, which opens on 30 September 2026, and on whether BCA's Built Environment PSG continues after Enterprise Singapore's PSG ends on 29 September.]

| Judging criterion | Where this proposal answers it |
|---|---|
| SME readiness | §3 value per flow · §4 safe adoption · §6 business model · §7 pilot and grants |
| Best use of agents | §3.4, and the Technical Document [5] for engineering depth |
| Social impact | §9 |

## 2. The problem SMEs face

### 2.1 A small office with a large contractor's paperwork

- **Registration.** Since 1 June 2025, a firm must register with BCA's Contractors Registration System (CRS) before it can hire construction Work Permit or S Pass holders. Registration is also the gateway to public-sector construction tenders [9].
- **Safety records.** Every employer must carry out a risk assessment, keep the records for at least three years and review it at least every three years [10]. High-risk work such as excavation deeper than 1.5 m, crane lifting, piling and tunnelling needs a permit-to-work system [11].
- **Tenders.** Government purchases above S$90,000 are open tenders on GeBIZ, judged on published criteria that generally cover quality as well as price [12].
- **Scarce people.** Manpower cost is businesses' top challenge (63%). Foreign-workforce policy is felt most by construction and civil-engineering firms (with hotels and restaurants) [13]. A construction firm may employ five Work Permit holders for each local employee earning the qualifying salary [14]. BCA expects the industry to need at least 1,000 new architects and engineers a year [15]: the people whose sign-off matters are in demand.
- **Hard to adopt technology.** Cybersecurity and data-privacy risk rose to 36% of businesses naming it as a business challenge in 2025 [13]. SME adoption of AI reached 14.5% in 2024, mostly off-the-shelf generative AI, and construction is among the sectors with lower digital adoption intensity [4].
- **Physical stakes.** Construction's rate of fatal and major injuries was 26.3 per 100,000 workers in 2025. Small-scale works (addition and alteration works, and renovations) accounted for more than 60% of the sector's fatal and major injuries [16].

> The premise that small firms carry this load with few people, and that wrong numbers and verdicts cost the most, is the team's own analysis. No survey or customer interview supports it yet. [TEAM TO FILL: any real SME conversation, with consent, date and what was said; otherwise keep this note.]

### 2.2 Where the expensive mistakes hide

These examples come from the team's own descriptions and from testing civil-buddy on synthetic tenders and test packing lists; none is customer data.

| Work | What we have seen |
|---|---|
| Bid against tender | A construction plan says 560 calendar days where the tender allows 540, while our own bid letter says 540. The project manager's name is spelt two ways across our files [17]. |
| Rejection clauses | They are scattered and phrased many ways. The tool lists each clause with an empty box, but the list "is not a licence to skip reading" [17]. |
| Packing lists | In the team's description, the salesperson guesses the container count from the spreadsheet, and a wrong guess means changing containers or cargo held at port (no time study was done). Our own code once read "Gross Weight (t)" as kilograms, turning 1.35 t into 1.35 kg, until we fixed it on 13 September 2026 [17]. |
| A model's verdict | A small local model (`qwen2.5:3b`) wrote that a bid bond "complies with the tender" when the tool had found only candidate matches. Its numbers were kept to the sources; the conclusion was invented (archived live-model observation, not rerun [17]). |
| Safety briefs | In the team's words, "the foreman reads a page of regulation text aloud; workers sign and leave" [17]. |

## 3. Our solution and value

**We have not measured staff time saved.** Every time figure below is machine time; time saved is a pilot metric. Each "Before" line is the team's understanding of current practice, not something observed at a customer.

### 3.1 Flow 1: checking a bid against the tender

**Before.** Staff read the tender and every bid file line by line and compare numbers by eye.

**With civil-buddy.**

- The tool extracts the requirements it recognises, each with its exact quote and, where the layout allows, its clause number and page. A layout it has not seen can make it miss some.
- It compares each value it finds in our files with the tender, flags mismatches as "needs review" (naming the file), and lists values that differ between our own files.
- It lists the rejection clauses it finds as a checklist with one empty box each.
- It lists document properties (author, company) side by side, shows what changed since the last check, and does not write "can bid" or "confirmed compliant".

**Evidence.** On a 19-case development set that the rules were tuned on, linking scores precision 1.000 and recall 0.980; all 14 planted number conflicts are found, with none false. On a bundled synthetic tender with three bid files, the tool locates 72 requirements, raises 3 conflicts and writes 14 files in 1.6 seconds, offline, with no model call [5].

**The person still** checks every candidate response (none is marked verified), ticks each rejection clause, reads the evaluation method, instructions and every addendum in full, and signs outside the product [17].

**Not yet proven:** real English (GeBIZ) tenders, since English is measured only on synthetic documents [5]. **Pilot measures:** hours per tender check, and conflicts found against those found by hand.

### 3.2 Flow 2: crating and containerising steel, precast and crated cargo

**Before.** Container count and stowage are estimated from experience and a supplier spreadsheet.

**With civil-buddy.**

- Columns and units are mapped: "3 EA" reads as 3, and "10/12" is flagged rather than read as 1012.
- A row without usable weight, dimensions or a whole-number quantity stops the plan, with one plain sentence per row.
- The tool proposes crates. On the packing page it pauses for a person to confirm them (an API caller that does not ask for the pause skips it), then plans containers of one type with a 3D layout, centre of gravity and risk verdict.
- It refuses to return a plan if the piece count differs between input and plan, or the mass differs beyond a small rounding tolerance. Drafts are marked not for booking; lashing and the VGM are signed separately.

**Evidence.** A long-frame list of 23,800 kg becomes 9 crates and, after a person confirms, 3 × 40HQ containers that fit, with the same mass in and out. Pieces in equal pieces out on all 50 test lists (3,571 pieces). All 128 automated runs completed, but completing is not fitting: 71 produced a plan that fits, and 84 ended with the plan marked for revision by a person [5].

**Limits:** one container type per plan; PDF lists only in known layouts. **Pilot measures:** plans accepted by the logistics person, and re-plans avoided.

### 3.3 Flow 3: site and office documents

**Before.** Daily reports, safety briefs and HR and admin forms are typed by hand, and gaps are filled from memory.

**With civil-buddy.**

- A person picks a post (for example, the daily report) or just types, attaches files, and downloads editable Word and Excel.
- Gaps stay `[A001]` / `UNSPECIFIED` / `TBD`.
- On the 19 high-risk posts (such as construction method, safety brief, structure and geotechnical), nothing is written until a person types the sign-off sentence: in the desktop app, the terminal UI and the workbench page, and, since 26 September 2026, over the web API and the MCP server too.
- A firm can add its own report or site-instruction format as a plugin: a procedure, form fields and a template, with no code. A plugin is treated as high-risk until the firm trusts it [17].

**Evidence.** One daily-report request placed all 6 stated facts. On the command line, the safety-brief post wrote nothing without the operator's confirmation and 3 files with it [5].

**The honest counterweight.** Across 65 posts, only 350 of 1,529 stated facts (0.229) land in the right field. The three bid posts and the warehouse post score 1.00, and the other 61 place fewer than half. For most non-bid posts, today's draft is a correct skeleton that keeps the user's words, not a finished form [5]. §10 explains how the pilot deals with this.

### 3.4 How the agent works

- **Rules, not a model, pick the post or workflow.** A fixed workflow runs before any open loop; tender review parses the tender, then runs two checkers in parallel on a frozen, hashed handoff.
- **An optional model loop** (off by default) runs only when no workflow matches, with eight registered tools and at most ten steps.
- **A policy check runs before every registered tool call** on the default path, over MCP and through the packing gateway's tool route, and gives a reason for each refusal.
- **Two deterministic guards** check every reply in model mode. One lists numbers with no source; the other strikes verdicts the product may never state. `civil review` runs both on any document, including a colleague's or another AI's, with no model [5].

## 4. Why it is safe to adopt

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

The gaps that remain after the baseline are listed in the Technical Document §4.4. Three matter to an adopting firm: a server behind a proxy is safe only with its token set; the Rust tools named above, including the old Rust-workbench trial builds on GitHub Releases, must not be deployed as if they were covered; and on the workbench's packing post, three packing lists that need a person's fix in a row currently switch that post's planning off for everyone until the server restarts.

**Model choice and data residency.** With a key, civil-buddy can be pointed at any OpenAI-compatible endpoint, such as OpenRouter or a local Ollama. Amazon Bedrock's OpenAI-compatible Chat Completions endpoint can be set in the same way, but it has never been run from our code, so whether it works is not yet known; a verification run is planned before the demo [5]. Model-mode quality has not been measured. Lightsail is available in the Singapore Region [18]. There, AWS lists Bedrock's `bedrock-runtime` endpoint as supported and its `bedrock-mantle` endpoint as not supported, and its model table does not list the gpt-oss models for Singapore [19]. A call to Bedrock in the Singapore Region would therefore have to use the `bedrock-runtime` URL of the Technical Document §6.3, and it is not established that Chat Completions works there with a model we could use; the path has not been exercised. AWS says global cross-Region inference may process data in any commercial Region [19], so we do not claim that model calls stay in Singapore. Firms with sensitive files can keep the no-key mode or a local model; masking personal data before cloud calls is on the roadmap.

## 5. Target customers and market

| Measure | Figure | Ref. |
|---|---|---|
| Construction demand (contracts awarded) | 2026: S$47–53B projected; 2025: S$50.5B preliminary; 2027–30: S$39–46B a year. BCA says demand could moderate after Changi T5 | [1] |
| SMEs, all industries (2025) | 99% of 371,000 enterprises; no construction-only split is published | [20] |
| Construction firms | 9,396 taxable companies (YA2024) [21]; 25,700 resident-owned enterprises (2024) [22] | |
| BCA-registered contractors | 15,864 firms. General building (CW01): 2,049; civil engineering (CW02): 935; 2,450 hold either, and 2,085 hold them only in grades C1–C3 | [2] |
| Public tender limits, CW01/CW02 | C3 S$0.8M · C2 S$1.6M · C1 S$5M · B2 S$16M · B1 S$50M · A2 S$105M · A1 unlimited | [3] |

The registry counts are our own count of BCA's open dataset (snapshot last updated 12 January 2026). The 15,864 firms span every registry in that dataset, not only CRS construction workheads. A grade reflects a firm's tender limit and finances, not its SME status, so C1–C3 is only a proxy for "small".

| Segment | Size | First flows |
|---|---|---|
| **Beachhead: small CW01/CW02 contractors (C1–C3 only)** | 2,085 firms [2] | Bid-against-tender check; daily report and safety brief with sign-off |
| Steel, precast and façade suppliers that crate and ship cargo | [TEAM TO VERIFY: no official count found] | Packing and shipping plan |
| Other registered specialists and subcontractors | Up to 15,864 registered firms [2] | Office posts; the firm's own forms as plugins |

**Why this beachhead.** [TEAM TO FILL: confirm.] The segment is a known public list. Its first flow is our best-measured one and, in the default no-key mode, runs with no model call. The catch is that these firms tender in English and our interface is in Chinese, so that must be fixed first. We give no dollar market size until a price is chosen (§6); after that, the serviceable market is firms × annual price.

## 6. Business model and pricing

**Cost to serve one firm.**

- **Software:** MIT licence [17], so no licence fee.
- **Server:** one Lightsail instance in Singapore. [TEAM TO VERIFY: plan size and monthly price, from the dated Lightsail pricing page.]
- **Model:** zero in no-key mode. With a key, the tender check in the workbench adds one optional call per checker. [TEAM TO VERIFY: price per million tokens of any chosen model.] Usage is not metered yet [5].
- **Our time:** setup, TLS, backups, updates, support and plugins. [TEAM TO FILL: hours per firm per month.]

| Option | For | Against |
|---|---|---|
| **A. Free self-host, paid managed server.** The MIT code is free on a laptop; we charge for one set-up, secured, backed-up server per firm, with support | Fits the one-company design; the firm keeps its data; no seat counting, so the approver and site staff can all have accounts | Small revenue per firm; we carry server and support costs; needs a company to invoice |
| **B. Per-seat subscription** on the managed server | Familiar; grows with the firm | Penalises adding the approver and foremen, whom the safety story needs; small firms have few seats |
| **C. Grant-eligible fixed package:** server, setup, training and plugins for a year | Answers cost, the top barrier [8]; EDGE pays up to 70% for SMEs [7] | Not open to us yet (§7.3) |
| **D. Setup and plugin service**, added to A or B | Answers the skills barrier and improves fact placement on the firm's own forms | Does not scale; must not become custom code |

**Paying for the model.** For model use, the firm can bring its own key (its own Bedrock or OpenRouter account), or we pass the cost through. The default stays no key.

**Benchmarks, not our price.** On the GoBusiness PSG directory (total package cost, before any grant), Novade Safety-HSE (electronic permit-to-work) is listed at S$16,000 for one project for a year and S$29,000 for unlimited projects, and Glodon Cubicost packages start at S$3,226 [23].

> **[TEAM TO FILL: chosen model and price.]** A suggestion for discussion only: option A during the pilot (no charge to the pilot firm, server paid from credits if AWS grants them), A + D afterwards, and C once eligible. Do not state a price until the team has agreed it and knows the server cost.

## 7. Go-to-market

### 7.1 Channels

1. **SBF network.** [TEAM TO VERIFY: which SBF associations or programmes serve construction SMEs, so the ask can name them.]
2. **BCA's public registry** lists registered firms by workhead and grade, with an address and phone number [2]. [TEAM TO VERIFY: a PDPA and terms-of-use check before using it for outreach.]
3. **Open source as the trial.** An SME can run the tender check on its own files on a laptop, with no key and no contract; today the interface is in Chinese. [TEAM TO FILL: publish a packaged release of the current app on GitHub Releases before 10 Oct? The Releases page holds only four early Rust-workbench trial builds (v0.1.0 to v0.4.0-workbench, the last on 31 Aug 2026). They predate the security baseline and still accept an approval flag, so they should be marked superseded. The last packaged build of the current app was 0.5.1-preview (never published), and `pyproject.toml` is now at 0.7.0.]
4. **AWS.** AWS Activate Founders starts at US$1,000 in credits, and select participants may qualify for up to US$5,000. Its listed conditions are self-funded, pre-Series B, founded in the last 10 years, and an AWS account on the paid tier [24]. [TEAM TO VERIFY: whether a team with no company qualifies.]

### 7.2 Pilot plan

- **Who and how long:** three to five beachhead SMEs for 8–10 weeks. [TEAM TO FILL: named pilot SMEs with consent, or "none yet"; the length.]
- **Set-up:** one server per firm behind TLS with accounts, or a laptop install. Pilots run in no-key mode, and a model is added only if the firm asks after model mode has been measured.
- **Schedule:** in weeks 1–2 the firm times its current process on its own past documents, and we aim to reach English tender readiness on its past tenders. In weeks 3–8 civil-buddy runs on live documents alongside the usual process, with a person still checking everything. Weeks 9–10 review the metrics below.

| Metric | How measured | Target |
|---|---|---|
| Staff hours per tender check | The firm's time log, before against during the pilot | [TEAM TO FILL] |
| Requirements with the correct clause and page, on real English tenders | A person spot-checks a sample | [TEAM TO FILL] |
| Conflicts found; false alarms | Against the person's own check | [TEAM TO FILL] |
| Fields placed correctly on the firm's forms | Our fact-placement benchmark rerun on those forms (0.229 across 65 posts today) | [TEAM TO FILL] |
| High-risk drafts with a named sign-off | The accounts log | 100% |
| Blocked verdicts or untraced numbers in delivered drafts | `civil review` on every draft | 0 |
| Productivity gain; satisfaction with price and quality | Time log and a week-10 survey | Recorded as evidence for pre-approval (built-environment threshold: 20%) [25] |

### 7.3 Grants: what the rules actually require

| Scheme | Offer | What it means for us |
|---|---|---|
| Enterprise Singapore PSG | Up to 50%, capped at S$30,000, for pre-approved solutions [26] | **Ceases 29 September 2026**, the day after this submission, together with EDG and MRA; from 30 September, business grant support is applied for under EDGE [7][26]. It closes before any pilot could start, so we do not plan on it |
| EDGE (from 30 Sep 2026) | Up to 70% for SMEs; S$100,000 a year, of which up to S$30,000 for single-function digital solutions. Whether a pre-approved vendor is needed depends on the activity, and the activity list appears from 30 Sep [7][27] | [TEAM TO VERIFY after 30 Sep: our activity, and whether it needs a pre-approved vendor] |
| BCA Built Environment PSG (1 Apr 2026 – 31 Mar 2031) | Up to 50% for pre-approved digital solutions, capped at S$50,000 per firm over five years. This tranche adds more pre-approved solutions in areas such as digital contract management [28] | [TEAM TO VERIFY with BCA: whether it continues after 29 Sep] |
| IMDA pre-approval (vendor side) | Vendor incorporated for at least 18 months, with at least 5 unaffiliated SME users of at least 6 months, 8 h × 5 weekday support, positive equity and a current ratio of at least 1. At least 5 SMEs must report a productivity gain of at least 15% (20% in the built environment) [25] | A four-student team with no company or customers cannot qualify today |

**Our plan.** The pilot does not depend on a grant, and it is built to collect what pre-approval asks for: consented users, six months of use, a measured gain and customer satisfaction. [TEAM TO FILL: whether and when to incorporate.] The earliest pre-approval is 18 months after incorporation.

## 8. Competitive landscape

No vendor below publishes a Singapore market share, so we state none; descriptions paraphrase their own pages.

| Category | Examples | How civil-buddy differs |
|---|---|---|
| General chat assistants | ChatGPT, Gemini, Copilot: the off-the-shelf tools behind most of the rise in SME AI adoption [4] | Fixed fields per post, numbers computed by code, visible gaps, blocked verdicts, licensed sign-off; also runs with no model |
| Construction management suites | Procore, Autodesk, Hubble, Novade: projects, documents, safety permits, inspections [29]. Hubble and Novade have permit-to-work packages in the PSG directory [23] | Not a project-management suite. It drafts and checks documents from the firm's own files, locally, and can sit beside a suite |
| AI tender analysis | Lucius AI reads a GeBIZ tender pack and returns requirements, deadlines, risk flags and a bid/no-bid recommendation [30] | Checks our response against the tender: numbers, internal consistency and document properties. It deliberately gives no bid/no-bid verdict, and in the default no-key mode the tender posts call no model |
| Load planning | EasyCargo, Cargo-Planner: cloud 3D load planning, not specific to construction [29] | We do not compete on solving. We cover both ends: safe reading of messy lists, a stop on bad rows, a person's confirmation and a conservation check |

**Where we are weaker.** Established vendors have customers, support teams, English interfaces, mobile apps and PSG listings; we have none yet.

## 9. Social impact

**Safety briefs people understand.** Small-scale works (addition and alteration works, and renovations) account for more than 60% of construction's fatal and major injuries [16]. Two posts ship today [17]. Like most non-bid posts, their drafts are still skeletons that do not yet place most stated facts (§3.3):

- **worker-brief** drafts a three-minute pre-shift talk in plain words: what we do today; where the danger is; three steps to do it; who calls stop; and a reminder to ask if anything is unclear. It is marked as not a signed briefing.
- **safety-brief** is for technicians and needs the typed sign-off. Its knowledge base names Singapore sources by title: the WSH Council's toolbox-meeting guide and the WSH (Construction) Regulations 2007. Its rules forbid writing "briefing complete, work may start".

**Fewer errors, open to small firms.** Numbers trace to a source, gaps stay blank and verdicts are blocked. It needs no model spend, runs on a laptop and is free under MIT, and it is meant to let the scarce licensed engineer spend time judging rather than retyping [15].

**Workers' rights, explained.** The hr-labor post drafts a contract checklist, and its knowledge base names MOM and TADM pages by title (Employment Act, salary payment, TADM mediation). Its rules say it explains the law, does not predict dispute outcomes and does not invent salary bands [17].

**Ideas, not delivered.** A phone briefing where three check questions replace the signature, because a signature proves you came and a quiz proves you understood (missing: mobile interface, speech output). Photo-based stop-work, where the model says what it sees and a rule engine decides (missing: vision model, hazard rules). [TEAM TO VERIFY: a MOM or BCA source before claiming anything about workers' languages.]

**We refuse to build** AI that signs on a worker's behalf, automatic "can start work" verdicts, emotion or behaviour scoring of workers, and fully unattended pipelines. In the team's words: however smart the model, it must stop and wait for a person to nod.

## 10. Risks and mitigations

| Risk | Mitigation today | Pilot or roadmap |
|---|---|---|
| **Liability for a wrong document** | Drafts only, `submit_blocked`, licensed sign-off, blocked verdicts. Since 26 September no API or MCP caller of the deployed apps can approve with a flag | Accounts that name the approver are planned before the demo. [TEAM TO VERIFY: legal review of terms and a liability cap before any paid use] |
| **Data privacy** | Local-first; no model call without a key; the key stays on the host and is never sent to the browser, and moving the model endpoint requires the key to be entered again; the apps are closed to the network unless a token is set; one server per firm (planned) | Personal-data masking (roadmap); no claim of Singapore-only model calls. [TEAM TO VERIFY: PDPA duties for pilot data] |
| **Model errors** | No model by default; number and verdict guards | Model-mode quality is unmeasured, so the pilot measures it before any firm enables a model |
| **Fact placement at 0.229** | Stated openly; the bid posts score 1.00; gaps stay blank | Start with the bid posts and each firm's two or three most-used forms, rebuilt as plugins; re-measure and fix those writers first. [TEAM TO FILL: target] |
| **Not yet Singapore-ready** | Chinese interface and sign-off sentence; English tenders measured only on synthetic sets | [TEAM TO FILL: English interface by 10 Oct?] English readiness is the pilot's first milestone |
| **Adoption and skills** | Browser use; forms as plugins; free trial | Setup and training (option D); return measured, not promised |
| **Team continuity** | MIT licence: a pilot firm keeps a working copy | [TEAM TO FILL: who maintains it after the hackathon] |

## 11. Roadmap and milestones

| When | Milestone |
|---|---|
| 26 Sep 2026 (done) | Security baseline, pull request #61 (142 of 142 checks in CI): only the typed sentence approves, over MCP and HTTP too; once a token is set, every API request needs it, local ones included, and without one no server listens beyond the local machine unless an operator explicitly opts out; key lock; packing reads files only inside the sandbox folders |
| Before the submission (28 Sep 2026) | One Lightsail server behind TLS, set up by the deployment guide; its URL goes in the submission email. [TEAM TO VERIFY: running, and the URL is in the email] |
| By 10 Oct 2026 (demo) | Accounts and roles (admin, engineer, licensed approver) with named sign-off; a Bedrock verification run |
| [TEAM TO FILL] | English interface and sign-off sentence |
| [TEAM TO FILL: e.g. Q4 2026 – Q1 2027] | Pilot with three to five SMEs; none is confirmed yet |
| After the demo | Durable audit log, metering and budgets, admin console, single sign-on, personal-data masking, per-user sessions |
| At least 18 months after incorporation | Earliest IMDA pre-approval application |

The dated rows match the Technical Document §7, which also puts the audit log and metering after the demo.

## 12. Team

| Name | Role | Contact |
|---|---|---|
| [TEAM TO FILL] | [TEAM TO FILL] | [TEAM TO FILL] |
| [TEAM TO FILL] | [TEAM TO FILL] | [TEAM TO FILL] |
| [TEAM TO FILL] | [TEAM TO FILL] | [TEAM TO FILL] |
| [TEAM TO FILL] | [TEAM TO FILL] | [TEAM TO FILL] |

- **Contact for SBF and AWS follow-up:** [TEAM TO FILL]
- **Track:** [TEAM TO FILL: SME or Public track. For the SME track, name the SME and its authorised representative.]

## References

1. Building and Construction Authority (BCA). "Steady construction demand in 2026 as Singapore steps up support for built environment firms through collaboration and innovation." Media release, 22 January 2026. <https://www1.bca.gov.sg/resources/newsroom/steady-construction-demand-in-2026-as-singapore-steps-up-support-for-built-environment-firms-through-collaboration-and-innovation/>
2. BCA. "Listing of Registered Contractors" (open dataset on data.gov.sg, last updated 12 January 2026). Counts by Team Mintang through the data.gov.sg API on 26 September 2026 (24,014 workhead registrations; 15,864 distinct UENs). <https://data.gov.sg/datasets/d_dcda79be4aded5f9e769b8e23ff69b47/view>
3. BCA. "CRS, FM and SY registries: tendering limits." Accessed 26 Sep 2026. <https://www1.bca.gov.sg/growth-and-transformation/procurement/registration-of-built-environment-firms/tendering-limits/crs-fm-and-sy-registries-tendering-limits/>
4. Infocomm Media Development Authority (IMDA). *Singapore Digital Economy Report 2025* (released October 2025). <https://www.imda.gov.sg/-/media/imda/files/about/resources/corporate-publications/annual-report/imda-sgde-report-fy2024-2025.pdf>
5. Team Mintang. *civil-buddy: Technical Document* (NUS-ISS submission), code baseline `main` at `d3ada11`, 26 September 2026. <https://github.com/LUOaini1213/civil-buddy>
6. BCA. "Speech by Minister Chee Hong Tat at BuildSG LEAD Summit 2026." 30 April 2026. <https://www1.bca.gov.sg/resources/newsroom/speech-by-minister-chee-hong-tat--at-buildsg-lead-summit-2026/>; also published by the Ministry of National Development: <https://www.mnd.gov.sg/newsroom/parliament-matters/speeches/view/speech-by-minister-chee-hong-tat-at-buildsg-lead-summit-2026>
7. Enterprise Singapore. "EDGE Grant." Accessed 26 Sep 2026. <https://www.enterprisesg.gov.sg/financial-support/edge-grant>
8. Singapore Business Federation (SBF). *National Business Survey 2025: Singapore Budget 2025 Edition* (report; fieldwork 27 March–21 April 2025, 526 businesses, 83% SMEs). <https://www.sbf.org.sg/docs/default-source/about-us/sbf-national-business-survey-2025--singapore-budget-2025-edition-report-(final).pdf?sfvrsn=245daeac_1>
9. BCA. "Contractors Registration System (CRS)." Accessed 26 Sep 2026. <https://www1.bca.gov.sg/growth-and-transformation/procurement/registration-of-built-environment-firms/contractors-registration-system-crs/>
10. Attorney-General's Chambers, Singapore Statutes Online. Workplace Safety and Health (Risk Management) Regulations, regs 3, 5 and 7. Version current at 26 September 2026. <https://sso.agc.gov.sg/SL/WSHA2006-RG8?WholeDoc=1>
11. Attorney-General's Chambers, Singapore Statutes Online. Workplace Safety and Health (Construction) Regulations 2007, Part III (permit-to-work system, regs 10–19; high-risk construction work listed in reg 10). Version current at 26 September 2026. <https://sso.agc.gov.sg/SL/WSHA2006-S663-2007?ProvIds=P1III->
12. Ministry of Finance. "Procurement processes." Last updated 9 September 2026. <https://www.mof.gov.sg/policies/government-procurement/procurement-processes/>
13. SBF. "Business Confidence Continues to Slide with Cautious Outlook for 2026" (National Business Survey 2025, Annual Business Sentiments Edition). Press release, 27 November 2025. <https://www.sbf.org.sg/newsroom/media/press-releases/detail/business-confidence-continues-to-slide-with-cautious-outlook-for-2026>
14. Ministry of Manpower (MOM). "Construction sector: Work Permit requirements." Last updated 3 July 2026. <https://www.mom.gov.sg/passes-and-permits/work-permit-for-foreign-worker/sector-specific-rules/construction-sector-requirements>
15. BCA. "Strengthening Singapore's built environment: advancing built environment professions and improving liveability in private developments" (MND Committee of Supply 2026). 4 March 2026. <https://www1.bca.gov.sg/resources/newsroom/strengthening-singapore-s-built-environment--advancing-built-environment-professions-and-improving-liveability-in-private-developments/>
16. MOM. "Workplace Safety and Health Report 2025." Press release, 25 March 2026. <https://www.mom.gov.sg/newsroom/press-releases/2026/0325-wsh-report-2025>
17. Team Mintang. civil-buddy repository at `d3ada11` (26 September 2026), MIT licence: security baseline, pull request #61, merged 26 September 2026 (GitHub Actions: 142/142 checks passed in run 36170078042 on the pull request and again in run 36171221472 on `main`), with operator settings in `docs/deploy-minimal.md`; `docs/civil-buddy/real-tender.md`, `plugins.md`, `civil-codex-eval-2026-09-19.md`; `test/benchmarks/verdicts/cases.json` (the recorded `qwen2.5:3b` sentence); `docs/submission/haizizhi-defence-deck.json`, `创意材料-工友侧.md` (worker-side material, 31 Aug 2026); `.agents/skills/{worker-brief,safety-brief,hr-labor}/SKILL.md` and `demo/kb/`; tonnes fix `53a550e` (13 Sep 2026). <https://github.com/LUOaini1213/civil-buddy>
18. Amazon Web Services. Amazon Lightsail User Guide: "Regions and Availability Zones for Lightsail." Accessed 26 Sep 2026. <https://docs.aws.amazon.com/lightsail/latest/userguide/understanding-regions-and-availability-zones-in-amazon-lightsail.html>
19. Amazon Web Services. Amazon Bedrock User Guide: "Regional availability by endpoints" and "Regional availability by models." Accessed 26 Sep 2026. <https://docs.aws.amazon.com/bedrock/latest/userguide/endpoints-region-availability.html>; <https://docs.aws.amazon.com/bedrock/latest/userguide/models-region-compatibility.html>
20. Singapore Department of Statistics (SingStat). Table M600981, "Enterprise Landscape by SMEs and Non-SMEs, Annual." Data last updated 30 March 2026. <https://tablebuilder.singstat.gov.sg/table/TS/M600981>
21. Inland Revenue Authority of Singapore, via SingStat. Table M130551, "Taxable Companies by Economic Sector, Annual." Data last updated 22 July 2026. <https://tablebuilder.singstat.gov.sg/table/TS/M130551>
22. SingStat. Table M602281, "Number of Resident-Owned Enterprises by Sex of Owner and Industry, Annual." Data last updated 30 April 2026. <https://tablebuilder.singstat.gov.sg/table/TS/M602281>
23. GoBusiness Singapore. PSG Solutions Directory: "CSG - Novade Safety-HSE", "Hubble Safety Management System" (both Built Environment, Smart Inspection and Management - e-PTW) and "CUBICOST 5D BIM Cost Management Solution Version 3" (Glodon International). Accessed 26 Sep 2026. <https://grants.gobusiness.gov.sg/support/productivity-solutions-grant/psg-directory/csg-novade-safety-hse>; <https://grants.gobusiness.gov.sg/support/productivity-solutions-grant/psg-directory/hubble-safety-management-system>; <https://grants.gobusiness.gov.sg/support/productivity-solutions-grant/psg-directory/cubicost-5d-bim-cost-management-solution-version-3>
24. Amazon Web Services. "AWS Activate: credits." Accessed 26 Sep 2026. <https://aws.amazon.com/startups/credits>
25. IMDA. Pre-Approval ICM Vendor Guide: "Eligibility criteria." Accessed 26 Sep 2026. <https://preapproval-guide.imda.gov.sg/pre-approval-guide/eligibility-criteria>
26. Enterprise Singapore. "Productivity Solutions Grant." Accessed 26 Sep 2026. <https://www.enterprisesg.gov.sg/financial-support/productivity-solutions-grant>
27. Enterprise Singapore. "EDGE Grant" FAQs. Accessed 26 Sep 2026. <https://www.enterprisesg.gov.sg/resources/all-faqs/edge-grant>
28. BCA. Circular, "Productivity Solutions Grant (PSG) for Built Environment" (tranche 1 April 2026 – 31 March 2031). 1 April 2026. <https://isomer-user-content.by.gov.sg/338/40140aed-8bdf-404c-8bb2-d894e1c5a83e/2026_Circular_Promotion%20of%20Productivity%20Solutions%20Grant%20Tranche%203%20(PSG).pdf>
29. Vendor websites, no publication date, accessed 26 Sep 2026: Procore <https://www.procore.com/en-sg>; Autodesk <https://construction.autodesk.com/>; Hubble <https://hubble.build/>; Novade <https://www.novade.net/construction-project-management-software-singapore/>; EasyCargo <https://www.easycargo3d.com/en/>; Cargo-Planner <https://www.cargo-planner.com/>.
30. Lucius AI. "GeBIZ Singapore government tenders guide" (vendor blog). 30 July 2026, updated 23 September 2026. <https://ailucius.com/blog/gebiz-singapore-government-tenders-guide>
