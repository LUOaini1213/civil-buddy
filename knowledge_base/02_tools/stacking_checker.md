---
category: tools
subcategory: stacking
priority: high
type: tool_doc
tags: [stack, stackable, layers]
source: internal
updated: "2026-07-30"
harness: ">=0.6.3"
status: active
---
# 工具：stacking_checker（装载策略）

## 功能

3D 放置时检查 stackable、堆高、重下轻上；报告是否可叠未叠。

## 代码入口

`tools.bin3d`（PackPolicy / prefer_stack）· `layout_quality`

## 何时调用

- loader 装载  
- replan 因空洞/可叠未叠  

## 参数（packing_options）

- `prefer_stack`, `max_stack_layers`, `max_stack_height_mm`, `prefer_bottom_weight_kg`
