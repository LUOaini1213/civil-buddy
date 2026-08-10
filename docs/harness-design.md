# Harness design decisions (interview sheet)

**Audience:** Agent Infra / Harness roles (e.g. MiMo Agent).  
**Thesis:** packing-agent is a **Development Harness** with a packing domain skin—not a “how many containers we saved” business demo.

Related: [architecture-as-harness.md](./architecture-as-harness.md) · [agents-vs-tools.md](./agents-vs-tools.md) · [hitl-checkpoint.md](./hitl-checkpoint.md)

---

## 1. What problem the Harness solves

| Without Harness | With this Harness |
|-----------------|-------------------|
| Free-form LLM “solves” packing | **Tools** own numbers; model only routes |
| Unbounded multi-step chaos | **Runtime** owns who runs, when, and stop |
| Silent failures | **Trace + artifacts** make every step observable |
| Demo-only confidence | **Eval** compares `steps` vs `llm_toolcall` |

Primary framing is **reliability, boundaries, and measurability**—not packing KPIs.

---

## 2. Design decision table

| Decision | Choice | Why | If reversed |
|----------|--------|-----|-------------|
| **Tool boundary** | Whitelist `tool_registry`; geometry/counts **only** from tools | Reproducible, auditable, testable | Model invents xyz / N0 → un-gateable errors |
| **Orchestration** | Big Team supervisor ⊃ Subagent Team A / B | Bounded context; clear ownership | Monolithic agent blows context and mixes concerns |
| **Default mode** | `agent_mode=steps` (deterministic professional nodes) | Production-like path without API key | Pure free tool-call is experimental only |
| **LLM role** | Scheduler / explainer on optional paths | Model smarts for routing, not arithmetic | LLM-as-calculator fails under distribution shift |
| **HITL** | Explicit confirm gate between A and B (auto only for demos) | High-cost steps need human stop | Fully auto ships irreversible mistakes |
| **Replan** | Bounded critic / replan caps | Prevent infinite loops | Open-ended retry burns tokens and time |
| **Memory** | Structured session + run artifacts + skills/KB | Plans are data, not chat sludge | Unbounded chat memory loses contracts |
| **Eval** | Shadow: same ticket on `steps` vs `llm`; illegal-tool KPI | Harness quality is measured | “It worked once” is not a product |
| **Trace** | Ordered `agent_steps` / events / `output/runs/` | Demo, debug, regression | Black-box runs cannot iterate |

---

## 3. Layer checklist (walkthrough script · ~3 min)

1. **Runtime** — Who schedules Subagents? Where is the stop condition?  
2. **Tools** — Name one tool that must never be “LLM free text.”  
3. **HITL** — Which step requires human confirm and why?  
4. **Eval** — How do you detect illegal tools or steps/llm disagreement?  
5. **Trace** — Where do you look after a failed run?

Do **not** lead with carton utilization percentages in Agent Infra interviews.

---

## 4. Honest boundary vs Agent Infra

| This repo has | This repo does **not** claim |
|---------------|------------------------------|
| Application-layer Harness / Runtime facade | Production LLM inference engine |
| Tool loop, gates, traces, shadow eval | Prefix/KV cache kernel, PD separation clusters |
| Open-source maintainable prototype | Training co-evolution with foundation models |

Inference literacy (Prefill/Decode, KV cache, batching) is complementary—see  
`求职/12_Agent_四周补强/notes/llm-inference-for-agents.md`.

---

## 5. Offline check (must pass)

```bash
cd packing-agent
python scripts/demo_one_shot.py
# optional:
python scripts/demo_one_shot.py --all
```

Exit code `0` and `OK` lines = harness smoke path healthy.

---

## 6. Good first contributions (community-facing)

See root [CONTRIBUTING.md](../CONTRIBUTING.md) and [GOOD_FIRST_ISSUES.md](../GOOD_FIRST_ISSUES.md).
