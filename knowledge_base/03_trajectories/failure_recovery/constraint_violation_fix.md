---
category: trajectories
subcategory: failure_recovery
priority: high
type: trajectory
tags: [lock_budget, dense, replan]
source: internal
updated: "2026-07-30"
harness: ">=0.6.3"
status: active
---
# 失败恢复：锁柜装不下

## 观察

lock_max_containers=N 且 can_fit=False  

## 恢复

- **禁止**突破预算加柜  
- dense_mode、clearance↓、max_stack_layers↑、cog_rebalance  
- 仍失败 → stop + 建议人工减货/改意图  

## 反思

- 锁柜场景下「加柜」不是合法动作。  
