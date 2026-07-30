---
category: trajectories
subcategory: failure_recovery
priority: high
type: trajectory
tags: [over_payload, replan, box_scheme]
source: internal
updated: "2026-07-30"
harness: ">=0.6.3"
status: active
---
# 失败恢复：超货载 → 拆箱而非加柜空转

## 目标

单件 80t 非法夹具 / 超 payload 箱。

## 错误观察

- can_fit=False，unpacked 非空  
- 旧行为：max_containers 提到 15 仍失败  

## 恢复规划

1. cargo_feasibility → ok=False  
2. replan_critic → **route=box_scheme**，max_box_net_kg↓  
3. mass_split / 拆行  
4. 再 loader  

## 结果

- 修复后锚点 t80 正常混料 can_fit=True  
- 永久回归：`test/phase0/over_payload_monster.json`  
