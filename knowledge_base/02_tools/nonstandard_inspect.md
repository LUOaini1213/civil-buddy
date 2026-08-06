---
category: tools
subcategory: team_a
priority: high
type: tool_doc
tags: [nonstandard.inspect, nonstandard, TeamA, taxonomy, catalog]
source: internal
updated: "2026-08-06"
harness: ">=0.6.3"
status: active
---
# 工具：非标件检验 v2 (`nonstandard.inspect`)

## 功能

对物料/成箱结果做 **taxonomy 分型 + 分级门禁 + 仪表盘**：DATA_GAP / GEO_OVERSIZE / LOAD_HEAVY / SHAPE_CUSTOM / PACK_PATH / STRUCT_PENDING / PROCESS_SPECIAL / COMPLIANCE。  
规则算数；`FAIL` 阻断自动出运；`WARN`/`NEED_DESIGN` 走人工；API 只下发 `public_summary`。

## 代码入口

- module: `packing_assistant.tools.nonstandard_inspect`
- 函数：`inspect_nonstandard` · `public_summary` · `run_and_attach`
- team: **A**
- tool id: **`nonstandard.inspect`**
- schema: `nonstandard.inspect.v2`

## 参数（示意）

```json
{
  "materials": [{"name": "...", "L": 1200, "W": 800, "H": 50, "weight_kg": 100}],
  "boxes": [],
  "container_type": "40HQ",
  "case_id": "optional",
  "packing_options": {"strict_nonstandard_gate": false, "ns_top_n": 20}
}
```

| 参数 | 类型 | 说明 |
|------|------|------|
| materials | list | 物料行 |
| boxes | list | 可选成箱行 |
| container_type | string | 默认 40HQ |
| packing_options.strict_nonstandard_gate | bool | FAIL 时阻断 confirm→Team B |
| packing_options.ns_top_n | int | 仪表盘 top 风险条数 |

## 何时调用

- Team A 成箱展示 / HITL 前：`present_team_a` 挂载检验摘要
- 口播「非标件 / 待详设 / 易碎」前必须 tools 出 overall，禁止 LLM 自判

## overall 含义

| overall | 含义 |
|---------|------|
| PASS | 检验通过（出运仍建议预检） |
| WARN | 有非标/告警，装前人工复核 |
| NEED_DESIGN | 结构待详设，可演示非正式签章 |
| FAIL | 禁止自动出运；strict 时禁止进 Team B |

## never

- 不用 LLM 改尺寸/重量
- 不把全量 `materials` 明细默认塞进前端（用 summary）
