# Expert skills (Codex / Agent Skills)

Each workbench expert is a skill:

- `.agents/skills/<id>/SKILL.md` — current Codex scan path
- `.codex/skills/<id>/SKILL.md` — same files, older repo-scoped path

Regenerate:

```
python scripts/build_codex_expert_skills.py
```

Do not put 66 personalities into `skills/civil-buddy/SKILL.md`. That file is the Grok `/civil-buddy` SOP router.
