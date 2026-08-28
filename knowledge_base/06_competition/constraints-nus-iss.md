---
category: competition
subcategory: constraints
priority: high
type: scoring
tags: [constraints, steps, llm_toolcall, HITL, SME, eligibility, nus_iss]
source: internal
updated: "2026-08-28"
harness: ">=0.6.3"
status: active
---
# 比赛约束 · NUS-ISS 新加坡赛道（Agent 叙事 + 资格）

> **本文件仅适用于 NUS-ISS（新加坡）赛道**（原 `06_competition/constraints.md` 于 2026-08-28 改名保留，原文未删）。
> 海之子杯（中建国际 AI 智能体挑战，截止 2026-08-31）口径见 [constraints-hzzb.md](./constraints-hzzb.md)，两赛条款互不通用。
> 下表前 8 行（坐标 / 锁柜 / HITL 等）为引擎横切约束，**两赛通用**；「参赛资格」以下 4 行为 NUS-ISS 专属。

| 约束 | 说明 |
|------|------|
| 坐标 | 仅 tools 计算，禁止 LLM xyz |
| 默认模式 | `agent_mode=steps` 确定性流水线 |
| llm_toolcall | 可选；可调 knowledge.search；数值仍 tools |
| 锁柜 | max_containers 不可擅自突破 |
| 超货载 | 拆箱优先，禁止只加柜 |
| HITL | 可中断、可磁盘续跑 |
| 标准箱 | 默认 standard_boxes=True（非 crate 当量） |
| 知识库 | 规则与范例；**不是**求解器 |
| **参赛资格** | 须在新加坡 working/studying；海外队友不可线上豁免 |
| **SME 赛道** | 正式实习/雇佣 + SME 授权代表公司；2–4 人；可 2 人 Kickoff |
| **Public 赛道** | 非 SME 代表；必须正好 4 人；官方题 Kickoff 发放 |
| Kickoff 9/5 | 合格队员须到场；缺席可能取消资格 |

架构冻结：大 Team ⊃ 小 Team A（成箱）+ 小 Team B（拼柜）。
