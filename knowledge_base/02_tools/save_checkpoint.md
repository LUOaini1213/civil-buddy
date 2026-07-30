---
category: tools
subcategory: checkpoint
priority: high
type: tool_doc
tags: [HITL, session, checkpoint]
source: internal
updated: "2026-07-30"
harness: ">=0.6.3"
status: active
---
# 工具：save_checkpoint / save_session

## 功能

将 PackingState 持久化到磁盘（及可选 LangGraph sqlite），供中断后续。

## 代码入口

`session_store.save_session` · `lg_checkpoint`

## 何时调用

- Team A 结束后 HITL  
- pipeline 关键 / done  

## 输出

- session_id / run_id 路径在 `output/sessions` 或 runs  
