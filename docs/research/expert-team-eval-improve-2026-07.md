# 专家 Team 联网评估 · 找改进点

**日期**：2026-07-29  
**方法**：4 路专家视角 × 联网检索 × 对照 `packing_assistant` 现状  
**基线**：单 Team 闭环 · What-if · POR 单 · 绑扎工单 · t60/t80 ship_ok

---

## 0. 综合裁决

| 维度 | 评分 | 一句话 |
|------|------|--------|
| 装载内核 / CoG | **A-** | 对齐 CTU 中段与横偏；LNS/配额到位 |
| Agent 闭环 / Harness | **A-** | 有界 replan 符合 harness 工程学；trace 可再厚 |
| What-if / 决策智能 | **B+** | 有场景 what-if，缺 **NL→约束** 与 Pareto 选点 |
| 航运/合规交付物 | **B** | VGM 草稿+绑扎单有；缺 Excel/照片证据包 |
| 评测 / CI | **B** | 脚本全；黄金 t80 依赖本地物料文件 |
| 观测 / 运营 | **B-** | SSE/OTEL 有；缺 KPI 看板与失败归因库 |

**结论**：内核与闭环已达「可演示 + 可出运讨论」；最大增量在 **决策交互（NL what-if / Pareto）**、**交付物（Excel 装柜单）**、**评测硬化（黄金集入库 + harness eval）**。

---

## 1. 四路专家意见

### 1.1 论文 / OR 专家

**联网要点**
- OptiGuide：LLM 改优化输入 → 求解器重跑 → 自然语言解释；**不替代求解器**。  
- 多目标：柜数 / 服务水平 / 成本 trade-off 需可解释。  
- CLP：支撑、CoG、多起点、LNS 仍是主路径。

**对照我们**
| 已对齐 | 缺口 |
|--------|------|
| 求解器写坐标 | NL 一句话 what-if（现为固定 scenario 枚举） |
| plan_diff | 缺「推荐选哪版」的评分器 |
| mid50 目标 | 缺 Pareto 前沿（N0 vs mid50 vs 空隙） |

**建议（按 ROI）**
1. **NL What-if 解析器**：`锁两柜` / `不要超长` → 映射到 scenario + options（仍求解器重算）。  
2. **方案评分卡**：`score_plan(state)` 统一 mid50/lat/can_fit/ship_ok/util → what-if 自动标「更优」。  
3. 轻量倾覆分（可选，非 FEM）。

---

### 1.2 GitHub / Harness 专家

**联网要点**
- *Harness engineering*：上下文、工具边界、验证环、权限、eval 决定成败，而非单模型。  
- 有界 loop（时间/轮次/CI 门闸）是生产共识。  
- Planner–Generator–Evaluator 多 Agent 模板普遍。

**对照我们**
| 已对齐 | 缺口 |
|--------|------|
| 单 Team 内/外环有界 | critic 理由未沉淀为「失败模式库」 |
| tools_used / SSE | 缺标准化 **eval harness**（固定 case 矩阵 + 门禁） |
| skills_registry | fail-loud 未全面覆盖 |

**建议**
1. **`eval/cases.yaml` + `scripts/eval_harness.py`**：矩阵 case（tiny/t30/t60/t80）× 断言（can_fit, mid50≥0.55, lat≤0.08, ship_ok）。  
2. **replan 归因日志**：`replan_reasons[]` 写入 artifacts，周汇总 Top 失败原因。  
3. Skills：关键 tool 缺失直接 raise，不静默降级。

---

### 1.3 航运 / CTU 专家

**联网要点**
- 箱内：中段质量、横平、填缝、垫梁、绑扎。  
- 箱外：VGM（SOLAS）、船上 lashing 手册——边界勿混。  
- 交付：装柜图 + 清单 + 加固说明。

**对照我们**
| 已对齐 | 缺口 |
|--------|------|
| mid50/lat、secure_work_order、0.25P | POR 单仅 JSON/前端，**无 xlsx 一键导出** |
| VGM 草稿须人签 | 无「装柜完成检查表」勾选工件 |
| 侧视空隙标注 | 总览/前端 3D 未同步标垫梁 |

**建议**
1. **导出包**：`export_shipment_pack(session)` → xlsx（POR+绑扎）+ 侧视 PNG zip。  
2. **检查表工件** `pre_ship_checklist.v1`：VGM 签/绑扎确认/照片位（HITL 勾选）。  
3. 保持不上船侧力学。

---

### 1.4 土木 / 钢结构出运专家

**联网要点**
- 铁架空心 → 外廓%低正常；订舱双口径。  
- POR 溯源、工厂/工地分票、超长分柜。  
- 现场以实测与加固为准。

**对照我们**
| 已对齐 | 缺口 |
|--------|------|
| 双口径 N0/3D、crate_passthrough | 业务情景「龙申 1 柜 / 工厂 2 柜」未产品化预设 |
| part_no 字段 | 缺「按批次/目的地」自动分票 what-if |

**建议**
1. **业务 preset**：`longshen_1c` / `factory_first_2c`（锁柜+过滤规则）。  
2. POR 单按 destination 分 sheet。  
3. 演示路径：preset → pipeline → what-if 锁柜 → 导出包。

---

## 2. 差距热力图（相对「生产级装柜 Agent」）

```
内核 CoG/LNS     ████████████░░  85%
单Team闭环       ████████████░░  85%
What-if          ████████░░░░░░  65%  ← 有API，NL/评分弱
合规工单         █████████░░░░░  70%
交付导出         ████░░░░░░░░░░  40%  ← 最大业务缺口
黄金Eval         ███████░░░░░░░  55%
观测KPI          ██████░░░░░░░░  50%
业务preset       █████░░░░░░░░░  45%
```

---

## 3. 改进 backlog（可执行）

### P0 · 本周（评委/业务立刻感知）

| ID | 改进 | 验收 |
|----|------|------|
| E1 | **NL What-if**：「锁 2 柜」「去掉超长」→ 解析为 scenario+options | 5 句中文用例全过 |
| E2 | **方案评分卡** `score_plan` + what-if 标 winner | after.score ≥ before 时标「更优」 |
| E3 | **导出包** POR+绑扎 xlsx + 侧视路径列表 | 一键 zip/目录 |
| E4 | **eval harness** 固定 3 case 门禁 | CI 无本地 t80 也能跑 tiny+synthetic |

### P1 · 两周

| ID | 改进 | 验收 |
|----|------|------|
| E5 | replan 归因写入 `output/runs/*/replan_log.json` | 可统计 Top 原因 |
| E6 | 业务 preset 龙申/工厂 | demo 一键 |
| E7 | 前端 3D/总览同步垫梁色 | 与侧视一致 |
| E8 | pre_ship_checklist HITL | 勾选后才 ship_ok 终态（可选开关） |

### P2 · 后放

- 引擎 A/B 每跑必出报告  
- VGM 真提交 / 照片证据  
- 运价钩子  
- 完整倾覆仿真  

---

## 4. 与「已做」对齐（避免重复）

| 已有 | 专家仍要的增量 |
|------|----------------|
| What-if 固定情景 | → NL 解析 + 评分卡 |
| POR JSON | → Excel 导出 |
| t80 脚本 | → 合成 case 进 CI（不依赖大文件） |
| secure_work_order | → 检查表 + 导出 |
| 单 Team 闭环 | → 归因日志 |

---

## 5. 推荐立刻动手的一条 workflow

```text
E1 NL What-if 解析
  + E2 score_plan 标更优
  + E4 eval harness（tiny 合成 20t）
→ 一次 PR 可演示「专家建议闭环」
```

---

## 6. 参考入口（联网）

- OptiGuide 论文 / 代码：arXiv 2307.03875 · github.com/microsoft/optiguide  
- NVIDIA cuOpt AI agent what-if 叙事  
- Awesome Harness Engineering / Agent harness 评测闭环  
- CTU / VGM / 绑扎实务（箱内 vs 船上边界）  

---

*本评估为多视角交叉结论，非法律合规意见。*
