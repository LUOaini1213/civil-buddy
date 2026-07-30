---
category: rules
subcategory: ctu_loading
priority: high
type: rule
tags: [load_bearing, payload, floor, CTU]
source: CTU_code_practice_summary
updated: "2026-07-30"
harness: ">=0.6.3"
status: active
---
# 承重与柜底

> 实务摘要，非法律全文。

## 规则

- 单柜总货重不得超过柜 payload（含安全裕度策略由配置决定）。
- 点荷载过大时须垫板分散（实务要求）。
- 单箱超 cap → 拆分，而不是硬塞。

## 代码

- `cargo_feasibility` · container payload 表 · `packing_knowledge_base.json` 箱规格
