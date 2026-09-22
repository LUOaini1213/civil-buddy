# NUS-ISS "Show Me Your Agents" 2026 — Civil Buddy entry notes

> 中文说明：本文是 NUS-ISS 赛道的对照表，与海之子杯材料（同目录 `haizizhi-*.md`）并列；两赛口径互不通用，资格条款见 [knowledge_base/06_competition/constraints-nus-iss.md](../../knowledge_base/06_competition/constraints-nus-iss.md)。提案 **2026-09-28** 提交，现场演示 2026-10-10。本文只写仓库里能复跑验证的事实（截至 main `71c841e`，2026-09-13）；业务叙事、SME 对象与团队信息留给队员填。
>
> Every number below is produced by a command in this repository, with no API key and no network. Nothing here is a judging outcome.

## What it is

Civil Buddy is an agent workbench for civil-engineering and construction SMEs: 66 job posts in 16 categories, each an SOP the model drafts against. Hard numbers — container counts, coordinates, unit prices — come only from deterministic tools; the model routes and drafts. High-risk actions (qualification verdicts, bids, writes to disk) stop at a human confirmation. One post, container packing (`pack-ship`), has a real engine behind it; the other 65 are drafting posts graded honestly in [docs/depth-ladder.md](../depth-ladder.md). MIT licence.

## What a judge can verify

| Capability | What happens | Command (repo root, no key) |
|---|---|---|
| 66 posts draft offline | Every post has a knowledge base, FAQ, required fields and gap list; drafts are produced with no model key, missing data stays `[A001]` / `UNSPECIFIED` | `python scripts/test_kb_k4_depth.py` → 66/66 |
| One-shot product demo | Routing, tool whitelist, HITL pause, trace on disk, shadow evaluation | `python scripts/demo_one_shot.py --all` → ALL_PASS |
| Packing engine with a human gate | Boxes → **confirm** → containers → 3D / centre of gravity / risk verdict; a structurally bad input is rejected, not packed | `python main.py --demo` · `python main.py --demo --preset structure_fail` → REJECT |
| A supplier's packing list in, a plan out | Real export headers (`Description of Goods`, `L x W x H`, `L (mm)`, N.W./G.W.), tonnes read as tonnes; a row with no weight or no dimensions stops the run and names the row, and a solve that packs nothing is an error, not a plan | `python scripts/test_table_mapper_unit.py` → ALL_PASS · `python scripts/test_pack_ship_dimension_gate.py` |
| PDF packing lists | `.pdf` reaches the parser on `pypdf` (BSD); an unrecognised layout returns an actionable reason instead of an empty plan | `python scripts/test_packing_list_pdf.py` |
| MCP tools that run the engine | `pack-ship__ingest / plan / vgm / booking_draft / export / list / health` over JSON-RPC 2.0 stdio; the VGM stops at `needs_shipper_signature`, the booking at `dry_run`; nothing is sent. The sample file is the long-frame list: 9 boxes, `can_fit` true, pieces 9→9 and 23800 kg conserved, 3×40HQ, `n0` 2, utilization 0.1934 | `python scripts/test_pack_ship_crates_structure.py` · `python scripts/test_pack_ship_solver_mcp.py` (same file; the script prints the solver fields, it does not freeze an older 7-container line) |
| Mount it in an agent host | The same server, scoped per post or category, for OpenClaw / Cursor / VS Code hosts | `python demo/mcp_stdio.py --expert pack-ship` (configs in `ide/`) |
| Agent middleware, asserted | Policy engine (deny with a reason), recovery chain (retry → `UNSPECIFIED` → audit), cost fuse | `python scripts/demo_agent_middleware.py` · `python scripts/test_agent_middleware.py` |
| Stop, resume, export | Cancelling a turn closes the live model socket (verified on Windows and Linux); traces export atomically; a task can be backed up and re-imported as a ZIP | `npm run check` (57 checks, ~6 min) |
| Evaluation, stated honestly | 128 automated packing runs (16 lanes × 8 rounds) all completed; **71 of 128 produced a plan that fits**, 57 came back `can_fit=False` for a human to revise; CI checks these figures against the archive | `python scripts/render_eval_table.py` |
| Tender vs. bid response, measured | One row per tender line; a stated number that does not meet the tender's (工期 60 vs 999 日历天) is flagged for review, never judged. Offline `--check` on 19 cases: link precision 1.000, link recall 0.980, conflict precision 1.000, conflict recall 1.000 (14/14). An older 14-case run (recall 0.974, 9/9) is not the current score | `python scripts/eval_tender_response_match.py --check` |
| CI | Three jobs (Python smoke, Rust workbench, packing-eval slice) green on `main` since #24–#26 (2026-09-13) | [Actions](https://github.com/LUOaini1213/civil-buddy/actions) |

## Against the award axes

**SME readiness**

- Runs on one machine with no cloud dependency; the deterministic paths need no model key at all, and a key for any OpenAI-compatible Chat Completions endpoint is entered in the UI and kept in memory only (never written to disk, never committed — `npm run check` includes a tracked-secrets scan).
- Every output is an internal working draft, never a signed document; the tool refuses to say "可以投标 / 可以开工", and `submit_blocked` stays `true` on bid deliverables until a licensed person confirms.
- Data honesty is enforced by tests, not by prompt: a table that cannot be read says so instead of showing demo numbers; a row with no weight stops the plan; unconnected fields are the literal `UNSPECIFIED`.
- Not yet in the repo: a named SME pilot and its data. The one real shipment case quoted elsewhere (446 t, 29 → 25 containers) is customer data kept out of the repository and is **not** reproducible from it.

**Best use of agents**

- Natural language → intent → whitelisted tools → human confirmation → evaluation, with `agent_mode=steps` as the production path and the LLM tool-calling path run only as a shadow arm whose agreement with the steps arm is checked in CI.
- Two runtime layers rather than prompt rules: a policy engine that decides who may call which tool at what cost, and a failure-recovery chain that degrades to `UNSPECIFIED` and leaves an audit trail.
- The engine is exposed as MCP tools so an external agent host can use it without re-implementing packing; the tools report `container_mix_supported: false` because the engine packs N containers of one type — a limit, stated.

**Social impact**

- The worker-facing angle is written up in [创意材料-工友侧.md](创意材料-工友侧.md): pre-shift safety briefings with the blanks the foreman must fill, stop-work judgement kept with people, and an explicit list of what the team refuses to build (AI signing on a worker's behalf, emotion or behaviour scoring, fully unattended pipelines).
- Every HITL gate is a place kept for a person; the product's rule is "tools compute numbers; the model only routes".

## Running it on AWS

- The packing gateway and UI ship as a Docker image (`Dockerfile`, `docker-compose.yml`): binds `$PORT`, health check at `/api/health`, output on a volume. It runs on any container host including a Lightsail container service or instance; that deployment has not been exercised yet and is a build-phase task.
- The workbench (`demo/`, port 8765) talks to the engine over HTTP (`PACKING_AGENT_URL`) or in-process (`PACKING_AGENT_ROOT`).
- Model access: any OpenAI-compatible Chat Completions base URL plus key, set at runtime in "设置 → 模型设置". OpenRouter (permitted by the organisers) works as-is. Amazon Bedrock exposes an OpenAI-compatible Chat Completions endpoint (`https://bedrock-mantle.<region>.api.aws/v1` or `https://bedrock-runtime.<region>.amazonaws.com/openai/v1`, `Authorization: Bearer <Bedrock API key>`), so the same setting takes a Bedrock key; AWS's model-compatibility table lists `openai.gpt-oss-*`, DeepSeek V3.x, Gemma 3, Mistral 3 and others under Chat Completions, and not the Claude, Nova or Llama families, which use other APIs. Streaming is documented on the bedrock-mantle endpoint. Neither has been exercised from this repository yet.

## Boundaries we will not cross in the proposal

No signed or statutory documents; no automatic "can bid / can start work" verdicts; no promised win rates; no container-type mixes; no invented coordinates, clause numbers or unit prices. Regulation text is not stored in the repository.

## Timeline and open items

| Date | Milestone |
|---|---|
| 2026-09-07 → 09-25 | Build phase |
| **2026-09-28** | Proposal submission |
| 2026-10-10 | Demo day |
| 2026-10-19 | Awards |

To be written by the team before 09-28: the SME problem statement and the pilot partner; which posts the demo walks through on 10-10; the Lightsail deployment record; team member list (Team Mintang, four members).
