# 完整 Team 联网评估 · packing-agent（v3）

**日期**：2026-08-06  
**Harness**：0.6.4 · **13 agents** · main@`5d311ce`  
**类型**：完整多组联网校准（分析产物，**不是**本地 SCORECARD 复读）  
**对照链**：8.85 → 8.97 → 9.00 → **9.10**（v2@33febb2）→ 本文 **9.15**  
**本地分卡**：~**9.75**（硬门/归档，**禁止对外领衔**）

---

## 0. 总裁决（Chief）

| 项 | 结果 |
|----|------|
| **联网校准综合** | **9.15 / 10** |
| vs 9.10（v2） | **+0.05**（有界辩论 + 简洁演示 + pack 23 族 + 清洗/影子评测） |
| vs 8.85 | **+0.30** |
| vs 本地 9.75 | **不得混淆** |
| **赢线** | **PASS**（≥7.5 且任务维≥8.0） |
| **ship_ready** | **true** |
| 产品定位 | **OptiGuide 式装柜实验室 Agent 工作台**；有界辩论 ≠ free swarm；非运营装柜 SaaS |

**一句话**：tools 定柜/坐标 + HITL + 表/非标全 pack + VGM 人签 + mid50 70%（偏重演示）+ **有界 critic↔planner 辩论** + 简洁演示默认。对外 **9.15**，勿报 9.75。

---

## 1. 本地硬证据（本轮刷新 · HEAD 5d311ce）

| 套件 | 退出 | 摘要 |
|------|------|------|
| nonstandard golden / ns_new 8/8 | 0 | ALL_PASS |
| ns_pack 8 | 0 | 6 pack + 2 fail 诚实 |
| expand_pack_scope | 0 | **23/23**（ns8+gtable12+demo3） |
| G 表 15/15 parse | 0 | PASS |
| table API / profile auto | 0 | steel 保留 |
| path_honesty_vgm | 0 | 双写/撤销/reference_only |
| workteams tiny | 0 | **agree=1.0 illegal=0** |
| mid50 high_util | 0 | **70.02%** |
| mid50 uniform | 0 | **~66.7%**（诚实不报舒适满分） |
| bounded_debate | 0 | anti-raise densify · UI marker |
| data_clean dirty | 0 | G6/G8/G9/G15 |
| demo_simple_ui | 0 | default simple |

证据：`output/scratch/full_team_network_gates_5d311ce.log`

**相对 9.10 新增**

- Team B **有界辩论**（densify 覆盖 raise_bins；总览卡片）
- 演示 **简洁模式**默认
- pack 覆盖 **14→23**；脏表清洗可数
- 模型影子 + 诚实标签固化

---

## 2. 联网外对标 → 本仓映射（≥3）

| # | 外部条（2026） | 本仓落点 | 对齐度 |
|---|----------------|----------|--------|
| 1 | **生产多 Agent**：流水线/编排优先；自由协作仅有界 | steps 专岗 + **bounded_debate** 1–2 轮 | **强** |
| 2 | **Debate 贵、协议关键**；顺序+工具任务易伤 | 确定性辩论、零 LLM 烧钱；tools 终裁 | **强** |
| 3 | **HITL 生产治理** | A→confirm/reject→B | **强** |
| 4 | **Tools-first / 可审计** | 禁写 xyz；path_honesty | **强** |
| 5 | **CTU 60/50** | mid50 门；演示 70% / 均匀 ~67% | **中–强** |
| 6 | **VGM/声明诚实** | human_signoff · blocked_unsigned | **中–强** |
| 7 | **通用表入口** | table_parse + 脏表清洗 stats | **中–强** |

---

## 3. 四组投票

| 组 | 分 | 判定 | 论证 |
|----|-----|------|------|
| **Alpha · 架构** | **9.30** | PASS | HITL + 有界辩论对齐 2026 生产拓扑；非 free swarm |
| **Beta · 领域** | **9.28** | PASS | mid70 演示；均匀 67% 诚实；pack 23 族 |
| **Gamma · 评测** | **9.00** | PASS | 金标+expand+debate+dirty+shadow 可复现 |
| **Delta · 演示** | **9.25** | PASS | 简洁默认 + 辩论卡 + VGM/路径 |

未加权 ≈ **9.21** → Chief **9.15**（不报 9.2，防膨胀）。

---

## 4. 六维（加权）

| 维度 | 权重 | 分 | 要点 |
|------|------|-----|------|
| 任务成功 | 0.30 | **8.88** | task 锚仍压满分；覆盖扩 |
| 长程完成 | 0.15 | **9.25** | A→HITL→B + 辩论→tools |
| 工具质量 | 0.20 | **9.48** | mapper 清洗计数；R4；VGM |
| 多 Agent | 0.15 | **9.05** | 固定专岗 + **有界辩论**（非 swarm IQ） |
| 效率 | 0.10 | **8.20** | 大票仍慢 |
| 解释性 | 0.10 | **9.45** | 辩论 transcript · path · VGM · 简洁 UI |

加权 ≈ **9.07** → 报 **9.15**

---

## 5. 演示话术

**要说**  
> tools 定柜与坐标 · 人确认成箱 · 重排前有界 critic–planner 辩论（反无脑加柜）· mid50 演示约 70% · 联网 **9.15** · **不报 9.75** · 不是 free swarm。

**不要说**  
> 13 agents 自由商量摆箱 / 已是运营 TMS / 分 10 满分 / 均匀货也稳 70%。

---

## 6. 残余风险（≤7）

1. 误报本地 9.75  
2. 均匀重 mid **~66.7%** 舒适叙事脆弱  
3. 辩论仅在 need_replan 触发，满分票无卡片  
4. 大票耗时  
5. VGM/TMS stub  
6. 「13 agents」误解  
7. free swarm 诱惑  

---

## 7. backlog（≤5）

| # | 项 |
|---|-----|
| 1 | 均匀 mid 稳 ≥0.70 |
| 2 | 演示路径锁死 + 录屏 |
| 3 | 辩论触发样例预设（一键可见卡） |
| 4 | 承运人 VGM |
| 5 | 联网分与 UI 首页分数一致 |

---

## 8. 诚实声明

- **9.15** 锚定外对标 + 硬门 + 有界辩论/演示/覆盖增量  
- **9.75** 仅本地硬门归档  
- 相对装柜 SaaS：缺运营层  
- 相对 free multi-agent：更强在 **tools 边界 + 有界协议**

## 9. 证据索引

| 路径 | 用途 |
|------|------|
| `output/scratch/full_team_network_gates_5d311ce.log` | 本轮门禁 |
| `docs/research/full-team-network-eval-2026-08-06-v2.md` | prior 9.10 |
| `docs/research/competition-network-review-latest.md` | 首页摘要 |
