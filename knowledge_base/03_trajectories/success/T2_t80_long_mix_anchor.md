---
category: trajectories
subcategory: success
priority: high
type: trajectory
tags: [T2, t80, anchor, long_horizon]
source: internal
updated: "2026-07-30"
harness: ">=0.6.3"
status: active
---
# 成功轨迹 T2：t80 长票锚点

## 目标

`t80_long_mix_s297883` 长票混料完整走通 bootstrap→成箱→装载→收口。

## Step 1

- thought: 长票物料归一，检查超重行
- tool: material.parse
- args: {"fixture": "t80_long_mix_s297883"}
- observation: {"n_items": "~349", "corrupt_single_80t_line": false}

## Step 2

- thought: 标准铁架 + 质量拆分 cap
- tool: box.scheme
- args: {"standard_boxes": true, "max_box_net_kg": 3200, "mass_split": true}
- observation: {"n_boxes": ">1", "feas_precheck": "pending"}

## Step 3

- thought: 单箱/单件 payload 可行性
- tool: cargo.feasibility
- args: {}
- observation: {"ok": true}

## Step 4

- thought: Team B 规划装载；柜数由 tools 算
- tool: plan_load.bin3d
- args: {"prefer_stack": true}
- observation: {"can_fit": true, "containers_used": ">=1"}

## Step 5

- thought: 评估 + 风险 + finalize
- tool: evaluator.risk.finalize
- args: {}
- observation: {"ship_ok": true, "hard_error": false}

## Final

- decision: 锚点 pass；永久回归 `scripts/test_anchor_t80_long_mix.py`
- metrics: phase0 task pass, long_horizon complete
- note: 禁止用「单行 80t 假夹具」污染夹具文件
