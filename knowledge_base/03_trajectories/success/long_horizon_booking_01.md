---
category: trajectories
subcategory: success
priority: medium
type: trajectory
tags: [long_horizon, standard_box, can_fit]
source: internal
updated: "2026-07-30"
harness: ">=0.6.3"
status: active
---
# 成功轨迹：标准铁架 + 全流程出方案

## 目标

混装铁件小票 → 可装下、有标准箱型、双口径可读。

## 规划

1. IntentSpec 解析（steps）  
2. Team A：材料 → 结构 → **标准箱库**合箱  
3. HITL 可 auto  
4. Team B：N0 → 3D → 评估 → 风险 → 出图 → finalize  

## 工具调用

- material_parser  
- run_packing（standard_boxes=True）  
- cargo_feasibility.check → ok  
- validate_boxes_against_kb → hit_rate≈1  
- compute_booking → n0  
- bin3d 自 N0 递增 → can_fit  

## 观察

- 箱型如「2米铁架」  
- can_fit=True，used≈N0 或略多  

## 反思

- 标准箱路径正确，无需 replan。  

## 结果

- ship_ok 视风险；演示可用。  
