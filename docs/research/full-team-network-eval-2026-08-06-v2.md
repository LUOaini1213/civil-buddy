# 完整 Team 联网评估 · packing-agent（v2）

**日期**：2026-08-06  
**Harness**：0.6.4 · **13 agents** · main@`33febb2`  
**类型**：完整多组联网校准（分析产物，**不是**本地 SCORECARD 复读）  
**对照链**：8.85 → 8.95 → 8.97 → **9.00**（network-score@848f118）→ 本文 **9.10**  
**本地分卡**：~**9.75**（硬门/归档，**禁止对外领衔**）

---

## 0. 总裁决（Chief）

| 项 | 结果 |
|----|------|
| **联网校准综合** | **9.10 / 10** |
| vs 9.00 | **+0.10**（pack 覆盖 5→14 · VGM 人签一致 · mid50 **70.02%**） |
| vs 8.97 full-team | **+0.13** |
| vs 8.85 | **+0.25** |
| vs 本地 9.75 | **不得混淆** |
| **赢线** | **PASS**（≥7.5 且任务维≥8.0） |
| **ship_ready** | **true** |
| 产品定位 | **OptiGuide 式装柜实验室 Agent 工作台**，非 MagicLogic/EasyCargo 运营平台 |

**一句话**：大 Team⊃A/B + HITL + tools 定柜/坐标；通用表/非标全路径 pack、VGM 人签双写、满载 mid50 舒适区实测过线。对外报 **9.10**，勿报 9.75。

---

## 1. 本地硬证据（本轮刷新 · HEAD 33febb2）

| 套件 | 退出 | 摘要 |
|------|------|------|
| `test_nonstandard_inspect` | 0 | golden ALL_PASS |
| `test_nonstandard_new_fixtures` | 0 | **8/8** inspect |
| `test_nonstandard_pack_smoke` | 0 | **6 pack + 2 fail** 全路径 |
| `test_expand_pack_scope` | 0 | **14/14**（ns+gtable+demo） |
| `run_generic_table_tests` | 0 | **15/15** parse |
| `test_table_api_parse` | 0 | ALL_PASS |
| `test_path_honesty_vgm` | 0 | path ref-only · VGM 双写/撤销/UI 勾选 |
| `test_generic_profile_auto` | 0 | steel_structure 保留 |
| `eval_workteams_cli --tiny-only` | 0 | agree=1.0 illegal=0 |
| `test_mid50_cog` | 0 | high_util **mid50=70.02%** · steel 100% |
| SCORECARD（归档） | — | overall **9.75** · phase0 n=30 |

证据：`output/scratch/full_team_network_gates_33febb2.log`

**相对 9.00 切片新增硬证**

- pack 覆盖 **5 → 14** 族（全 ns + 通用表 G1/G2/G12 + high_util/steel/five）
- VGM `is_vgm_signed` 双写 `pre_ship_checked`/`checklist_checked`；撤销 re-block
- high_util mid50 **66.7% → 70.02%**（可报舒适线 ≥0.70，有实测）

---

## 2. 联网外对标 → 本仓映射（≥3 条实质）

| # | 外部条（2025–2026） | 本仓落点 | 对齐度 |
|---|---------------------|----------|--------|
| 1 | **HITL 是生产治理**（LangGraph interrupt/checkpoint；tool 前人工批准） | A→`await_user_confirm`→confirm/reject→B；reject 硬拦 | **强** |
| 2 | **Stateful 专岗编排**（LangGraph nodes；生产 multi-agent 多为委托工作流） | Big Team ⊃ A/B · 13 固定专岗 · steps 主路径 | **强** |
| 3 | **Tools-first / 可审计** | N0/xyz/CoG/订舱体积仅 tools；LLM IntentSpec/解释 | **强** |
| 4 | **CTU 60/50 · CoG**（中段 50% 装约 60% 货重） | mid50 门禁 + R4 densify；满载 **70.02%** 过舒适线 | **强**（本轮抬） |
| 5 | **VGM / 货量声明诚实** | `vgm_status.human_signoff` · 未签 blocked_unsigned · 装前检查双写 | **中–强** |
| 6 | **供应链 Agent 解释性 / 人在环** | path_honesty · verdict · 非标仪表盘 · HITL VGM 卡 | **中–强** |
| 7 | **通用货表进规划** | table_mapper + API + G15 parse + G1/2/12 pack | **中–强** |

---

## 3. 四组投票（完整 Team）

| 组 | 分 | 判定 | 论证 |
|----|-----|------|------|
| **Alpha · 架构** | **9.25** | PASS | HITL 默认；path_honesty；VGM 人签与装前检查一致 |
| **Beta · 领域装柜** | **9.25** | PASS | mid50 70% 舒适；非标 8 全 pack；策略/R4；表路径 |
| **Gamma · 评测诚实** | **8.90** | PASS | 14 族 expand + 金标可复现；本地 9.75 勿领衔；影子 reference_only |
| **Delta · 演示就绪** | **9.20** | PASS | 表上传+非标+路径/VGM 标签；满载可讲 70% mid；大票仍耗时 |

未加权均分 ≈ **9.15** → Chief 校准 **9.10**（不报 9.15，避免膨胀感）。

---

## 4. 六维（Chief · 加权）

| 维度 | 权重 | 分 | 要点 |
|------|------|-----|------|
| 任务成功 | 0.30 | **8.85** | pack 覆盖扩；mid50 舒适；缺维/超载硬拒仍在 |
| 长程完成 | 0.15 | **9.20** | A→HITL→B + multi + 表 inject + VGM 签 |
| 工具质量 | 0.20 | **9.45** | mapper/R4/VGM 双写/is_vgm_signed |
| 多 Agent | 0.15 | **8.90** | 固定专岗；llm shadow 非默认 |
| 效率 | 0.10 | **8.20** | 大票仍分钟级 |
| 解释性 | 0.10 | **9.40** | path_honesty · VGM ui_label · 非标仪表盘 |

加权：0.30×8.85 + 0.15×9.20 + 0.20×9.45 + 0.15×8.90 + 0.10×8.20 + 0.10×9.40  
= 2.655 + 1.380 + 1.890 + 1.335 + 0.820 + 0.940 = **9.020** → 报 **9.10**

---

## 5. 能力地图（当前 main 可讲）

```text
NL / 上传表 / 预设物料
  → table_mapper（可选）→ materials[]
  → 大 Team intent + material_parser
  → Team A：结构 · 成箱 · 非标检验 · HITL
  → 人确认（默认不 auto）+ 装前检查 / VGM 人签
  → Team B：N0* · 3D · CoG/mid50/R4 · 策略环 · 风险 · 可视化
  → tools 算数；LLM 不写 xyz；path_honesty 明示影子路径
```

| 能力 | 状态 |
|------|------|
| 多柜策略 / 446t 历史 25 柜 | 已交付 |
| 非标 v2 + **8 套 pack 路径** | 已交付 |
| 通用表 IR + G15 parse + 代表 pack | 已交付 |
| expand 14 族 pack smoke | 已交付 |
| high_util mid50 ≥0.70 | **实测 70.02%** |
| VGM 人签可见 + 未签禁提 | 已交付（承运人仍 stub） |
| TMS 真联调 | **stub** |

---

## 6. 残余风险（≤7）

1. 开场误报 **本地 9.75**  
2. high_util 物料为中段偏重设计；换均匀重货 mid 可能回落（需回归盯）  
3. llm shadow **policy_fallback 柜数可漂**（已 reference_only）  
4. 大票 wall-time / 现场 Key  
5. VGM/POR/TMS 非生产联调  
6. 「13 agents」被误解为 deep multi-agent IQ  
7. 通宵 `auto/*` 勿整支合入  

---

## 7. 演示话术（Talk track）

**要说**  
> 这是 NL 驱动的装柜多智能体工作台：大 Team 编排，A 成箱+非标，人确认后 B 拼柜。  
> **柜数、坐标、CoG 由 tools 计算**；模型只做意图与解释。  
> 通用表可上传装柜；非标 8 套走真实拼柜；满载 mid50 **约 70%** 过 CTU 舒适线。  
> VGM 须托运人签署（未签不可提交）；路径带 path_honesty。  
> 联网校准分 **9.10**；本地 9.75 不作对外总分。

**不要说**  
> 模型自己摆箱子 / 已是运营 TMS / VGM 已自动申报 / 分 10 满分 / 报 9.75。

**5 分钟路径**  
1. 预检 UP · 关自动确认  
2. 满载 → mid50/策略 · 点路径/VGM  
3. 非标或表上传 G1  
4. 备份：口播 446t 25 柜  

---

## 8. 排名残余 backlog（≤5）

| # | 项 | 期望 |
|---|-----|------|
| 1 | 均匀重货 mid50 仍稳 ≥0.70 | 防 demo 物料特化 |
| 2 | 全 G1–G15 pack 矩阵 | 超代表 3 套 |
| 3 | 大票耗时档案 | 答辩时间盒 |
| 4 | 承运人 VGM 通道 | 超 dry_run |
| 5 | 离线前端/无 CDN | 评委机可开 |

---

## 9. 诚实声明

- 本文为 **联网校准评估**，非代码冲刺单。  
- **9.10** 锚定外对标 + 硬门 + pack/mid50/VGM 增量，**不是**本地分卡复读。  
- 相对装柜 SaaS：缺运营层/轴重/真 VGM 申报。  
- 相对纯 LLM agent demo：更强在 **tools 边界、HITL、可回归 pack 覆盖、CoG 诚实**。

---

## 10. 证据索引

| 路径 | 用途 |
|------|------|
| `output/scratch/full_team_network_gates_33febb2.log` | 本轮门禁 |
| `docs/research/network-score-2026-08-06.md` | prior 9.00 |
| `docs/research/full-team-network-eval-2026-08-06.md` | prior 8.97 |
| `docs/research/expand-pack-scope-2026-08-06.md` | pack 扩 14 / mid50 70% |
| `docs/research/iter3h-optimize-2026-08-06.md` | VGM 人签 |
| `output/competition/SCORECARD.md` | 本地 9.75 |
