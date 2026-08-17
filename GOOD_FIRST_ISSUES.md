# Good first issues (Civil Buddy)

Open these on GitHub when ready; kept here so the portfolio shows **maintenance intent**.

## GFI-1 · Docs: link a new tool to the decision table

- Add one row to `docs/harness-design.md` when a new tool is introduced.
- Acceptance: PR updates design table + registry docstring.

## GFI-2 · Eval: one more tiny case in `eval/`

- Add a minimal materials fixture and assert in `eval_harness` or workteams tiny path.
- Acceptance: `python scripts/demo_one_shot.py` still exits 0.

## GFI-3 · Trace: print step count summary at end of smoke

- In smoke path, print `n_steps` / illegal tool count if available.
- Acceptance: no API key required; CI-friendly.

## GFI-4 · HITL: document default auto_confirm for demos vs product

- Clarify in `docs/hitl-checkpoint.md` when auto confirm is allowed.
- Acceptance: contributor cannot confuse demo flags with production defaults.

## Community checklist (maintainer)

- [ ] Issues labeled `good first issue` / `docs` / `eval`
- [ ] PR template: what / why / how tested
- [ ] Smoke `python scripts/demo_one_shot.py` green before release tags
- [ ] No secrets in repo; domain samples only under `data/samples/`

External PRs to other Agent repos (optional): record URL in personal notes when done.
