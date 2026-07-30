---
category: trajectories
subcategory: success
priority: high
type: trajectory
tags: [T6, dual_caliber, booking, volume]
source: internal
updated: "2026-07-30"
harness: ">=0.6.3"
status: active
---
# 成功轨迹 T6：双口径订舱话术

## 目标

同时给出订舱口径与 3D 外廓口径，禁止混用。

## Step 1

- thought: 成箱后计算订舱体积
- tool: volume.booking
- args: {"use_pack_effective": true}
- observation: {"booking_volume_m3": "V_b", "binding": "weight|volume|both"}

## Step 2

- thought: N0 = max(重量柜, 体积柜)
- tool: booking.n0
- args: {}
- observation: {"n0": "N0", "n0_weight": "Nw", "n0_volume": "Nv"}

## Step 3

- thought: 3D 装载得 outer 利用率
- tool: plan_load.bin3d
- args: {}
- observation: {"outer_space_utilization": "U_o", "containers_used": "C"}

## Step 4

- thought: 对客/评测话术分离
- tool: knowledge.search
- args: {"q": "双口径 订舱体积 outer"}
- observation: {"hits": ["01_rules/volume_weight/dual_caliber.md"]}

## Final

- decision: 报告 booking_volume_utilization 与 outer_space_utilization 两列
- metrics: never booking_volume == blind outer sum for hollow frames
- tests: `scripts/test_booking_volume_metrics.py`
