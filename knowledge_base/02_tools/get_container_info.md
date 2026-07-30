---
category: tools
subcategory: container
priority: high
type: tool_doc
tags: [container, 40HQ, payload]
source: internal
updated: "2026-07-30"
harness: ">=0.6.3"
status: active
---
# 工具：get_container_info / container_select

## 功能

推荐柜型、返回 payload / 容积 / 与装载后复核建议。

## 代码入口

`tools.container_select.recommend_container` · `compare_after_load`

## 何时调用

- 大 Team 开局选柜  
- finalize 复核是否建议换柜  
