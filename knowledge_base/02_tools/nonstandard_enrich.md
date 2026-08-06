---
category: tools
subcategory: team_a
priority: high
type: tool_doc
tags: [nonstandard.enrich, nonstandard, TeamA, notes, catalog]
source: internal
updated: "2026-08-06"
harness: ">=0.6.3"
status: active
---
# 工具：非标备注增强 (`nonstandard.enrich`)

## 功能

从物料 **名称/规格/备注** 抽取 fragile、禁翻、禁叠、ns_tags 等提示；**禁止改尺寸与重量**。  
默认 **规则关键词**（policy_fallback）；仅当 `PACKING_NS_LLM=1` 或 `packing_options.ns_llm_enrich=True` 才尝试 LLM。

## 代码入口

- module: `packing_assistant.tools.nl_nonstandard_enrich`
- 函数：`enrich_materials`
- team: **A**
- tool id: **`nonstandard.enrich`**

## 参数（示意）

```json
{
  "materials": [
    {"name": "中空玻璃 易碎", "note": "禁翻 向上", "L": 2000, "W": 1000, "H": 30, "weight_kg": 80}
  ],
  "packing_options": {"ns_llm_enrich": false}
}
```

| 参数 | 类型 | 说明 |
|------|------|------|
| materials | list | 物料行（只读尺寸重量） |
| packing_options.ns_llm_enrich | bool | 可选 LLM；失败回退规则 |

## 规则命中示例

| 备注关键词 | 写出字段 |
|------------|----------|
| 易碎/玻璃/精密 | fragile + tag 精密件 |
| 禁翻/向上/直立 | this_side_up |
| 禁叠/勿压 | no_stack |
| 开顶/框架柜 | ot_container_hint |
| 异形/非标 | tag 异形件 |

## 何时调用

- 材料解析后、成箱前：丰富 ns 提示供 `nonstandard.inspect` 与 risk 使用
- 无 Key / 默认路径：必须 rules 可跑

## never

- 改 L/W/H/weight
- 无规则兜底时硬依赖 LLM
