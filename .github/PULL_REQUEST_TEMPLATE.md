## Summary

<!-- What & why (1–3 bullets) -->

## Harness layer

- [ ] Runtime
- [ ] Tools
- [ ] Memory / session
- [ ] Eval / KPI
- [ ] Trace
- [ ] Docs / demo DX
- [ ] Domain phase1 / phase2

## Boundary

- [ ] LLM still **cannot** invent xyz / free container counts / raw weights
- [ ] Tools remain the source of numerics

## Test plan

```bash
python scripts/demo_one_shot.py
# add more if needed:
# python scripts/demo_one_shot.py --all
```

## Contracts

- [ ] No change to `boxes[]` / public API contracts
- [ ] API / schema changed (describe + update docs)

## Checklist

- [ ] No secrets / `.env` / customer dumps
- [ ] Docs updated if behavior changed (`README` / `architecture-as-harness.md`)
