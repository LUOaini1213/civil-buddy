---
category: trajectories
subcategory: failure_recovery
priority: high
type: trajectory
tags: [T7, structure, replan, box_scheme]
source: internal
updated: "2026-07-30"
harness: ">=0.6.3"
status: active
---
# 失败恢复 T7：结构不通过 → 打回成箱

## 目标

结构结论「不通过」时不得当可装单元进柜。

## Step 1

- thought: 结构校核
- tool: structure.calc
- args: {}
- observation: {"structure_ok": false, "reason": "span_or_load"}

## Step 2

- thought: 红线：禁止进入 loader
- tool: knowledge.search
- args: {"q": "结构不通过 红线"}
- observation: {"hits": ["01_rules/ctu_loading/safety_redlines.md"]}

## Step 3

- thought: critic → box_scheme
- tool: replan.critic
- args: {"route": "box_scheme", "reason": "structure_fail"}
- observation: {"route": "box_scheme"}

## Step 4

- thought: 调整分箱/架型后再校核
- tool: box.scheme
- args: {"standard_boxes": true}
- observation: {"n_boxes": "adjusted"}

## Step 5

- thought: 再 structure
- tool: structure.calc
- args: {}
- observation: {"structure_ok": true}

## Final

- decision: 结构通过后才进 Team B
- metrics: structure_fail_never_shipped=true
