# Workteams 联网评估（2026-07）

对照对象：本仓库 **大 Team ⊃ 小 Team A 成箱 + 小 Team B 拼柜**（harness ≥ 0.6.1）  
评估维度：多智能体组织模式 · LLM tool-call · HITL/resume · 装柜行业 · 与 OptiGuide 类 what-if

---

## 1. 我们是什么（现状快照）

| 项 | 现状 |
|----|------|
| 组织 | `big_team_wraps_a_b`：大 Team=编排/HITL/critic/收口；A=成箱；B=拼柜 |
| 角色 | 13 节点名册（含 intent / llm_scheduler / replan_critic） |
| 工具 | 27 个确定性 tools + 11 个 LLM 可调度白名单 |
| 调度 | 默认 `steps` 固定专业节点；可选 `llm_toolcall` 多轮选工具 |
| 边界 | 内环 replan≤3 · 出运 ship_replan≤2；LLM **禁止写 xyz** |
| 入口 | NL → IntentSpec；场景名仅示例 |
| Resume | graph A/B 子图 + 磁盘 session + LangGraph checkpoint |

---

## 2. 对标坐标系（联网）

### 2.1 通用多智能体形态

| 形态 | 来源特征 | 与我们关系 |
|------|----------|------------|
| **Supervisor + subagents** | 中心调度、子代理作 tool 调用；LangChain/LangGraph 推荐「supervisor via tools」 | **高度同构**：大 Team ≈ supervisor；A/B ≈ specialist subagents |
| **Hierarchical teams** | 多层 supervisor 嵌套 | 我们是 **两层**（大 Team + 两个小 Team），未做更深嵌套 |
| **Swarm / handoff** | 对等 handoff、子 agent 可互转 | 我们 **不** 做 A↔B 对等 handoff；由大 Team critic 路由 |
| **单 Agent 全能** | 一个 LLM 绑全部 tools | 我们有 `llm_toolcall` 路径，但仍以 **分 Team 工具簇** 约束 |

LangGraph 侧共识：领域边界清晰时用 supervisor；子 agent 用 tool 封装；控制上下文与 handoff 消息。  
见：[Subagents / supervisor](https://docs.langchain.com/oss/python/langchain/multi-agent/subagents-personal-assistant)、[Benchmarking multi-agent](https://www.langchain.com/blog/benchmarking-multi-agent-architectures)、[langgraph-supervisor 已建议改用 tools 模式](https://reference.langchain.com/python/langgraph-supervisor)。

### 2.2 评估与可观测

生产向多 agent 强调：**路由准确率、tool 选择质量、全链路 trace、持续改进回路**（如 telecom 场景的 supervisor 指标）。  
见：[Continuous improvement for LangGraph multi-agent](https://galileo.ai/blog/evaluate-langgraph-multi-agent-telecom)。

我们已有：`agent_steps` · stream schema · OTEL hooks · eval_harness · replan_log。  
缺口：尚未把「supervisor 路由准确率 / tool selection quality」做成 **固定 KPI 看板**。

### 2.3 OptiGuide 类（NL what-if + 求解器）

OptiGuide 路线：自然语言 → 改优化模型/约束 → **求解器重算**，LLM 不替代 solver。  
见：[OptiGuide overview](https://www.microsoft.com/en-us/research/project/optiguide-language-models-for-optimization/) · [GitHub](https://github.com/microsoft/OptiGuide)。

我们：`nl_whatif` / `whatif` + 3D/CoG tools 重算；IntentSpec 驱动 options。  
对齐度：**高**（尤其「意图改约束、不写坐标」）。

### 2.4 装柜 / 航运行业 AI

| 行业方向 | 特征 | 我们 |
|----------|------|------|
| 装柜软件（MagicLogic 等） | 3D 利用率、WMS/TMS 集成、稳定性 | 有 3D/双口径利用率；**ERP/TMS 集成弱** |
| Load planning agents（Pando 等） | 拼货、订舱、实时管道 | 我们偏 **单票/批量成箱+拼柜**，非全网拼货 |
| 航运 AI agent 舰队（如 CH Robinson 多 agent） | 报价、订单、分类等 **文档/流程 agent** | 我们是 **物理装载+合规** 垂直；文档链（VGM/POR）有草稿 |
| CTU 实践 | 重心/绑扎/装载证明 | 有 CoG R0–R4、secure WO、checklist；证书工作流仍浅 |

见：[MagicLogic shipping container software](https://magiclogic.com/shipping-container-software/) · [Pando load planning agents](https://pando.ai/blogs/revolutionizing-load-planning-with-ai-agents) · [CTU Code 相关材料](https://unece.org/sites/default/files/2025-12/ECE-TRANS-WP.24-CTU-2025-Inf01e_.pdf)。

---

## 3. 工作团队评分卡（相对 2026 主流）

评分：● 强 / ◐ 中 / ○ 弱（相对「可上线的专业装柜 Agent」目标）

| 维度 | 分 | 依据 |
|------|----|------|
| **组织形态（大⊃A/B）** | ● | 与 supervisor+specialists 行业主推一致；边界清晰 |
| **NL 通用入口** | ● | IntentSpec + material-aware；非线路写死 |
| **Tool 安全边界** | ● | 白名单 + 禁止 LLM 写坐标；符合 OptiGuide 精神 |
| **有界闭环** | ● | 内/外环上限 + critic 只改策略 |
| **HITL / 分段 resume** | ● | A→确认→B；磁盘+LG checkpoint |
| **LLM 自主 tool-call** | ◐ | 已实现路径；默认仍 steps；缺 Key 时 policy，真实 LLM 路由质量未系统测 |
| **子 Team 封装为 tool** | ◐ | `team_a.run` / `team_b.plan_load_eval` 已在 agent_loop；未完全「子图 as tool」统一 |
| **评估 KPI 体系** | ◐ | 有 harness/smoke；缺路由准确率/回归套件常态化 |
| **行业集成（TMS/ERP）** | ○ | 交付物有，系统对接无 |
| **端到端出运闭环** | ◐ | VGM/POR/清单草稿有；签核/申报正式流弱 |
| **前端组织可解释** | ● | 三层组织图已画 |

**综合**：架构主骨架 **达到 2025–2026 主流 supervisor 工作团队水准**；装柜垂直深度（成箱+3D+CoG）是差异点；LLM 调度与行业集成是下一阶。

---

## 4. 与「理想 Workteam」差距（可执行）

### P0（巩固差异）

1. **Eval 套件绑定 Team 语义**  
   - 指标：`can_fit` · `ship_ok` · mid50 · 柜数 · critic 轮次 · agent_mode  
   - 每 PR 跑 tiny + t30 子集  
2. **LLM tool-call 影子评测**  
   - 同票 `steps` vs `llm_toolcall`：柜数/can_fit/步骤数/失败率  
3. **子 Team 工具契约统一**  
   - 文档化：`team_a.run` 输入输出 = boxes 摘要；`team_b.*` = plan 摘要  

### P1（对齐 supervisor 最佳实践）

4. 大 Team 只见 **摘要**，不全量塞 3D 进 LLM 上下文  
5. 路由 trace：每次 critic/route 记 `route_reason` 可聚合准确率  
6. HITL 卡片标准化（已有 hitl_summary → 固定字段版）

### P2（行业）

7. TMS/订舱号回写接口 stub → 真对接  
8. CTU 装载证明 PDF 一键导出  

---

## 5. 结论（给决策用）

| 问题 | 结论 |
|------|------|
| 工作团队分法对不对？ | **对。** 大 Team 调度 + A 成箱 + B 拼柜，是主流 supervisor 模式在装柜域的正确落地。 |
| 和「扁平单 Team」比？ | 分层更利于 HITL、权限与工具簇；不要再抹平成单一流水线叙事。 |
| 和行业装柜软件比？ | 算法/合规 Agent 化 **领先叙事**；集成与规模化运营 **落后**。 |
| 和 LangGraph 官方范式比？ | 概念对齐；可再加强「subagent as tool + 上下文裁剪 + 路由 KPI」。 |
| 龙申/工厂？ | 仍只是例子；不进入 workteam 组织。 |

**一句话**：  
Workteams 组织 **已具备联网对标下的正确架构**；下一步不是再拆 Team，而是 **测路由、压 LLM 路径、补行业接口**。

---

## 6. 参考链接

- LangChain multi-agent subagents / supervisor  
- LangGraph multi-agent architecture benchmarks (2025)  
- Microsoft OptiGuide  
- MagicLogic / Pando load planning AI  
- UNECE CTU Code materials (2025)  
- Galileo: evaluating LangGraph multi-agent in production  
