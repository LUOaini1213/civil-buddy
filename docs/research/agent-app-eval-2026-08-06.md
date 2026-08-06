# 以 Agent 应用视角评估 · packing-agent

**日期**：2026-08-06 · **HEAD** `6a2ed50` / 产品基线 `33febb2`  
**Harness** 0.6.4 · **13 agents** · 大 Team⊃A/B  
**评测性质**：把本仓当作 **可交付的 Agent 应用**（非纯算法库、非纯 LLM 聊天）做竖切评估  
**对照**：联网校准 **9.10**（领域 Team 分）· 本地 SCORECARD **~9.75**（勿对外领衔）

---

## 0. 产品形态定义

| 问题 | 答案 |
|------|------|
| 是不是 Agent 应用？ | **是**：NL 入口 + 专岗编排 + tools 执行 + HITL + 可观测 UI |
| 不是什么？ | 不是 EasyCargo 运营 SaaS；不是「模型自己写 xyz」的聊天 demo |
| 评测锚点 | 生产 Agent 应用常见六维：**任务 · 长程 · 工具 · 多 Agent · 效率 · 解释** + HITL/安全 |

---

## 1. Agent 应用能力地图（可演示）

```text
用户 NL / 表上传 / 预设
  → IntentSpec（可选 LLM）
  → 大 Team 编排
  → Team A 成箱 + 非标检验 → HITL 人确认
  → Team B tools：N0* / 3D / CoG·mid50 / 风险 / 可视化
  → public_response：path_honesty · vgm_status · verdict
```

| Agent 应用能力 | 本仓落点 | 成熟度 |
|----------------|----------|--------|
| 自然语言任务入口 | NL + IntentSpec + 预设 | ✅ |
| 工具边界（写操作不归模型） | 柜数/xyz/CoG 仅 tools | ✅ 强 |
| 人在环 HITL | await_user_confirm · reject 拦 B | ✅ 强 |
| 多 Agent 专岗 | 13 固定专岗 steps 主路径 | ✅（非 free-form swarm） |
| 状态恢复 | session + graph resume | ✅ |
| 可观测 | SSE/ws · steps · trace.jsonl | ✅ |
| 路径诚实 | path_honesty · cabin reference_only | ✅ |
| 领域合规面 | 非标 taxonomy · mid50 CTU · VGM 人签 | ✅ |
| 外部系统联调 | TMS/VGM 承运人 | ⚠ stub |

---

## 2. 与「通用 Agent 应用」对标（2026）

| 外部范式 | 本仓 | 评价 |
|----------|------|------|
| LangGraph HITL interrupt/checkpoint | A→确认→B；durable session | **对齐强** |
| Tools-first / tool-call 前审批 | 拼柜算数在 tools；人确认成箱 | **对齐强** |
| Multi-agent 生产形态 = 委托工作流 | 固定 roster，非 deep free routing | **诚实对齐**（不吹 IQ） |
| 供应链 agent 要可解释 | verdict / path_honesty / VGM 面板 | **中–强** |
| GitHub harness（DeerFlow/OpenHands 类） | smoke · scorecard · workteams | **领域更深，通用 sandbox 更浅** |

---

## 3. 六维打分（Agent 应用口径 · 与联网 Team 一致）

> 与 `full-team-network-eval-2026-08-06-v2.md` 同口径，避免双轨分数。

| 维度 | 分 | Agent 应用解读 |
|------|-----|----------------|
| 任务成功 | **8.85** | 装柜任务可闭环；pack 覆盖 14 族；mid50 70% |
| 长程完成 | **9.20** | A→HITL→B 多段可恢复 |
| 工具质量 | **9.45** | tools 权威；表/非标/R4/VGM 可测 |
| 多 Agent | **8.90** | 专岗清晰；非 deep multi-agent 研究 |
| 效率 | **8.20** | 大票分钟级；UI 首屏偏信息密 |
| 解释性 | **9.40** | 路径/VGM/verdict 面 |

**联网综合（Agent 应用）**：**9.10 / 10**  
**本地 SCORECARD**：**~9.75**（硬门+phase0 归档，**禁止对外领衔**）

---

## 4. 应用级硬证据（应跑套件）

| 套件 | 证明什么 |
|------|----------|
| `smoke_agent_product.py` | harness / pipeline / HITL session 产品冒烟 |
| `eval_workteams_cli --tiny-only` | steps vs llm 影子 · agree · illegal=0 |
| `test_hitl_resume_competition` | 人确认/拒绝/多柜 resume |
| `test_path_honesty_vgm` | 路径诚实 + VGM 人签应用面 |
| `test_expand_pack_scope` | 领域任务覆盖 14 族 |
| `test_mid50_cog` | CTU 类领域质量门 |
| SCORECARD / phase0 | 比赛本地硬门归档 |

日志：`output/scratch/agent_app_eval.log`

---

## 5. 应用级优 / 缺

### 强项（Agent 应用答辩可讲）

1. **工具所有权清晰** — 模型不写柜数坐标  
2. **HITL 是产品默认** — 不是装饰 checkbox  
3. **领域竖切完整** — 材料→成箱→拼柜→风险→可视化  
4. **诚实标签** — path_honesty / VGM 未签禁提  
5. **可回归** — workteams / expand / scorecard 门禁  

### 缺口（Agent 应用审委会常问）

1. UI 首屏信息密度高（像控制台不像 C 端应用）  
2. 外部系统（承运人 VGM / TMS）仍 stub  
3. 多 Agent 是 **固定流水线**，不是动态协商 swarm  
4. 大票耗时 / 现场 Key 摩擦  
5. 与 DeerFlow 类通用 harness 比：skills 生态 / 通用 sandbox 较弱  

---

## 6. 一句话裁决

> packing-agent 是 **领域向的生产级 Agent 应用原型**：编排 + tools + HITL + 可观测齐套；联网按 Agent 应用评 **9.10**，本地分卡 **9.75 不对外领衔**。  
> 相对装柜 SaaS：缺运营层。相对纯 LLM agent：更强在 **可审计工具边界与领域门禁**。

---

## 7. 演示话术（Agent 应用口径）

**要说**  
> 这是一个装柜 **Agent 应用**：大 Team 编排，小 Team A/B 专岗，**tools 算柜数和坐标**，人在环确认成箱。  
> 带路径诚实标签与 VGM 人签；硬门与 pack 覆盖可回归。联网 **9.10**。

**不要说**  
> 通用超级助手 / 13 个智能体自由争论出方案 / 模型自己摆箱 / 运营 TMS 已上线 / 报 9.75。

---

## 8. 证据索引

| 路径 | 用途 |
|------|------|
| `docs/research/full-team-network-eval-2026-08-06-v2.md` | 联网 9.10 全文 |
| `docs/research/github-agent-eval-2026.md` | GitHub Agent 对标 |
| `docs/research/competitive-landscape.md` | 装载软件 / 算法库 |
| `output/competition/SCORECARD.md` | 本地 9.75 |
| `scripts/smoke_agent_product.py` | 产品冒烟入口 |
