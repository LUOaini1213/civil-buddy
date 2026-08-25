# Skills

Civil Buddy **就是**土木版 Codex：本产品当 Host，66 岗是它的 skill 包。不是把专家导出给 OpenAI Codex 用。

四套「skill」不要混：

| 名称 | 路径 | 给谁 | 不是 |
|------|------|------|------|
| **产品 skill（土木版 Codex）** | `.agents/skills/<id>/SKILL.md`（镜像 `.codex/skills/`） | Civil Buddy 自己的 agent：catalog → 选用 → 加载全文 | 不是用户画像；不是给 OpenAI Codex CLI 当插件目录 |
| Grok 土木 skill | `skills/civil-buddy/` | `/civil-buddy` 起草总控 SOP | 不是 66 份人格；路由后读对应 Codex skill |
| 装箱引擎 skill | `docs/skills/README.md` + `packing_assistant/skills_registry.py` | 成箱/拼柜节点契约 | 不是 Grok `/skill`；**不要**把 `bin3d.pack` 做成让模型改坐标的 MCP |
| MCP | `demo/mcp_stdio.py` · `civil-mcp` | Host `tools/list` | 不是 SOP |

工作台 **66 岗 = 66 个 Codex skill**。路由器是 `.agents/skills/civil-buddy/SKILL.md`。不要把 66 份人格写进一份 `SKILL.md`。

格式（[Agent Skills](https://agentskills.io/specification) / Codex）：

```
---
name: <expert-id>
description: <何时上场，单行，≤500 字>
---
何时上场 / 必问输入 / 交付骨架 / 独有工具 / 硬规则
```

生成：`python scripts/build_codex_expert_skills.py`（源是 `demo/catalog_seed.py` + `workbench/yibiao-map.json`）。  
冒烟：`python scripts/test_codex_expert_skills.py`。

召唤某岗时，Runtime 只把该岗 `SKILL.md` 正文装进工作记忆（`prompt_suffix`），这是程序记忆，不是长期用户记忆。

## Codex skill 树

```
.agents/skills/
  civil-buddy/SKILL.md          # 路由器，不要一次加载 66 岗
  construction/SKILL.md
  bid-parse/SKILL.md
  pack-ship/SKILL.md
  …（共 66 岗）
.codex/skills/                  # 同内容，旧版 Codex 仓库扫描路径
```

知识库仍在 `demo/kb/<category>/<id>/`。Skill 正文只点名要读的文件，不把 FAQ/规范全文抄进去。

## Grok skill 树

```
skills/civil-buddy/
  SKILL.md
  references/hard-rules.md · jurisdictions.md · citation-format.md · scheme-outline.md
  references/experts/{construction,cost,municipal,structural-geotech,supervision,traffic}.md
  scripts/scan_forbidden_inventions.py · fill_scheme_template.py
```

Grok `/civil-buddy` 选岗之后读 `.agents/skills/<id>/SKILL.md`。离线仍可完成 construction 十一章草稿。KB / 装箱数字走 MCP，不写进 skill 正文。

## 装箱 skill ↔ MCP

| 引擎 Skill ID | MCP |
|---------------|-----|
| `material.parse` `structure.calc` `bin3d.pack` `booking.volume` | **无**。坐标/N0 只在引擎内。禁止暴露成模型可改 MCP |
| `hitl.confirm` `vgm.draft` | 无代签 MCP |
| （岗）pack-ship 投影 | `pack-ship__list` / `plan` / `export` / `health` |

完整契约表仍见 [docs/skills/README.md](../skills/README.md)。
