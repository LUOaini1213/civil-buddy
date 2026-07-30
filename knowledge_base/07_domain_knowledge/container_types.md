---
category: domain
subcategory: containers
priority: low
type: domain
tags: [container, 40HQ, 20GP, 柜型]
source: internal
updated: "2026-07-30"
harness: ">=0.6.3"
status: active
---
# 集装箱柜型常识

| 常用 | 用途提示 |
|------|----------|
| 20GP | 重货/体积小 |
| 40GP / 40HQ | 混料主流；HQ 更高 |
| OT / FR | 超限件（本 Agent 主路径仍以标准封闭柜+架为主） |

内尺寸与 payload **以代码柜型表 / 配置为准**，本页不双写毫米表。  
Agent 选柜：`container.select`。
