# Workteams 联网评估 · 产品 Plan（2026-07-29）

**评估对象**：packing-agent 当前产品/架构计划（Harness **v0.6.2**）  
**方法**：联网对标（多智能体 supervisor、装柜软件、OptiGuide 类）+ 本仓库能力盘点 + 近期 workflow 实测摘要  
**结论先行**：**组织 Plan 正确，可继续；执行 Plan 需收成 3 条主线，先修 booking 体积口径，再压 LLM 路由 KPI，再做 TMS 真接。**

---

## 1. 被评估的 Plan（你们实际在走的）

| 层 | Plan 内容 | 状态 |
|----|-----------|------|
| **组织** | 大 Team（编排/HITL/critic/收口）⊃ 小 Team A 成箱 + 小 Team B 拼柜 | 已落地 |
| **Agent** | NL → IntentSpec → 多工具；禁止 LLM 写 xyz | 已落地 |
| **双路径** | `steps` 默认 + `llm_toolcall` 可选 | 已落地 |
| **质量** | 影子评测 + workteam KPI + CI tiny | 已落地 |
| **出运** | CoG/R0–R4、POR/VGM 草稿、TMS stub | 半落地 |
| **装载** | 双利用率、prefer_stack、stackable、CTU 向 CoG | 持续加深中 |
| **仓库** | hygiene：output 出仓、docs/scripts 分层 | 已落地 |

---

## 2. 三支「联网 Workteam」打分

### Team α · 多智能体架构（Supervisor 2026）

**对标**：LangGraph supervisor-via-tools、2026 production multi-agent 共识（supervisor 为默认，swarm 次之）。

| 检查项 | 判定 | 说明 |
|--------|------|------|
| 中心调度 + 专业子团队 | **通过** | 大 Team ≈ supervisor；A/B ≈ specialists |
| 子能力当 tool 调度 | **通过（可加深）** | `agent_loop` 已有 `team_a.run` / `team_b.*` |
| 有界重试 / 不无限自治 | **通过** | 内环≤3、出运≤2 |
| HITL + durable resume | **通过** | session + LG checkpoint + graph_resume |
| 默认 LLM 全权调度 | **刻意不采用** | 默认 `steps` 正确：装柜域优先确定性 |

**Team α 裁决**：组织 Plan **与 2026 生产默认一致**，不要再拆更多 Team，也不要退回扁平单流水线叙事。

### Team β · 装柜/航运产品（Load planning）

**对标**：MagicLogic/Cargo-Planner 类 3D 装载；Pando/Aptean 类 AI load + TMS；CTU 重心/空隙/叠装。

| 检查项 | 判定 | 说明 |
|--------|------|------|
| 3D + 利用率叙事 | **通过** | N0/3D 双口径已是产品差异点 |
| 叠装/承重/堆高 | **加强中** | prefer_stack / stackable / max layers 已有 P0 |
| CoG / CTU 中段 | **通过（可继续严）** | R0–R4、LNS、lateral |
| TMS/WMS 真集成 | **缺口** | 仅 stub 契约，行业软件靠这里赚钱 |
| 网络拼货/动态管道 | **不在当前 Plan** | 保持单票/批量垂直正确 |

**Team β 裁决**：垂直「成箱+拼柜+合规」Plan **对**；下一阶不是做全网拼货 Agent，而是 **装载物理规则更深 + 订舱接口真接**。

### Team γ · 评估与可观测（Eval / Ops）

**对标**：路由准确率、tool selection、trace 回放、影子评测。

| 检查项 | 判定 | 说明 |
|--------|------|------|
| 影子 steps vs llm | **通过** | `eval_workteams` + CI |
| KPI 抽取 | **通过** | `workteam_kpi`；看板化仍弱 |
| 多轮 smoke / t30 | **通过** | 近期 workflow：smoke 8/8、t30 12/12 |
| Evaluator 双口径 | **通过** | binding 自适应、outer 不进主订舱分（复核 OK） |
| Booking 体积口径 | **需修** | audit workflow：`NEEDS_FIX` |
| 前端叙事一致性 | **需修** | 部分检查仍搜 “Team Mode” 旧品牌；组织图已三层 |

**Team γ 裁决**：评测骨架 **够用**；Plan 里必须把 **booking 体积审计修通** 列为 P0，否则「双利用率」故事会被自己打脸。

---

## 3. 综合评分（相对「可演示的专业装柜 Agent」）

| 维度 | 分 | Plan 是否合理 |
|------|----|----------------|
| 组织（大⊃A/B） | 9/10 | **合理，冻结** |
| NL + IntentSpec | 8/10 | **合理** |
| 工具安全边界 | 9/10 | **合理** |
| 装载/叠装/CoG | 7/10 | **合理，继续加深** |
| 评测/CI | 7/10 | **合理，补 booking 与看板** |
| LLM 路由质量 | 5/10 | **路径有，缺真实 Key 回归** |
| TMS/出运闭环 | 4/10 | **契约有，真接不足** |
| 文档/仓库观感 | 8/10 | **hygiene 后明显改善** |

**总分（加权）≈ 7.3/10** → **Plan 方向通过，执行队列要重排。**

---

## 4. Plan 问题清单（不是架构错，是优先级）

1. **双路径并存未完全收敛**  
   - `steps`（big_team）与 `llm_toolcall`（agent_loop）与 `graph` 三套入口，对外仍易说不清「哪条是主 Plan」。  
   - **建议 Plan 写死**：主路径 = `steps`；`llm_toolcall` = 实验/影子；`graph` = HITL 分段 resume。

2. **Booking 体积路径 audit = NEEDS_FIX**  
   - 与「订柜看 booking_volume、外廓仅展示」产品承诺强相关。  
   - **必须进 P0**，否则 evaluator 再漂亮也不可信。

3. **行业集成仍停在 stub**  
   - 联网产品都把 load plan 嵌 TMS；你们有 `tms_booking` 契约即可，但 Plan 不能假装「已出运闭环」。

4. **前端/旧叙事残留**  
   - 自动化检查与部分文案仍可能对齐「Team Mode / 总分总分总 / 0.5.0」。  
   - Plan 应包含一次 **叙事对齐**（前端 label、health features、旧测试断言）。

5. **不要扩 Plan 的事**  
   - 不做第四条业务专线 Team（龙申/工厂）。  
   - 不做全网拼货/运价 Agent（那是另一条产品）。  
   - 不默认打开 LLM 全权调度。

---

## 5. 修订后的 30 天 Plan（Workteams 建议版）

### P0（本周，正确性）

| # | 事项 | 验收 |
|---|------|------|
| P0-1 | 修 booking 体积路径（audit NEEDS_FIX） | 体积柜与重量柜、外廓分项单测绿；双口径文档一致 |
| P0-2 | 主路径写死 + 文档/CI 对齐 v0.6.2 | ARCHITECTURE / README / CI 不再出现 single_closed_loop 硬断言 |
| P0-3 | 前端组织叙事与 smoke 字符串 | 三层组织图 + 去掉过时 Team Mode 硬依赖（可保留兼容文案） |

### P1（两周，可信度）

| # | 事项 | 验收 |
|---|------|------|
| P1-1 | LLM 影子评测：有 Key 时 steps vs llm 报告进 CI（软门槛） | agree_core≥0.9；记录 tool 序列 diff |
| P1-2 | KPI 出汇总页或 `output` 本地报告模板 | 覆盖率、replan、illegal=0 一页可读 |
| P1-3 | 叠装规则再压一层 | 承重/空隙 15cm 级风险提示（对齐 CTU 调研） |

### P2（月内，可对接）

| # | 事项 | 验收 |
|---|------|------|
| P2-1 | TMS HTTP 联调（沙箱） | 真 URL 返回 booking_id 写回 session |
| P2-2 | 出运包一键（POR+secure+VGM+图） | export 稳定、字段齐全 |
| P2-3 | 可选：子 Team 统一「as tool」摘要回传 | supervisor 上下文只见摘要 |

---

## 6. Go / No-Go

| 决策 | 建议 |
|------|------|
| **继续大⊃A/B Plan？** | **GO** |
| **继续 NL IntentSpec？** | **GO** |
| **默认 LLM 自主调度？** | **NO-GO**（保持 steps 默认） |
| **扩更多业务专线 Team？** | **NO-GO** |
| **优先 TMS 炫技还是 booking 修口径？** | **先 booking** |
| **当前是否可对外讲「专业装柜 Agent」？** | **可演示**；「生产对接」需 P0+P2 |

---

## 7. 一句话

**你们的 Workteams 组织 Plan 已经和 2026 联网主流对齐；真正要改的不是「再想一个架构」，而是把 Plan 收成：修订舱体积正确性 → 压评测与叙事一致 → 再接 TMS。**

---

## 参考（联网）

- LangGraph supervisor via tools / multi-agent benchmarks  
- 2026 multi-agent production：supervisor 为默认拓扑  
- MagicLogic / Cargo-Planner / Pando / Aptean load planning  
- CTU 重心、空隙、叠装（行业调研已映射到 bin3d/cog）  
- 本仓：`docs/ARCHITECTURE.md` · `docs/research/workteams-network-eval-2026-07.md`  
