---
category: tender_delivery
subcategory: rules
priority: high
type: rule
tags: [transport, packaging, CTU, tender, redline]
source: internal
updated: "2026-08-06"
harness: ">=0.6.4"
status: active
---
# 运输 / 包装条款应答红线（实务）

## 抽取后必进响应矩阵

| 条款类型 | 应答证据 |
|----------|----------|
| 包装方式 / 标准箱 / 木箱 | Team A 成箱方案 + box 规格 |
| 集装箱型 / 柜数上限 | booking N0* + 3D used |
| 重心 / 绑扎 / CTU | cog + risk_compliance（中段质量 mid50 实务目标 ≥55–60%；参考 [IMO/ILO/UNECE CTU Code](https://unece.org/transport/intermodal-transport/imoilounece-code-practice-packing-cargo-transport-units-ctu-code)） |
| 超长 / 超重 | nonstandard.inspect |
| 交货期 / 分批 | 人工；Agent 只列里程碑提示 |

## 禁止

- LLM 声称「已满足全部招标要求」而无矩阵行
- 无 tools 结果时填写柜数/坐标
