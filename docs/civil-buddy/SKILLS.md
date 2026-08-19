# Skills

两套「skill」不是一种东西。MCP 是第三种。

| 名称 | 路径 | 给谁 | 不是 |
|------|------|------|------|
| Grok 土木 skill | `skills/civil-buddy/` | `/civil-buddy` 起草 SOP | 不是 66 岗一次加载；V1 路由 6 个 id，**construction 写满** |
| 装箱引擎 skill | `docs/skills/README.md` + `packing_assistant/skills_registry.py` | 成箱/拼柜节点契约 | 不是 Grok `/skill`；**不要**把 `bin3d.pack` 做成让模型改坐标的 MCP |
| MCP | `demo/mcp_stdio.py` · `civil-mcp` | Host `tools/list` | 不是 SOP |

工作台 **66 岗** 走 `demo/` / `workbench/`。不要把 66 份人格写进 `SKILL.md`。

## Grok skill 树

```
skills/civil-buddy/
  SKILL.md
  references/hard-rules.md · jurisdictions.md · citation-format.md · scheme-outline.md
  references/experts/{construction,cost,municipal,structural-geotech,supervision,traffic}.md
  scripts/scan_forbidden_inventions.py · fill_scheme_template.py
```

离线可完成 construction 十一章草稿。KB / 装箱数字走 MCP，不写进 skill 正文。

## 装箱 skill ↔ MCP

| 引擎 Skill ID | MCP |
|---------------|-----|
| `material.parse` `structure.calc` `bin3d.pack` `booking.volume` | **无**。坐标/N0 只在引擎内。禁止暴露成模型可改 MCP |
| `hitl.confirm` `vgm.draft` | 无代签 MCP |
| （岗）pack-ship 投影 | `pack-ship__list` / `plan` / `export` / `health` |

完整契约表仍见 [docs/skills/README.md](../skills/README.md)。
