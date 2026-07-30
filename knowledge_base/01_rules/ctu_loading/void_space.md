---
category: rules
subcategory: ctu_loading
priority: high
type: rule
tags: [void, 15cm, dunnage, CTU]
source: CTU_code_practice_summary
updated: "2026-07-30"
harness: ">=0.6.3"
status: active
---
# 空隙与塞实

> 实务摘要，非法律全文。

## 规则：水平空隙

- **条件**：货与货、货与柜壁之间水平空隙
- **动作**：宜 **≤ 15 cm**；更大空隙视为动态冲击风险源；>15 cm 必须绑扎/支撑/充气袋等防移
- **后果**：大空隙未处理 → risk 降级 / replan 密装

## 规则：门端防倾

- 开门侧须防止货件前倾；门端应有阻挡或绑扎。

## 规则：刚性货更严

- 钢件、石材、混凝土等刚性货：尽量更小间隙，优先 **楔紧 + 绑扎**。

## 与代码

- 布局质量：`layout_quality` 可报告水平空隙；replan 可因大空隙触发 `multi_start`/密装。
