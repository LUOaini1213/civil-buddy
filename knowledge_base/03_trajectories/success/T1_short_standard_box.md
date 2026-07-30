---
category: trajectories
subcategory: success
priority: high
type: trajectory
tags: [T1, standard_box, short, can_fit]
source: internal
updated: "2026-07-30"
harness: ">=0.6.3"
status: active
---
# 成功轨迹 T1：短票标准箱

## 目标

少量混料 → 标准铁架成箱 → 单柜/少柜拼柜 → `can_fit=True`。

## Step 1

- thought: 解析物料，不得编造尺寸重量
- tool: material.parse
- args: {"source": "materials_rows", "strict": true}
- observation: {"n_items": 12, "missing_dims": 0}

## Step 2

- thought: 默认标准箱合箱，非 crate 直通
- tool: box.scheme
- args: {"standard_boxes": true, "max_box_net_kg": 3200}
- observation: {"n_boxes": 4, "standard_box_hit_rate": 1.0}

## Step 3

- thought: 可行性与货载
- tool: cargo.feasibility
- args: {"boxes": "$state.boxes"}
- observation: {"ok": true, "over_payload": 0}

## Step 4

- thought: N0 规划后 3D 装载（坐标仅 tools）
- tool: plan_load.bin3d
- args: {"container": "40HQ", "max_containers": null}
- observation: {"can_fit": true, "containers_used": 1, "n0": 1}

## Final

- decision: 出运方案可展示；双口径同时报 booking% 与 outer%
- metrics: can_fit=true, containers_used=1, illegal_tool_xyz=0
- tests: phase0 tiny/small 族
