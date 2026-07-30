---
category: multi_agent
subcategory: examples
priority: medium
type: protocol
tags: [collab, examples]
source: internal
updated: "2026-07-30"
harness: ">=0.6.3"
status: active
---
# 协作示例（摘要级）

## 例 1：标准短票

大 Team 开 Intent → A 成箱摘要 n_boxes=4 → HITL auto → B can_fit=true → finalize。

## 例 2：超货载

B 回报 can_fit=false, failure_class=over_payload → critic route=box_scheme → A mass_split → B 再装。

## 例 3：HITL 跨进程

A 后 await_user_confirm → save → 新进程 load → confirm → B done。  
详见轨迹 T4。
