---
category: trajectories
subcategory: failure_recovery
priority: high
type: trajectory
tags: [T8, feasibility, tool_error, block]
source: internal
updated: "2026-07-30"
harness: ">=0.6.3"
status: active
---
# 失败恢复 T8：feasibility 拦截 / 工具错误

## 目标

`cargo.feasibility` 失败或工具异常时有界重试，达上限 stop + 人工。

## Step 1

- thought: 装载前可行性
- tool: cargo.feasibility
- args: {}
- observation: {"ok": false, "errors": ["single_piece_over_payload"]}

## Step 2

- thought: 不调用 loader 硬冲
- tool: replan.critic
- args: {"route": "box_scheme", "max_box_net_kg_delta": -500}
- observation: {"attempt": 1}

## Step 3

- thought: 若工具抛错，记录 failure_class
- tool: session.note
- args: {"failure_class": "feasibility_block"}
- observation: {"logged": true}

## Step 4

- thought: 多轮仍失败 → stop
- tool: replan.critic
- args: {"attempt": 3, "max_replan": 3}
- observation: {"action": "stop", "need_human": true}

## Final

- decision: need_more_info 或人工拆票；禁止编造尺寸
- metrics: illegal_silent_ship=0
- rule_ref: escalation_rules + safety_redlines
