---
category: rules
subcategory: booking_constraints
priority: high
type: rule
tags: [container_budget, lock, max_containers, NL]
source: internal
updated: "2026-07-30"
harness: ">=0.6.3"
status: active
---
# 柜数预算 / 锁柜

## 规则

- Intent / NL 写入 `max_containers` 后，装载 **不得擅自突破**。
- can_fit=false 且预算锁定：密装、叠高、打回成箱；**不**为冲分偷偷加柜。
- 用户明确改预算除外（新 Intent）。

## 条件 / 动作 / 后果

- **条件**：`max_containers` 非空
- **动作**：plan_load 受约束；critic `respect_budget=true`
- **后果**：破预算视为约束违规

## 轨迹

- T5_container_budget_lock
