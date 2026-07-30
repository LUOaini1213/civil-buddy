---
category: tools
subcategory: big
priority: high
type: tool_doc
tags: [kpi.extract, big, catalog]
source: internal
updated: "2026-07-30"
harness: ">=0.6.3"
status: active
---
# 工具：路由选工具KPI (`kpi.extract`)

## 功能

从 state 抽取 workteam KPI

## 代码入口

- module: `packing_assistant.workteam_kpi`
- team: **big**
- tool id: `kpi.extract`

## 参数（示意）

```json
{"state_ref": true}
```

实际参数以模块实现为准；Agent 只选工具，数值由 tools 计算。

## 何时调用

- Team 簇 **big** 流水线中需要「路由选工具KPI」时
- 规则提示：遵循 team 边界与红线

## errors

| 情况 | 处理 |
|------|------|
| 输入 state 不完整 | 返回 ok=false / need_more_info |
| 计算失败 | 记 failure_class=tool_error，有界重试 |

## never

- never 由 LLM 代替本工具编造数值结果
- never 输出伪造 xyz（装载类工具仅返回引擎结果）
- 遵循 team 边界与红线

## 相关

- 注册表：`packing_assistant.tool_registry.TOOL_CATALOG`
- 非法行为：`05_multi_agent/illegal_tools.md`
