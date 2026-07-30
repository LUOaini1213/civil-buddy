---
category: trajectories
subcategory: failure_recovery
priority: high
type: trajectory
tags: [T3, over_payload, replan, box_scheme, no_empty_containers]
source: internal
updated: "2026-07-30"
harness: ">=0.6.3"
status: active
---
# 失败恢复 T3：超货载 → 拆箱而非只加柜

## 目标

单件/单箱超 payload（如 monster 80t）时，**禁止只把 max_containers 拉高空转**。

## Step 1

- thought: 成箱后装载失败
- tool: plan_load.bin3d
- args: {"max_containers": 3}
- observation: {"can_fit": false, "unpacked": ">0"}

## Step 2

- thought: 诊断是否货载不可行
- tool: cargo.feasibility
- args: {}
- observation: {"ok": false, "reason": "over_payload", "suggest": "mass_split"}

## Step 3

- thought: critic 路由回成箱，降 max_box_net_kg（不是只加柜）
- tool: replan.critic
- args: {"route": "box_scheme", "max_box_net_kg": 2000, "bump_max_containers": false}
- observation: {"route": "box_scheme", "options_patched": true}

## Step 4

- thought: 质量拆分 / 拆行后重装
- tool: box.scheme
- args: {"mass_split": true, "max_box_net_kg": 2000}
- observation: {"n_boxes": "increased", "feas_ok": true}

## Step 5

- thought: 再 loader
- tool: plan_load.bin3d
- args: {}
- observation: {"can_fit": true}

## Final

- decision: 恢复成功；failure_class=over_payload_recovered
- metrics: can_fit=true after replan; empty_container_bump_only=false
- tests: `test/phase0/over_payload_monster.json`
- rule_ref: `01_rules/ctu_loading/safety_redlines.md`
