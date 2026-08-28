# Civil Buddy · Agent notes

- **This product is 土木版 Codex.** Host = Civil Buddy. Skills = 66 experts. Not an export pack for OpenAI Codex CLI.
- **Experts are skills.** One `SKILL.md` per post: `.agents/skills/<id>/SKILL.md`. Router: `.agents/skills/civil-buddy/SKILL.md`. Catalog (name+description) first; load full SOP only after `$id` or implicit match. Do not load all 66 into one prompt.
- CLI: `python -m packing_assistant.civil` (TUI) · `civil exec` · `civil app` · `civil mcp --pack construction` · `civil serve` (JSON-RPC on this harness, not openai/codex)
- Slash: `/skills` `/new` `/bg` `/threads` `/sandbox` `/approvals` `/confirm`
- Sandbox `read-only|workspace-write`. Approval `untrusted|on-request|never`. No danger-full-access (secrets/spawn stay denied).
- **Procedural memory ≠ user memory.** Skills are SOP. Session slots (`jurisdiction` / `project` / `P0`) live in `session.summary.json`. Do not invent a user profile.
- **Tools compute; the model routes.** No hand-written xyz, N0, cabinet counts, clause numbers, or composite unit prices. Unconnected solver fields stay the literal `UNSPECIFIED`. `can_fit=false` is a failure.
- **High-risk write gate:** user must type `我明白，将由持证人员签认`. Chat/questions do not write.
- **Bids:** `submit_blocked=true`. Never assert 可以投标 / 可以开工.
- Regenerate skills: `python scripts/build_codex_expert_skills.py`
