# Skills 文档（v0.5 · 非 MCP 完整实现）

本仓库采用 **确定性 tools + 多智能体编排**，而非通用 MCP skill 市场。  
下列「skill」是可复用能力包：输入/输出契约固定，供 Agent 节点调用。

| Skill ID | 职责 | 入口模块 | 主要 Agent |
|----------|------|----------|------------|
| `material.parse` | 文本/表 → 标准 materials[] | `agents/material_parser.py` | material_parser |
| `structure.calc` | 成箱结构半严格校核 + 详设事实 | `tools/structure_calc.py`, `tools/design_facts.py` | structure, box_scheme |
| `packing.standard_boxes` | 标准箱库合箱 / 混装 | `tools/packing.py`, `agents/box_scheme.py` | box_scheme |
| `booking.volume` | N0 / V_eff / 双利用率 | `tools/booking.py`, `tools/volume_estimate.py` | planner |
| `bin3d.pack` | 3D 摆位（laff / skjolber） | `tools/bin3d.py`, `skjolber_client.py` | loader |
| `evaluate.plan` | 自适应权重评估 | `agents/evaluator.py` | evaluator |
| `risk.cog` | 重心偏心 + 合规 | `tools/cog.py`, `agents/risk_compliance.py` | risk_compliance |
| `visualize.layout` | 三视图 + scene3d + COG | `agents/visualizer.py` | visualizer |
| `hitl.confirm` | 用户确认闸门摘要 + 策略门 | `hitl_summary.py`, `hitl_gates.py` | present_team_a |
| `replan.critic` | 有界 replan（只改 packing_options） | `agents/replan_critic.py` | harness replan 环 |
| `vgm.draft` | VGM Method2 草稿（须人签） | `tools/vgm_draft.py` | finalize |
| `nl.revise` | 自然语言改方案 | `tools/nl_revision.py` | API `/api/revise-nl` |
| `trace.stream` | SSE + trace.jsonl | `trace_events.py`, `iter_agent_pipeline` | harness |

注册与 fail-loud：`packing_assistant/skills_registry.py` · 冒烟 `python scripts/test_agent_p0_eight.py`

## 约定

1. **数值不靠 LLM 编造**：装柜/结构/评估均由代码计算。  
2. **LLM 可选**：仅材料解析增强、文案润色。  
3. **扩展方式**：新增 `tools/xxx.py` + 在对应 agent 中调用；在本表登记；不必上完整 MCP。  
4. **观测**：每次 pipeline 写 `output/runs/<run_id>/trace.jsonl`。

## 示例：调用契约（booking.volume）

```text
in:  boxes[], container_type, packing_options
out: n0, booking_volume_utilization, outer_space_utilization, binding_constraint
```

## 示例：trace 事件

```json
{"type":"agent_start","node":"loader","title":"装载(3D)"}
{"type":"agent_end","node":"loader","duration_ms":42,"step":{"can_fit":true}}
{"type":"done","summary":{"n_steps":12}}
```
