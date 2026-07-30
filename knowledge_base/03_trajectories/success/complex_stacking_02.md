---
category: trajectories
subcategory: success
priority: medium
type: trajectory
tags: [stack, prefer_stack, CoG]
source: internal
updated: "2026-07-30"
harness: ">=0.6.3"
status: active
---
# 成功轨迹：叠装 + 重心

## 目标

多矮箱优先叠高，同时 mid50 可接受。

## 规划

prefer_stack + cog_rebalance + multi_start。

## 工具

- bin3d prefer_stack  
- cog / lns / lateral 视 options  

## 观察

- 部分 z>0；重箱 z=0  

## 反思

- 若 mid50 不足 → critic 加 cog_rebalance 再跑 loader。  
