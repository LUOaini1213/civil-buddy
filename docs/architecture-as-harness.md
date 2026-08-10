# Architecture as Harness

This document maps **packing-agent** onto an **Agent Harness** vocabulary  
(Runtime · Tools · Memory · Eval · Trace), for readers coming from Agent Infra / MiMo-style roles.

> Domain skin: container packing.  
> **Product thesis is harness-shaped:** the model proposes and routes; **tools own numbers**;  
> the runtime owns gates, traces, and evaluation.

Related: [ARCHITECTURE.md](./ARCHITECTURE.md) · version badge in root `README.md`.

---

## 1. One-line definition

**Harness** = the execution environment that turns an LLM (or a fixed policy) into a **reliable multi-step agent**:

| Layer | Job |
|-------|-----|
| **Runtime** | Who runs when; subagents; HITL; stop conditions |
| **Tools** | Whitelisted, deterministic capabilities |
| **Memory** | Session / artifact / knowledge boundaries |
| **Eval** | Shadow runs, KPIs, illegal-tool checks |
| **Trace** | Ordered events for debug, demo, regression |

packing-agent implements these layers for a packing workflow (cartonize → containerize → risk → optional booking).

---

## 2. Layer map

### 2.1 Runtime

| Concept | Implementation |
|---------|----------------|
| Orchestrator | Big Team (`teams/big_team.py`) |
| Subagents | Team A (cartonize) · Team B (containerize / CoG / risk) |
| Entry facade | `packing_assistant/harness.py` → `run_agent_pipeline` / `iter_agent_pipeline` |
| Modes | `steps` (default) · `llm_toolcall` · `auto` · `graph` (LangGraph) |
| Human gate | HITL confirm between A and B (`enable_auto_confirm` for demos) |
| Bounded loops | Critic / replan caps; outer ship-risk loops |
| HTTP runtime | FastAPI `gateway/` + SSE stream |

**First principle:** default production path is **`steps`** (deterministic professional nodes).  
LLM tool-call is an **experimental / shadow** scheduler, not the source of geometry.

### 2.2 Tools

| Concept | Implementation |
|---------|----------------|
| Registry | `tool_registry.py` — clusters big / A / B |
| Contract | Tools return structured results; **no free-form xyz from the model** |
| Intent | `IntentSpec` — NL → constraints / options before tools fire |
| Fail-soft | No API key → policy fallback on LLM path |

**First principle:** **tools compute; the model (if any) only routes.**  
Illegal tool calls are KPI failures, not “creative freedom.”

### 2.3 Memory (scoped, not magical)

| Kind | What we store | Where |
|------|----------------|-------|
| Session | Pipeline state, confirmations | `session_store` / disk sessions |
| Artifacts | Plans, risk reports, run folders | `output/runs/` · `run_artifacts` |
| Knowledge / skills | Domain rules, tables | `knowledge/` · skill docs |
| Checkpoint | Graph resume | LangGraph checkpoint (`lg_checkpoint`) |

We deliberately **do not** pretend unbounded chat memory is the plan.  
Plans live in **structured state + artifacts**.

### 2.4 Eval

| Mechanism | Role |
|-----------|------|
| `eval_workteams` | Same ticket: `steps` vs `llm_toolcall` shadow |
| `workteam_kpi` | Coverage, illegal tools, replan routes, result agreement |
| CLI | `scripts/eval_workteams_cli.py --tiny-only` |
| Targets | e.g. `agree_core_rate ≥ 0.90`, `illegal_tool_calls == 0` |

**First principle:** harness quality is **measured**, not claimed.  
Model upgrades must not silently break tool discipline.

### 2.5 Trace

| Mechanism | Role |
|-----------|------|
| `agent_steps` / events | Ordered step log on state |
| `trace_events` | Normalized event schema |
| JSON / JSONL dumps | Demo & judge packages |
| SSE | Live UI observation |

Traces are the bridge between **research feedback** and **product iteration**.

---

## 3. Control flow (harness view)

```text
User NL (+ materials)
    │
    ▼
┌────────────────── Runtime ──────────────────┐
│  IntentSpec                                   │
│       │                                       │
│       ▼                                       │
│  Scheduler: steps | llm_toolcall | auto       │
│       │                                       │
│       ├─► Subagent A ──► Tools (cartonize)    │
│       │         │                             │
│       │         ▼                             │
│       │      HITL gate                        │
│       │         │                             │
│       ├─► Subagent B ──► Tools (load/CoG/…) │
│       │         │                             │
│       └─► Finalize / optional TMS             │
└───────────┬───────────────┬───────────────────┘
            │               │
            ▼               ▼
         Trace log       Artifacts
            │
            ▼
     Eval / shadow KPI (optional CI)
```

---

## 4. Why this is not “just a packing app”

| Packing app | This harness |
|-------------|--------------|
| Hard-coded scripts | Pluggable **agent_mode** + tool registry |
| LLM writes coordinates | **Forbidden** — tools own numerics |
| Success = “looks OK” | Success = **KPI + illegal-tool = 0** |
| Opaque runs | **Trace + artifacts** every demo |
| Single agent blob | **Subagents + orchestrator + HITL** |

The domain is packing; the **object of design** is the harness.

---

## 5. Open questions (honest research surface)

Useful discussion topics (issues welcome):

1. How far can `steps` go before LLM scheduling is necessary?
2. What belongs in session memory vs skill/knowledge vs pure tools?
3. Best metrics for **model–harness co-evolution** (beyond agree_core_rate)?
4. Sandbox / permission model for tools beyond a whitelist?

---

## 6. Code index

| Harness idea | Code |
|--------------|------|
| Runtime facade | `packing_assistant/harness.py` |
| Big / A / B teams | `packing_assistant/teams/` |
| Tool registry | `packing_assistant/tool_registry.py` |
| Intent | `packing_assistant/intent_spec.py` |
| LLM loop | `packing_assistant/agent_loop.py` |
| Eval | `packing_assistant/eval_workteams.py`, `workteam_kpi.py` |
| Trace | `packing_assistant/trace_events.py`, `run_artifacts.py` |
| Gateway | `gateway/app.py` |
