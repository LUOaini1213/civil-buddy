---
category: tools
subcategory: packing
priority: high
type: tool_doc
tags: [3D, can_fit, CoG]
source: internal
updated: "2026-07-30"
harness: ">=0.6.3"
status: active
---
# 工具：bin3d.pack

## 功能

三维装箱；支持 multi_start、叠装、CoG 相关放置偏好。

## 代码入口

`tools.bin3d` · loader 自 N0 递增

## 红线

- **禁止 LLM 写 xyz**；结果以 engine 输出为准。

## 失败

- `can_fit=False` / `unpacked_box_ids` → evaluator need_replan → critic。
