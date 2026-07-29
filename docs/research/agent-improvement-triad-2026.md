# Agent 层面改进（三路联网 · 2026-07）

GitHub · 论文 · 行业 对照当前 `packing_assistant` 流水线。

## 结论一句话

几何/叠高/CoG 已较满；**Agent 产品空白**在：plan 工件化、有界 replan 批评环、出运 HITL 审批、VGM/证据包、可观测评测——**不是再堆一个 LLM 去编坐标**。

## 我们已有 vs 缺口

| 能力 | 现状 | 缺口 |
|------|------|------|
| 固定图流水线 | ✅ 总分总 agents | 策略选择/失败原因结构化不够 |
| 工具算几何 | ✅ bin3d / booking | 策略枚举 + 差异 diff 给 HITL |
| HITL | ✅ 文件 checkpoint / confirm | 审批角色、edit 工具参数、双签 |
| replan | ✅ evaluator need_replan | 有界轮次 + critic 改 packing_options |
| 可观测 | ✅ SSE/trace/OTEL 开关 | KPI 进 span；黄金用例集 CI |
| 销售估柜 | 部分 | 分享链接/步骤图/报价钩子 |
| VGM/证据 | 弱 | Method2 草稿 + 照片清单 + 归档 |
| Skills | docs/skills | 严格 SKILL 契约 + fail-loud |

## P0（Agent 优先）

1. **PackingPlan 工件**：placements + stacking + cog + layout_quality + fail_reasons 版本化 JSON  
2. **HITL 门禁策略化**：export_strict / CoG block / 改柜型 → interrupt；approve|edit|reject  
3. **有界 replan**：evaluator FAIL → critic 只改 `packing_options`/N0 → ≤2–3 轮  
4. **黄金轨迹测试**：t30/t80 + 叠高/mid50 不变量 CI  
5. **工具边界死规定**：LLM 禁止写 xyz（已遵守，写进 skill 与网关校验）

## P1

6. Skills 包：parse / scheme / strategy / compliance / explainer  
7. 计划 diff 叙事（OptiGuide 风格 before/after）  
8. Langfuse/LangSmith KPI metadata  
9. 装柜步骤工单导出（工厂 HITL）  
10. VGM Method2 草稿（须人签）

## P2

11. 客户偏好记忆 12. 多单 supervisor 13. 离线启发式进化（FunSearch 式，不进热路径）  
14. claim 证据包 15. 运价/估柜商业闭环  

## 不要做

- LLM 编坐标 · 无界多 agent 闲聊 · 当 DeerFlow 做装柜内核 · 无 CTU 只刷利用率  
