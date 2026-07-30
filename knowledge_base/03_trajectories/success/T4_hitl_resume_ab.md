---
category: trajectories
subcategory: success
priority: high
type: trajectory
tags: [T4, HITL, resume, multi_agent, checkpoint]
source: internal
updated: "2026-07-30"
harness: ">=0.6.3"
status: active
---
# 成功轨迹 T4：HITL A→磁盘→B 续跑

## 目标

成箱后等人确认；进程可重启；仅从 session 恢复再拼柜。

## Step 1

- thought: 跑 Team A 至成箱
- tool: team_a.run_segment
- args: {"enable_auto_confirm": false}
- observation: {"phase": "await_user_confirm", "n_boxes": ">=1"}

## Step 2

- thought: 落盘 session（不依赖内存 dict）
- tool: session.save
- args: {"session_id": "$id"}
- observation: {"saved": true, "path": "session_store"}

## Step 3

- thought: 模拟重启：清空进程态，再 load
- tool: session.load
- args: {"session_id": "$id"}
- observation: {"phase": "await_user_confirm", "boxes_restored": true}

## Step 4

- thought: 用户确认
- tool: hitl.confirm
- args: {"approved": true}
- observation: {"phase": "team_b_ready"}

## Step 5

- thought: Team B 拼柜收口
- tool: team_b.run_segment
- args: {}
- observation: {"can_fit": "not null", "graph_segment": "team_b_done"}

## Final

- decision: 长程中断后续成功
- metrics: hitl_resume=3/3 on competition script
- tests: `scripts/test_hitl_resume_competition.py`
