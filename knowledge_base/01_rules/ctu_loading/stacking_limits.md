---
category: rules
subcategory: ctu_loading
priority: high
type: rule
tags: [stack, stacking, crush, CTU]
source: CTU_code_practice_summary
updated: "2026-07-30"
harness: ">=0.6.3"
status: active
---
# 叠装限制

> 实务摘要，非法律全文。

## 规则

- 下层箱须能承受上层荷载；不可压溃包装/架体。
- prefer_stack 仅在结构与 fragility 允许时启用。
- 重货优先底层；轻泡/ fragile 不压底。

## 条件 / 动作 / 后果

- **条件**：多箱叠高或 prefer_stack=true
- **动作**：stacking_checker / 结构与 risk 联合
- **后果**：不满足则取消叠高或改方案

## 代码

- `stacking` 相关 tools · risk_rules · loader options
