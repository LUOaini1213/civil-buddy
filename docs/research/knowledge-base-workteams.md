# 知识库 Workteams 评估与接线（Harness ≥0.6.3）

## 结构

```text
knowledge_base/
  01_rules/          # 硬规则（最高优先）
  02_tools/          # 工具说明书（对齐 TOOL_CATALOG）
  03_trajectories/   # T1–T8 ReAct 范例
  04_strategies/     # 启发式（低于 rules）
  05_multi_agent/    # 大Team⊃A/B + agent_kb_bindings.yaml
  06_competition/    # 评分与任务镜像
  07_domain_knowledge/
  INDEX.yaml
```

与 `knowledge/packing_knowledge_base.json`（数值箱库）分工：md 管规则与范例，JSON 管可执行规格。

## 运行时

| 能力 | 模块 |
|------|------|
| 关键词检索 | `packing_assistant.tools.search_knowledge` |
| 工具 ID | `knowledge.search`（tool_registry） |
| 按 Agent 窄接 | `packing_assistant.kb_bindings` + YAML |
| 裁决横幅 | `packing_assistant.verdict` |

## 分卡

`python scripts/eval_knowledge_base_scorecard.py`  
目标：七维 ≥9.5，综合 ≥9.5（结构 + Recall@3 + 轨迹完整度 + 工具覆盖）。

## 叙事

- 坐标 / 柜数由 **tools** 计算  
- loader 默认 **不检索** KB  
- replan_critic / finalize 可挂 `kb_evidence` 解释  
