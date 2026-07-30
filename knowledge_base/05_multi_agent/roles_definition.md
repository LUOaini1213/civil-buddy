---
category: multi_agent
subcategory: roles
priority: high
type: protocol
tags: [big_team, team_a, team_b, I/O, illegal]
source: internal
updated: "2026-07-30"
harness: ">=0.6.3"
status: active
---
# 角色定义（绑定 Harness ≥0.6.3）

架构文档：`docs/ARCHITECTURE.md`。代码：`packing_assistant/teams/*`、`tool_registry.py`。

## 大 Team（Supervisor）

| 项 | 内容 |
|----|------|
| **职责** | Intent、编排、HITL 闸、有界 critic、finalize、KPI/TMS |
| **输入** | NL / materials / IntentSpec / session_id |
| **输出** | 决策摘要、HITL 状态、最终 ship 包引用（非全量 layout） |
| **可调工具** | intent.interpret, hitl.confirm, replan.critic, knowledge.search, tms.booking, kpi.extract, export.shipment, plan.diff |
| **禁止** | 直接写 3D xyz；拍脑袋改柜数绕过 tools；把 B 的全量 layout 灌进上下文 |

## 小 Team A（成箱）

| 项 | 内容 |
|----|------|
| **职责** | 材料解析 → 结构 → 成箱 → 展示 |
| **输入** | materials_rows / packing_options |
| **输出** | boxes、standard_box_hit_rate、structure 结论、摘要 JSON |
| **可调工具** | material.parse, structure.calc, box.scheme, cargo.feasibility, design.facts, packing 族 |
| **禁止** | 编造尺寸重量；结构不通过仍标可装；LLM 手写箱坐标 |

## 小 Team B（拼柜）

| 项 | 内容 |
|----|------|
| **职责** | N0 规划 → 3D 装载 → 评估 → 风险 → 可视化 |
| **输入** | boxes、container 约束、max_containers |
| **输出** | can_fit、containers_used、N0、booking/outer 利用率、风险结论 |
| **可调工具** | container.select, bin3d/plan_load, evaluator, risk, cog 族, visualize, vgm_draft |
| **禁止** | 突破已锁定柜预算（除非 Intent 改预算）；忽略 feasibility |

## replan_critic

| 项 | 内容 |
|----|------|
| **职责** | 只改 packing_options / 柜数上限策略 / 路由 |
| **可改** | route∈{box_scheme, dense, multi_start, stop}；max_box_net_kg；有界 max_containers |
| **禁止** | 写 xyz；无限 replan；超货载时只加柜空转 |

## 默认调度

- `agent_mode=steps`：确定性流水线（默认比赛路径）
- `llm_toolcall`：可调 `knowledge.search` 与工具面；**数值仍 tools**

## 知识库窄接

每 Agent 允许检索的路径见 **`agent_kb_bindings.yaml`**（同目录）。  
代码：`packing_assistant.kb_bindings.search_for_agent(agent_id, q)`。  
API：`GET /api/kb/bindings` · `POST /api/kb/search`。
