---
category: competition
subcategory: constraints
priority: high
type: scoring
tags: [constraints, steps, llm_toolcall, HITL]
source: internal
updated: "2026-07-30"
harness: ">=0.6.3"
status: active
---
# 比赛约束（Agent 叙事）

| 约束 | 说明 |
|------|------|
| 坐标 | 仅 tools 计算，禁止 LLM xyz |
| 默认模式 | `agent_mode=steps` 确定性流水线 |
| llm_toolcall | 可选；可调 knowledge.search；数值仍 tools |
| 锁柜 | max_containers 不可擅自突破 |
| 超货载 | 拆箱优先，禁止只加柜 |
| HITL | 可中断、可磁盘续跑 |
| 标准箱 | 默认 standard_boxes=True（非 crate 当量） |
| 知识库 | 规则与范例；**不是**求解器 |

架构冻结：大 Team ⊃ 小 Team A（成箱）+ 小 Team B（拼柜）。
