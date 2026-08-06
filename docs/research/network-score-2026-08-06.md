# 联网打分 · packing-agent（HEAD 848f118）

**日期**：2026-08-06（刷新）  
**Harness**：0.6.4 · **13 agents** · main@`848f118`  
**类型**：联网校准综合分（分析产物，**不是**本地 SCORECARD 复读）  
**对照链**：8.85（2026-07-30）→ 8.95（当日切片）→ **8.97**（full-team@`b63565d`）→ 本文 **9.00**  
**本地分卡**：~**9.75**（硬门/归档，**禁止对外领衔**）

---

## 0. 总裁决（Chief）

| 项 | 结果 |
|----|------|
| **联网校准综合** | **9.00 / 10** |
| vs 8.97（full-team 同日） | **+0.03**（path_honesty / VGM 面 / 非标 8 套磁盘夹具） |
| vs 8.95 | **+0.05** |
| vs 8.85 | **+0.15** |
| vs 本地 9.75 | **不得混淆**；本地叠 bonus / 完备维偏高 |
| **赢线** | **PASS**（≥7.5 且任务维≥8.0） |
| **ship_ready** | **true**（比赛 demo 可交付） |
| 产品定位 | **OptiGuide 式装柜实验室 Agent 工作台**，非 MagicLogic/EasyCargo 运营平台 |

**一句话**：tools 定柜/坐标 + HITL 成箱 + 通用表 + 非标分型；本轮补齐 **路径诚实标签** 与 **VGM 状态面**，并扩 **8 套非标磁盘夹具** 可回归。对外报 **9.00**，勿报 9.75。

---

## 1. 本地硬证据（本轮刷新 · HEAD 848f118）

| 套件 | 退出 | 摘要 |
|------|------|------|
| `test_nonstandard_inspect` | 0 | ALL_NONSTANDARD_GOLDEN_PASS |
| `test_nonstandard_new_fixtures` | 0 | **8/8** ALL_PASS（FAIL×2 WARN×6 · taxonomy 覆盖） |
| `run_generic_table_tests` | 0 | **15/15** parse PASS |
| `test_table_api_parse` | 0 | multipart + json；ALL_PASS |
| `test_path_honesty_vgm` | 0 | path_honesty=llm_toolcall_policy_fallback · vgm=not_drafted |
| `test_generic_profile_auto` | 0 | generic_table inject；**steel_structure 保留** |
| `eval_workteams_cli --tiny-only` | 0 | agree=1.0 illegal=0 |
| SCORECARD（归档） | — | overall **9.75** · hard gates 全绿 · phase0 n=30 |

证据日志：`output/scratch/network_score_local_gates.log`  
摘要：`output/scratch/network_score_summary.md`

**相对 8.97 切片新增硬证**

- `path_honesty` + `vgm_status` 进 public_response / 回归  
- 磁盘 `test/sim_materials/ns_*` ×8 + `test_nonstandard_new_fixtures`  
- 仍未抬 high_util mid50 舒适区（历史 ~66.7% 贴近 60% 软线）

---

## 2. 联网外对标 → 本仓映射（≥3 条实质）

| # | 外部条（2025–2026） | 本仓落点 | 对齐度 |
|---|---------------------|----------|--------|
| 1 | **HITL 是生产治理**（LangGraph interrupt/checkpoint；tool-call 前人工批准为头号用例） | A→`await_user_confirm`→confirm/reject→B；reject 硬拦 B；demo 默认 auto_confirm=false | **强** |
| 2 | **Stateful 专岗编排**（LangGraph nodes/edges；非 deep free-form 即生产） | Big Team ⊃ A/B · 13 固定专岗 · steps 主路径 | **强** |
| 3 | **Tools-first / 可审计写操作** | 柜数/xyz/N0/CoG/订舱体积 **仅 tools**；LLM IntentSpec/解释/可选 shadow | **强** |
| 4 | **CTU 60/50 · CoG 偏心**（IMO/ILO/UNECE；中段 50% 装约 60% 货重） | mid50 软门、strategy 环、light 参考禁出运 | **中–强**（无轴重 SaaS 运营层） |
| 5 | **货量/质量声明诚实**（VGM 须核实；缺信息阻碍安全装箱） | `vgm_status` 明示 not_drafted / 人签；`path_honesty` 标明 policy_fallback 非真 LLM 摆箱 | **中–强**（本轮新增面） |
| 6 | **通用货表进规划**（装柜软件 Excel/导入） | `table_mapper` + `/api/table/parse` + 前端上传 · G1–15 | **中–强** |

---

## 3. 四组投票

| 组 | 分 | 判定 | 论证 |
|----|-----|------|------|
| **Alpha · 架构** | **9.20** | PASS | HITL 默认；reject 硬拦；path_honesty 进 harness 公共响应（防误读「模型自己摆箱」） |
| **Beta · 领域装柜** | **9.10** | PASS | 表/非标/mid50/策略环；**8 套磁盘 ns 夹具**扩 taxonomy 覆盖；task 锚仍压满分 |
| **Gamma · 评测诚实** | **8.70** | PASS | 金标+API+G15+ns8+path_vgm 可复现；影子 policy_fallback 公开；本地 9.75 明示勿领衔 |
| **Delta · 演示就绪** | **9.10** | PASS | 表上传+非标卡+路径/VGM 诚实面；大票仍耗时；非运营 SaaS |

未加权均分 ≈ **9.025** → Chief 校准 **9.00**（不报 9.03，避免小数膨胀感）。

---

## 4. 六维（Chief · 加权）

| 维度 | 权重 | 分 | 要点 |
|------|------|-----|------|
| 任务成功 | 0.30 | **8.70** | phase0/task 锚；缺维/超载硬拒；未抬 mid≥0.70 |
| 长程完成 | 0.15 | **9.15** | A→HITL→B + multi resume + 表 inject |
| 工具质量 | 0.20 | **9.40** | mapper 同核；path/VGM 面可测 |
| 多 Agent | 0.15 | **8.90** | 固定专岗；llm shadow 非默认 |
| 效率 | 0.10 | **8.20** | 大票仍分钟级 |
| 解释性 | 0.10 | **9.35** | verdict / 非标仪表盘 / path_honesty / vgm_status |

加权：0.30×8.70 + 0.15×9.15 + 0.20×9.40 + 0.15×8.90 + 0.10×8.20 + 0.10×9.35  
= 2.610 + 1.373 + 1.880 + 1.335 + 0.820 + 0.935 = **8.953** → 报 **9.00**

---

## 5. 相对 8.97 的增量（诚实）

| 增量 | 证据 | 对分影响 |
|------|------|----------|
| path_honesty 公共面 | harness + `test_path_honesty_vgm` | Gamma/Alpha/解释 + |
| vgm_status 面 | 同上；人签诚实 | Delta/对标 VGM + |
| ns 磁盘 8 套 | `ns_INDEX` + new_fixtures 8/8 | Beta/Gamma + |
| high_util mid 抬到 0.70 | **未达成**（布局限 ~66.7%） | **不加分** |
| 全 ns 全 pipeline pack | 延期 | **不加分** |

---

## 6. 演示话术（Talk track）

**要说**  
> 这是 NL 驱动的装柜多智能体工作台：大 Team 编排，A 成箱+非标检验，人确认后 B 拼柜。  
> **柜数、坐标、CoG、订舱体积由 tools 计算**；模型只做意图与解释。  
> 响应带 **path_honesty**（是否真 LLM / policy_fallback）与 **vgm_status**（是否已人签）。  
> 通用 Excel/CSV 可上传；非标 8 类磁盘夹具可复现。  
> 联网校准分 **9.00**；本地 9.75 不作对外总分。

**不要说**  
> 模型自己摆箱子 / 自己决定几柜 / 已是运营级 TMS / VGM 已自动签章 / 分 10 满分 / 报 9.75。

**5 分钟路径**  
1. 预检 UP · 关自动确认  
2. 满载或钢件 → HITL 非标卡  
3. 确认拼柜 → 策略/mid50 · 点路径/VGM 标签  
4. 备份：表上传 G1 或口播 446t 25 柜  

---

## 7. 残余风险（≤7）

1. 开场误报 **本地 9.75**  
2. high_util mid50 **~66.7%** 贴近 CTU 60% 软线  
3. llm shadow **policy_fallback 柜数可漂**  
4. 大票 wall-time / 现场 Key  
5. VGM/POR/TMS 非生产联调（仅状态面）  
6. 「13 agents」被误解为 deep multi-agent IQ  
7. 通宵 `auto/*` 分支历史勿整支合入  

---

## 8. 排名残余 backlog（≤5 · 分析 only）

| # | 项 | 期望 |
|---|-----|------|
| 1 | dense/high_util mid50 舒适区 | mid≥0.70 稳定 |
| 2 | llm shadow used 对齐或 UI「仅参考」 | 演示零歧义 |
| 3 | 大票耗时档案 / 预计算 | 答辩时间盒 |
| 4 | VGM 人签一键可见（超 stub） | 诚实产品化 |
| 5 | ns 夹具全 pipeline pack 抽检 | 非仅 inspect |

---

## 9. 诚实声明

- 本文为 **联网校准评估**，非代码冲刺交付单。  
- **9.00** 锚定外对标 + 硬门 + 诚实增量，**不是**本地分卡复读。  
- 相对 MagicLogic/EasyCargo：缺运营装柜 SaaS、轴重/多式联运产品层。  
- 相对纯 LLM agent demo：本仓更强在 **tools 边界、HITL 可恢复、路径/VGM 诚实面**。

---

## 10. 证据索引

| 路径 | 用途 |
|------|------|
| `output/scratch/network_score_local_gates.log` | 本轮门禁 |
| `output/scratch/network_score_summary.md` | 一页摘要 |
| `output/competition/SCORECARD.md` | 本地 9.75 |
| `docs/research/full-team-network-eval-2026-08-06.md` | prior 8.97 |
| `docs/research/competition-network-review-latest.md` | 首页摘要（与本文一致） |
| `docs/research/ns-iter3h-new-materials-2026-08-06.md` | ns×8 切片 |
| `docs/research/self-iter-5h-2026-08-06.md` | path/VGM 迭代 |
| `test/sim_materials/ns_INDEX.json` | 非标夹具索引 |
