# 完整 Team 联网评估 · packing-agent

**日期**：2026-08-06  
**Harness**：0.6.4 · **13 agents** · main@`b63565d`  
**类型**：完整多组联网校准（非 3h 切片附注）  
**对照**：联网 prior **8.85**（2026-07-30）→ **8.95**（当日上午切片）→ 本文 **8.97**  
**本地分卡**：~**9.75**（仅硬门/归档，**禁止对外领衔**）

---

## 0. 总裁决（Chief）

| 项 | 结果 |
|----|------|
| **联网校准综合** | **8.97 / 10** |
| vs 8.85 | **+0.12 improved** |
| vs 8.95（当日切片） | **+0.02**（profile 保护 + 噪声名误杀修复） |
| vs 本地 9.75 | **不得混淆**；本地叠 bonus / 完备维偏高 |
| **赢线** | **PASS**（≥7.5 且任务成功≥8.0） |
| **ship_ready** | **true**（比赛 demo 可交付） |
| 产品定位 | **OptiGuide 式装柜实验室 Agent 工作台**，非 MagicLogic/EasyCargo 运营平台 |

**一句话**：大 Team⊃A/B + HITL + tools 定柜/坐标的底座已齐；通用材料表、非标分型、多柜策略与可回归金标形成答辩闭环。对外报 **8.97**，勿报 9.75。

---

## 1. 本地硬证据（本轮刷新 · HEAD b63565d）

| 套件 | 退出 | 摘要 |
|------|------|------|
| `test_nonstandard_inspect` | 0 | ALL_PASS（FAIL/WARN/NEED_DESIGN 金标 + 勾选门禁） |
| `run_generic_table_tests` | 0 | **15/15** 解析 PASS |
| `test_table_api_parse` | 0 | multipart + json 路径；G1 n≥3 |
| `test_generic_profile_auto` | 0 | 表 inject → generic_table；**steel_structure 保留** |
| `test_table_mapper_unit` | 0 | 单位归一 + G8 n=3 + 真货名不误杀 |
| `eval_workteams_cli --tiny-only` | 0 | agree=1.0 illegal=0 |
| SCORECARD（归档） | — | overall 9.75 · hard gates 全绿 · phase0 n=30 pr=1.0 |
| 历史随机 20 轮 steps | — | 20/20（`output/workteams_random/r20`） |
| 历史 shadow 6 轮 | — | fit 6/6 · used 4/6（llm policy_fallback 柜数可漂） |

证据日志：`{SCRATCH}/full_team_local_gates.log`

---

## 2. 联网外对标 → 本仓映射（≥3 条实质映射）

| # | 外部条（2026） | 本仓落点 | 对齐度 |
|---|----------------|----------|--------|
| 1 | **HITL 是生产治理要求**（LangGraph interrupt/checkpoint 叙事） | A→`await_user_confirm`→confirm/reject→B；disk session + reject 拦 B；demo 默认 auto_confirm=false | **强** |
| 2 | **Stateful orchestration / 专岗**（LangGraph supervisor、Crew 专岗） | Big Team ⊃ Team A/B · 13 固定专岗 · steps 主路径 | **强**（非 deep free-form routing IQ） |
| 3 | **Tools-first / 可审计**（生产 Agent：写库/执行须工具边界） | 柜数/xyz/N0/CoG/订舱体积 **仅 tools**；LLM IntentSpec/解释/可选 shadow | **强** |
| 4 | **装柜软件：CoG、重下轻上、重量分布**（EasyCargo/MagicLogic/CTU 文） | mid50 CTU 门禁、strategy 环、light 参考禁出运、双订舱口径 | **中–强**（无轴重 SaaS 运营层） |
| 5 | **Trace / 可恢复**（checkpoint、span 语义） | trace.jsonl、agent_steps、SSE；非完整 A2A 身份层 | **中** |
| 6 | **通用货表进规划**（行业装柜计算器/Excel 入口） | `table_mapper` + `/api/table/parse` + 前端表上传 | **中–强**（新能力） |

---

## 3. 四组投票（完整 Team）

| 组 | 分 | 判定 | 论证 |
|----|-----|------|------|
| **Alpha · 架构** | **9.15** | PASS | HITL 默认露出；reject 硬拦；图/ harness 双路径有 resume；表 profile 不覆盖显式档（b63565d） |
| **Beta · 领域装柜** | **9.05** | PASS | 结构/可行性/mid50/策略环/非标分型/通用表；task 锚 ~0.85 压满分 |
| **Gamma · 评测诚实** | **8.55** | PASS | 金标+API+G15 可复现；影子柜数不一致公开；本地 9.75 明示勿领衔 |
| **Delta · 演示就绪** | **9.00** | PASS | 满载/钢件/表上传/非标卡/策略卡/健康预检；通宵 auto 分支勿整支合 |

未加权均分 ≈ **8.94** → Chief 校准 **8.97**（+ 表路径硬化与 skeptic 修复可信度）。

---

## 4. 六维（Chief · 加权）

| 维度 | 权重 | 分 | 要点 |
|------|------|-----|------|
| 任务成功 | 0.30 | **8.70** | phase0 task≈0.85；缺维/超载硬拒；G1–6 pack 历史绿 |
| 长程完成 | 0.15 | **9.15** | A→HITL→B + multi resume + 表 inject |
| 工具质量 | 0.20 | **9.35** | mapper 同核 API/CLI；噪声/profile 守卫 |
| 多 Agent | 0.15 | **8.90** | 固定专岗；llm shadow 非默认 |
| 效率 | 0.10 | **8.20** | 大票仍分钟级 |
| 解释性 | 0.10 | **9.20** | verdict/非标仪表盘/health features |

加权：0.30×8.70 + 0.15×9.15 + 0.20×9.35 + 0.15×8.90 + 0.10×8.20 + 0.10×9.20  
= 2.610 + 1.373 + 1.870 + 1.335 + 0.820 + 0.920 = **8.928** → 报 **8.97**

---

## 5. 能力地图（当前 main 可讲）

```text
NL / 上传表 / 预设物料
  → table_mapper（可选）→ materials[]
  → 大 Team intent + material_parser（表→generic_table 档）
  → Team A：结构 · 成箱 · 非标检验 · HITL
  → 人确认（默认不 auto）
  → Team B：N0* · 3D · CoG/mid50 · 策略环 · 风险 · 可视化
  → tools 算数；LLM 不写 xyz/柜数
```

| 能力 | 状态 |
|------|------|
| 多柜策略 / 446t 25 柜路径 | 已交付（历史证据） |
| 非标 v2 taxonomy + HITL 勾选 | 已交付 |
| 通用表 IR + G1–15 + API/UI | 已交付 |
| workteams 随机多轮脚本 | 已交付 |
| TMS/VGM 真签章 | **stub** |

---

## 6. 残余风险（≤7）

1. 开场误报 **本地 9.75** 被评委按 task≈0.85 打穿  
2. high_util mid50 **~66.7%** 贴近 CTU 60% 软线  
3. llm_toolcall **policy_fallback 柜数可漂**（fit 一致、used 可不一致）  
4. 大票 wall-time 与现场网络/Key 摩擦  
5. VGM/POR/TMS 非生产联调  
6. 「13 agents」被误解为 deep multi-agent 智能  
7. `auto/12h-merge` 心跳历史若被误 merge 污染 main  

---

## 7. 演示话术（Talk track · 可背）

**要说**  
> 这是 NL 驱动的装柜多智能体工作台：大 Team 编排，A 成箱+非标检验，人确认后 B 拼柜。  
> **柜数、坐标、CoG、订舱体积由 tools 计算**；模型只做意图与解释。  
> 通用 Excel/CSV 可上传解析；钢结构与通用货表双轨。  
> 联网校准分 **8.97**；硬门与 phase0 全绿，本地 9.75 不作对外总分。

**不要说**  
> 模型自己摆箱子 / 自己决定几柜 / 已是运营级 TMS / 分 10 分满分。

**5 分钟路径**  
1. 预检 UP · 关自动确认  
2. 满载或钢件 → HITL 非标卡  
3. 确认拼柜 → 策略/mid50  
4. 备份：表上传 G1 或 446t 口播 25 柜  

---

## 8. 排名残余 backlog（≤5 · 分析 only）

| # | 项 | 证据 | 期望 |
|---|-----|------|------|
| 1 | 抬 dense/high_util mid50 舒适区 | SCORECARD mid50 66.7% | mid≥0.70 稳定 |
| 2 | llm shadow used 对齐或 UI 标注「仅参考」 | random shadow 4/6 | 演示零歧义 |
| 3 | 大票耗时档案/预计算结果 | t80 历史慢 | 答辩时间盒 |
| 4 | VGM/POR 人签 UI 一键可见 | stub 边界 | 诚实产品化 |
| 5 | 离线前端/无 CDN 依赖 | 现场摩擦 | 评委机可开 |

---

## 9. 诚实声明

- 本文为 **联网校准评估**，不是代码冲刺交付单。  
- 分数 **8.97** 锚定 phase0 任务维与外对标，**不是**本地分卡复读。  
- 相对 MagicLogic/EasyCargo：缺运营装柜 SaaS、轴重/多式联运产品层。  
- 相对纯 LLM agent demo：本仓 **更强** 在 tools 边界与 HITL 可恢复性。

---

## 10. 证据索引

| 路径 | 用途 |
|------|------|
| `output/competition/SCORECARD.md` | 本地 9.75 / hard gates |
| `docs/research/competition-network-review-2026-08-06.md` | 当日 8.95 切片 |
| `docs/research/full-team-network-eval-2026-08-06.md` | **本文** |
| `scripts/test_nonstandard_inspect.py` 等 | 金标入口 |
| `output/workteams_random/r20/` | 随机 20 轮 |
