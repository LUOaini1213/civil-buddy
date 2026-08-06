# 比赛/Agency 分阶段 Plan · 对齐 v0.6.4

> 与「Phase 0–4」草案对齐：保留其逻辑，**映射到现有大 Team⊃A/B + IntentSpec + tools**，并标明**不伤 Agent 叙事**的讲法。  
> Phase 0 工件：`packing_assistant/phase0_benchmark.py` · `scripts/run_phase0_baseline.py`

---

## 0. 总原则（叙事安全）

| 原则 | 说明 |
|------|------|
| Agent = 目标 + 工具 + 有界决策 + 可观测 | 不是「LLM 写坐标」 |
| 主路径默认 `steps` | 确定性多智能体流水线 = 可解释 Agency |
| `llm_toolcall` | 加分项 / 影子评测，不默认 |
| 领域工具打磨 | 服务 Agency，不是取代「主循环」叙事 |
| 大⊃A/B | 直接对应 Phase 3「Supervisor + 专业子 Agent」——**已基本完成，Phase 3 是打磨不是从零** |

---

## 1. 草案 vs 现状映射

| 草案阶段 | 你们已有 | 缺口 / 本阶段真正要做 |
|----------|----------|------------------------|
| **P0 对齐与基线** | eval_harness、workteams 影子、KPI、t30/t80 料 | **统一成功标准权重**；**≥20 可自动 case**；**一页基线报告**（见 Phase 0 脚本） |
| **P1 核心 Agency** | big_team 闭环、replan_critic、HITL checkpoint、tools | 轨迹「Plan-Act-Observe-Reflect」**对外更可读**；工具错误恢复率量化；体积路径可靠 Tool |
| **P2 长程** | replan 有界、session resume、agent_steps | 显式 subgoal/milestone；supervisor 只收摘要；记忆层仍薄 |
| **P3 多 Agent + 领域** | **组织已落地**；CoG/叠装/双利用率 | 路由可解释打磨；CTU/空隙规则更锋利；按难度动态升维（可选） |
| **P4 打磨** | smoke、CI、Docker、export 草稿 | pass@k、对抗 case、token/步数预算、提交封装 |

**结论**：草案时间线合理；**Phase 3 不应从零建多 Agent**，应写成「协作可解释性 + 领域工具锋利度」；**Phase 1 的体积/叠装**定位为 **可靠 Tool** 正确。

---

## 2. Phase 0 成功标准（评分权重假设）

若赛方未公布细则，采用下列 **可辩护默认权重**（可改 JSON）：

| 维度 | 权重 | 自动代理指标（本仓库） |
|------|------|------------------------|
| **任务成功** | 0.30 | `can_fit` 且（若要求）柜数/锁柜约束满足；无硬 error |
| **长程完成** | 0.15 | 走完 A→B→finalize；`phase` 非半残；HITL 后续可 resume（子集测） |
| **工具使用质量** | 0.20 | 有 tools 轨迹；`illegal_tool_calls=0`；booking/体积字段自洽（软） |
| **多 Agent 协作** | 0.15 | 轨迹含 A 节点 + B 节点；有 critic/replan 则记协作事件 |
| **效率** | 0.10 | 步数、耗时；相对基线不爆炸 |
| **解释性** | 0.10 | `agent_steps` 可读；intent_spec / messages 非空 |

加权分 = Σ (维度分 × 权重)，维度分 ∈ [0,1]。  
**「赢」的假设**：总分 ≥ 0.75 且任务成功维度 ≥ 0.80。

配置：`test/phase0/success_criteria.json`  
实现：`phase0_benchmark.SUCCESS_CRITERIA`

---

## 3. Phase 0 评测集设计

| 类型 | 数量目标 | 来源 |
|------|----------|------|
| 仿真物料 short | ~10+ | `test/sim_materials/*` 小票 |
| 重量/体积边界 | ~4 | weight_bound / volume_bound / near_payload / overweight |
| t30 风格 | 6 | t30_* |
| NL/锁柜意图 | 4+ | 同料 + 不同 user_input / max_containers |
| 恢复/长程标签 | 子集 | 期望 replan 或 HITL 路径（auto 下测闭环完整） |

**≥20 自动 case**：由 `build_phase0_cases()` 从 INDEX + 合成意图生成。  
标签：`short` | `long` | `nl` | `lock` | `boundary` | `stack` | `recovery`

---

## 4. Phase 0 基线怎么跑

```bash
# 快速（≤12 case，CI/本周每日）
python scripts/run_phase0_baseline.py --quick

# 完整（全部可解析 case，约 20–40）
python scripts/run_phase0_baseline.py

# 仅报告已有 json
python scripts/run_phase0_baseline.py --from-json output/phase0/baseline_latest.json
```

产出：

- `output/phase0/baseline_<ts>.json` — 全量明细  
- `output/phase0/baseline_latest.json` — 最新  
- `output/phase0/BASELINE_REPORT.md` — **一页基线报告**

---

## 5. Phase 1–4 修订要点（避免跑偏）

### Phase 1（核心 Agency）

- **主循环**：已是 bootstrap → loop → tail；加强 **对外 Reflect 字段**（每步 observe 摘要写入 step）。  
- **工具 ≥95%**：对 booking/bin3d/cog 做 **tool-level 单测 + 调用失败 fallback**。  
- **失败 replan**：已有 critic；补 **失败 taxonomy** 与恢复成功率统计（接 Phase 0 报告）。  
- **Checkpoint**：已有；Phase 1 验收改为「长任务 HITL 断点续跑 100%」。

### Phase 2（长程）

- Subgoal：把 N0 / 成箱 / 首装 / 风险门 标成 **milestone 状态机**。  
- 记忆：`intent_spec` + `packing_options` + replan_log = 工作记忆；可加 `decision_log[]`。  
- 摘要协议：critic/子 Team **只回 summary dict** 给大 Team（防上下文爆）。

### Phase 3（多 Agent + 领域）

- **已有 Supervisor+A/B** → KPI 变成「路由是否合理、简单任务是否不升维」。  
- 领域：体积路径修复、空隙/承重/CTU 提示进 risk 解释。  
- RAG 仅当赛题考规范条文时再上。

### Phase 4

- pass@k（k=3）同 case 重复跑。  
- 对抗：缺尺寸、矛盾、工具抛错。  
- 叙事：前端三层组织图 + agent_steps 抽屉 = 评委可读。

---

## 6. 与「Agent 叙事」是否冲突？

| 动作 | 是否伤叙事 |
|------|------------|
| Phase 0 基线、量化成功 | **加强**（能证明） |
| 默认 steps + 工具可靠 | **加强**（专业 Agency） |
| Phase 3 说「我们从零做多 Agent」 | **伤害**（假）→ 应说「协作已就绪，打磨路由与领域」 |
| 把体积修复说成「唯一主路径」 | **伤害** → 应说「主循环调用的可靠 Tool」 |

---

## 7. 本周 Phase 0 验收清单

- [x] 成功标准权重文档 + JSON  
- [x] ≥20 可自动 case 构建器  
- [x] 基线跑批脚本 + 一页 MD 报告  
- [x] quick 基线可跑；报告含 **失败账本** 驱动 P1  
- [x] 主路径声明：`steps` 默认（README / ARCHITECTURE）  
- [x] CI：`run_phase0_baseline.py --quick`  
- [ ] 全量基线（含 t30/t80）至少跑通一轮并归档报告  
- [ ] （可选）填入真实比赛名后重算权重  

**落地总规划**：会话 plan「作战图落地规划」· 顺序 P0 收口 → P1 工具/Reflect → P2 长程 → P3 领域打磨 → P4 赛前。

未知比赛名时，以上默认权重足够启动；有评分表后只改 `success_criteria.json` 即可。

## 8. Phase 1 锚点进度（`t80_long_mix_s297883`）

| 项 | 状态 |
|----|------|
| 根因 | 夹具 1×80t 脏数据 + replan 只加柜不拆箱 |
| 夹具重生 | `n_lines=349` · max 行重 ≤1.2t |
| `cargo_feasibility` | 单件/单箱超 payload 门禁 |
| packing mass_split | 单件超 cap 按质量拆 |
| replan_critic | 超货载 → `box_scheme`，禁空转加柜 |
| 回归 | `python scripts/test_anchor_t80_long_mix.py` → can_fit=True used=5 |

未知比赛名时，以上默认权重足够启动；有评分表后只改 `success_criteria.json` 即可。
