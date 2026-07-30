---
category: tools
subcategory: materials
priority: high
type: tool_doc
tags: [materials, parse]
source: internal
updated: "2026-07-30"
harness: ">=0.6.3"
status: active
---
# 工具：list_cargo / material_parser

## 功能

解析与归一化物料：mm/kg、分类、感知摘要。

## 代码入口

`agents.material_parser` · adapters 归一化

## 何时调用

- Team A 开局；NL 改方案后重解析  

## 红线

- **不得编造**缺失的尺寸与重量；缺字段应标 need_more_info。
