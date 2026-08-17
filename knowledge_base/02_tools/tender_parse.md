---
category: tools
subcategory: team_t
priority: high
type: tool_doc
tags: [tender.parse, tender.checklist, tender.response_matrix, TeamT, catalog]
source: internal
updated: "2026-08-13"
harness: ">=0.6.4"
status: active
---
# 工具：招标要点 / 清单 / 响应矩阵 (`tender.*`)

## 功能

- `tender.parse`：规则抽取条款（category/title/snippets/**requirement_ref/owner/risk**）+ 行项目（★/评分点/专项）+ `handoff` / P0
- `tender.checklist`：must_respond 勾选清单
- `tender.response_matrix`：条款×证据；装柜 summary 可覆盖 transport/packaging
- `run_tender_pipeline`：解析 → 矩阵 → 经营岗交接 → 按抽出评分点出技术标目录骨架
- 不编造天数/分值/workhead；原文没有则 `duration_days=null`

## 代码入口

- module: `packing_assistant.tools.tender_parse`
- team: **T**
- tool ids: `tender.parse` · `tender.checklist` · `tender.response_matrix`

## never

- 编造资质/业绩
- 无 evidence 声称 covered
