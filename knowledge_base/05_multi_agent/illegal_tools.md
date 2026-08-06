---
category: multi_agent
subcategory: protocol
priority: high
type: protocol
tags: [illegal, xyz, narrative, redline]
source: internal
updated: "2026-07-30"
harness: ">=0.6.3"
status: active
---
# 非法工具 / 非法行为（叙事红线）

以下行为在评测 `illegal` 计数与产品叙事中视为 **违规**：

| ID | 行为 | 正确做法 |
|----|------|----------|
| I1 | LLM 直接生成货件/箱体 xyz | 调用 bin3d / loader tools |
| I2 | LLM 拍脑袋报 containers_used / N0 | volume/booking + plan_load 输出 |
| I3 | 把 can_fit=False 方案当出运 | feasibility + replan 或 stop |
| I4 | 超货载只 `max_containers++` | route=box_scheme + mass_split |
| I5 | 编造缺失尺寸/重量 | need_more_info |
| I6 | 结构不通过仍进柜 | critic → box_scheme |
| I7 | 子 Team 回传全量 layout 进 supervisor | summary_protocol 摘要字段 |
| I8 | 用轨迹 few-shot 替代求解器 | 轨迹只示范流程 |

检索工具 `knowledge.search` **不得**返回坐标字段；见 search_knowledge 实现守卫。

## nonstandard
- 禁止 LLM 自判 overall FAIL/PASS；必须 `nonstandard.inspect`
- 禁止 enrich 改 L/W/H/weight
