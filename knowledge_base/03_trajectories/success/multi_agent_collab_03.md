---
category: trajectories
subcategory: success
priority: medium
type: trajectory
tags: [multi_agent, HITL, big_team]
source: internal
updated: "2026-07-30"
harness: ">=0.6.3"
status: active
---
# 成功轨迹：大 Team ⊃ A/B + HITL 续跑

## 目标

成箱等人确认后，磁盘恢复再拼柜。

## 规划

run_team_a_segment → save_session → load_resume_state → resume_team_b_segment  

## 工具

- save_session / load_session  
- team A agents / team B agents  

## 观察

- phase=await_user_confirm 时 boxes≥1  
- B 后 can_fit 有值，graph_segment=team_b_done  

## 结果

- 测试：`test_hitl_resume_competition.py` 3/3  
