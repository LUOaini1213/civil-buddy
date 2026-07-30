---
category: trajectories
subcategory: success
priority: high
type: trajectory
tags: [T5, container_budget, NL, lock]
source: internal
updated: "2026-07-30"
harness: ">=0.6.3"
status: active
---
# 成功轨迹 T5：NL 锁柜 / 柜数预算

## 目标

用户说「预算 1 柜 / 最多 2 柜」→ IntentSpec 写入 max_containers → 装载遵守。

## Step 1

- thought: NL → IntentSpec
- tool: intent.interpret
- args: {"text": "这票预算最多1个40HQ"}
- observation: {"max_containers": 1, "container_type_hint": "40HQ"}

## Step 2

- thought: 成箱
- tool: box.scheme
- args: {"standard_boxes": true}
- observation: {"n_boxes": "N"}

## Step 3

- thought: 拼柜受预算约束
- tool: plan_load.bin3d
- args: {"max_containers": 1}
- observation: {"containers_used": "<=1", "can_fit": "true|false"}

## Step 4

- thought: 若 can_fit=false，密装/叠高/打回成箱，不擅自破预算
- tool: replan.critic
- args: {"respect_budget": true, "route": "dense_or_box_scheme"}
- observation: {"budget_violated": false}

## Final

- decision: 锁柜约束优先于「盲目加柜冲 can_fit」
- metrics: containers_used <= budget when budget set
- rule_ref: `01_rules/booking_constraints/container_budget.md`
