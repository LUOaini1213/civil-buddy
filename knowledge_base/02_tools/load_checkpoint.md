---
category: tools
subcategory: checkpoint
priority: high
type: tool_doc
tags: [HITL, resume]
source: internal
updated: "2026-07-30"
harness: ">=0.6.3"
status: active
---
# 工具：load_checkpoint / load_resume_state

## 功能

从磁盘或 LangGraph thread 恢复状态，进入 Team B。

## 代码入口

`graph_resume.load_resume_state` · `resume_team_b_segment`  
测试：`scripts/test_hitl_resume_competition.py`

## 何时调用

- 用户 confirm 后  
- 进程重启后的 resume  

## 错误

| 错误 | 处理 |
|------|------|
| session 不存在 | 要求重新 team-a |
| boxes 为空 | 不可进 B，重跑成箱 |
