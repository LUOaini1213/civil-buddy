# Contributing to Civil Buddy

Thanks for interest in **Civil Buddy** (土木工作台 + packing engine).

## Ground rules

1. **Tools compute; models route.** Do not add paths where the LLM invents coordinates, counts, or weights.
2. Prefer **`agent_mode=steps`** for production behavior; treat `llm_toolcall` as experimental / shadow.
3. Every behavior change should be **observable** (trace step or artifact) and, when possible, **tested** (`scripts/smoke_agent_product.py` or a tiny eval).
4. No secrets, customer raw dumps, or API keys in the repo. Use `.env` locally (see `.env.example`).

## Dev setup

```bash
git clone https://github.com/LUOaini1213/packing-agent.git
cd packing-agent
# 产品名 Civil Buddy；GitHub 仓名可改为 civil-buddy
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate   # Unix
pip install -r requirements.txt
```

## One-shot demo (must pass before PR)

```bash
python scripts/demo_one_shot.py
# equivalent core:
python scripts/smoke_agent_product.py
```

Optional:

```bash
python scripts/demo_one_shot.py --closed-loop
python scripts/eval_workteams_cli.py --tiny-only
uvicorn gateway.app:app --reload --host 127.0.0.1 --port 8000
```

## Branch & PR

1. Fork / branch from `main`.
2. Keep PRs focused (one harness concern per PR when possible).
3. Fill the PR template: **what / why / how tested**.
4. Link related issues.

Suggested labels: `runtime`, `tools`, `eval`, `trace`, `docs`, `gateway`.

## Issue types

Use GitHub templates:

| Template | Use when |
|----------|----------|
| Bug report | Broken pipeline, illegal tools, crash |
| Feature request | New tool, gate, KPI |
| Harness design | Architecture / first-principles discussion |
| Phase1 / Phase2 | Legacy domain task splits (cartonize vs containerize) |

## Code map (short)

| Path | Role |
|------|------|
| `packing_assistant/harness.py` | Runtime facade |
| `packing_assistant/teams/` | Orchestrator + subagents |
| `packing_assistant/tools/` | Deterministic tools |
| `packing_assistant/tool_registry.py` | Whitelist |
| `docs/harness-design.md` | Design decisions (tool/HITL/eval) — interview sheet |
| `docs/architecture-as-harness.md` | Harness vocabulary map |
| `docs/ARCHITECTURE.md` | Domain architecture |
| `GOOD_FIRST_ISSUES.md` | Starter tasks for contributors |

## License / scope

Portfolio + research prototype. Not a warranty of production packing accuracy.  
By contributing you agree your patches may be redistributed with the project.
