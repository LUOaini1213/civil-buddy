# 三路研究纪要：论文 · GitHub · 土木/航运行业  
**日期**：2026-07-29 · 方法：多轮 Web 检索 + 对照当前 `packing_assistant`  
**范围**：3D 装柜 / CoG / Multi-Agent / CTU·VGM·绑扎 / 钢结构出运

---

## 0. 执行摘要（给产品）

| 来源 | 核心共识 | 对我们 Agent 的含义 |
|------|----------|---------------------|
| **论文/OR** | 几何求解器 + 启发式/多起点；CoG 作为硬/软约束；LLM **不写坐标**，写解释与 what-if | 继续 bin3d/LAFF/R0–R4/LNS；LLM 做 NL 修订、diff、工单叙事 |
| **GitHub** | skjolber 3D packing、OptiGuide、LangGraph 多 Agent、仓库/物流 Agent 分工 | 引擎 A/B 已有方向；OptiGuide 式 what-if；角色化 Agent 已对齐 |
| **航运/土木** | CTU 装载、VGM、空隙填缝、集中载荷垫梁、纵中质量、绑扎证据 | mid50/lat、secure_work_order、0.25P 垫梁、ship_ok≠can_fit 正确 |

**一句话**：业界路径是 **「确定性装载内核 + 有界 Agent 闭环 + 合规工件」**，不是再堆一个 LLM 去摆箱。

---

## 1. 论文 / 算法线

### 1.1 经典与近年 CLP（Container Loading Problem）

- **3D 矩形装柜 + 稳定性/支撑**：行业与 OR 综述长期把 *full support / partial support*、层/墙（wall-building）、条带（layer/slab）作为主启发式族。
- **重心约束**：近年工作把 CoG 放进目标或可行域（横向偏心、纵向位置、高度比），与我们的 CTU 60/50、lat、height_ratio 一致。
- **多柜 / 多起点（multi-start）**：对大实例，固定一种序不够；多排序 + 选优是标配（我们已用 stack/floor/mid_heavy 并按规模裁剪）。
- **LNS / destroy-repair**：大规模组合优化里对「最差子结构」局部摧毁再装，比全局重开更划算——对应我们的 **分柜 LNS**。

### 1.2 LLM × 优化（2023–2026）

| 工作/方向 | 要点 | 对照我们 |
|-----------|------|----------|
| **OptiGuide** (Li et al., Microsoft；arXiv 2307.03875；github.com/microsoft/optiguide) | NL → 改优化输入 → **求解器重跑** → NL 解释；what-if；隐私上可不上传专有数据到 LLM | 我们应用 plan_diff、自然语言 revise、**禁止 LLM 写 placements** |
| **InvAgent / Agentic SCM** (2024–2025) | 分层/多阶段库存 Agent，反思与共识 | 主控 + Team A/B + replan_critic 同构 |
| **物流 LLM 工作流** (2025) | Rate/Compliance/Visibility 分工；RAG + 工具调用 | risk / VGM / 绑扎工单 角色化 |
| **MAIW / LangGraph 仓库** (NVIDIA 等) | 多 Agent + MCP 工具层 + RAG | harness 流式 + skills 契约方向一致 |
| **Tool-use 综述** (2025) | OctoTools、MIRROR 反思、TUMIX 测试时 scaling | 有界 replan 轮次 + 批评环已具备雏形 |

**论文侧禁止项（反复出现）**：让 LLM 直接输出 3D 坐标 → 幻觉与不可审计。**我们的红线正确。**

### 1.3 算法侧可吸收（未做/半做）

1. **稳定性仿真轻量层**：除支撑比外，虚拟加速度下的倾覆启发式（行业论文常做简化，不做完整 FEM）。
2. **多目标 Pareto 展示**：柜数 vs mid50 vs 重量 vs 空隙，给 HITL 选点（OptiGuide 精神）。
3. **实例规模自适应**：已做 multi_start 裁剪；可再加「先 R2/R4 再开 multi」日志化 KPI。

---

## 2. GitHub / 工程实践线

### 2.1 装载引擎

| 项目 | 内容 | 对照 |
|------|------|------|
| **skjolber/3d-bin-container-packing** | Java LAFF + brute force；多箱多柜 | 我们 Python LAFF + 可选 skjolber 服务；应保持 A/B |
| **RL 3D BPP 玩具库** | 学习序/放置 | 热路径不适合；可离线启发 |
| **数字孪生 + Gemini 式 JSON 布局** | 视觉/空间推理生成静态方案 | 演示向，非合规主路径 |

### 2.2 Agent 框架

| 项目 | 内容 | 对照 |
|------|------|------|
| **microsoft/OptiGuide** | what-if + 解释层 | 应把「若减一柜/若只装 VMU 铁」做成一键 what-if |
| **LangGraph / CrewAI 物流示例** | 角色 Agent + 工具 | 已是 9 智能体 + replan_critic |
| **供应链 multi-agent 论文开源** | 共识、反思 | ship 外环打回 ≤2 轮已对齐 |

### 2.3 工程教训（从仓库 issue/设计归纳）

- **可旋转 / 不可倾倒 / 超长** 必须是一等公民字段（我们 special_attributes + prefer_bottom）。
- **可视化是验收刚需**（侧视/分柜）——我们已有 visualizer；缺「空隙/垫梁」图层标注。
- **测试黄金集**：固定 seed 60t/80t 比口头 demo 重要——已有 `run_t60_main` / `run_t80_main`。

---

## 3. 土木 · 航运 · 钢结构出运线

### 3.1 装柜与箱内（CTU / 实务）

来自 CTU 实务、ICS/WSC 装箱指南、装柜培训材料的稳定原则：

| 原则 | 行业表述 | 我们实现 |
|------|----------|----------|
| 纵向质量中段 | 重货靠中，避免门端/前端过重 | mid50 / cog_rebalance / LNS |
| 横向平衡 | 左右偏心宜小（常述 ≤5% 量级） | lat + lateral_repair |
| 高度重心 | 过高血压稳性 | height_ratio 门禁 |
| 空隙 | 宜填实；常见气囊/木方/止挡 | secure_work_order void_fill |
| 集中载荷 | 重件垫梁，荷载进纵梁 | 0.25P + footprint 垫梁 |
| 超长件 | 沿柜长、禁竖放、多道绑扎 | 超长标签 + strapping 工单 |
| 可叠/层间 | 支撑充分，禁重压轻失控 | prefer_stack + support_ratio |

### 3.2 船侧 / 箱外（与我们边界）

| 主题 | 要点 | 产品边界 |
|------|------|----------|
| **VGM (SOLAS)** | 无 VGM 不装船；托运人责任 | 我们已有 Method2 **草稿须人签**——保持草稿，不做「真提交」除非对接承运人 API |
| **CSS / CSM / 绑扎桥** | 船上堆码与绑扎手册 | 超出柜内方案；最多导出「建议勿超重柜」 |
| **堆重 / lashing** | 层间 twistlock、杆件角度 | 不进 3D 内核 |

### 3.3 钢结构 / 土木构件出运

| 实务 | 含义 |
|------|------|
| 铁架/钢托空心外廓 | **外廓利用率低不等于货少**——双口径订舱正确 |
| 铝板/型材超长 | 分票工厂 vs 工地；20GP 禁用 | 我们草案已分票 |
| 构件标号 / POR 溯源 | 装柜单按 POR 可追溯 | part_no 字段应贯穿工单 |
| 现场装柜 vs 算法 | 最终以现场加固与实测 VGM 为准 | HITL + WARN 正确 |

---

## 4. 对照表：业界能力 vs 我们现状

| 能力 | 业界/论文 | 我们 | 差距 |
|------|-----------|------|------|
| 3D 装载 | LAFF/层/墙/LNS | ✅ bin3d + R0–R4 + LNS | 可加轻量倾覆启发式 |
| CoG/CTU | mid/lat/height | ✅ | 分柜表已前端；可加 per-cabin 导出 |
| Multi-start | 多 | ✅ 规模裁剪 | KPI 打点 |
| Multi-Agent | 分工+工具 | ✅ 9 Agent + critic | Skills fail-loud 加强 |
| LLM 解释/what-if | OptiGuide | △ plan_diff / NL revise | **正式 what-if 入口** |
| 绑扎工单 | 行业清单 | ✅ secure_work_order | 图上标注空隙 |
| VGM | 真申报 | △ 草稿 | 对接承运商再 P2 |
| 证据包/索赔 | 照片清单 | △ 弱 | P2 |
| 引擎 A/B | skjolber 等 | △ 可选服务 | CI 对比 |
| 黄金回归 | OR 基准 | ✅ t60/t80 | 进 CI workflow |

---

## 5. 反复搜索后的「不要做」清单

1. **LLM 写 xyz 坐标**（论文/OptiGuide/安全审计一致反对）。  
2. **用外廓利用率当订舱唯一 KPI**（钢结构/铁架场景误导）。  
3. **无界多 Agent 闲聊 replan**（成本与抖动；应有界轮次）。  
4. **把船上 lashing 力学全做进柜内引擎**（边界错位）。  
5. **无 VGM 人签就标「可出运终态」**（SOLAS 红线）。

---

## 6. 建议路线图（研究驱动，按优先级）

### 立刻（P0/P1 收口，1–2 周）

1. **What-if 面板**（OptiGuide）：「减 1 柜 / 锁 2 柜 / 不要超长混装」→ 只改 packing_options 或过滤材料 → 重跑求解器 → plan_diff 叙事。  
2. **侧视图标注** secure_work_order 空隙与垫梁件。  
3. **CI**：`test_p0_cog_t80` + `run_t60_main --skip-gen` 进 workflow。  
4. **双口径固定文案**进 finalize 默认段落（订舱 N0 vs 3D 用柜）。

### 下一阶段（P1/P2）

5. 轻量 **倾覆/滑动**评分（非 FEM）。  
6. skjolber **A/B 报告**进每次 t60/t80 产物。  
7. **POR 溯源装柜单**（按 part_no 汇总重量与柜号）。  
8. 会话级 **客户偏好**（优先叠高 / 优先少柜 / 严格 mid50≥60%）。

### 后放（P2）

9. VGM 真提交、索赔照片证据包、运价钩子、完整 GRASP。

---

## 7. 关键参考（检索入口）

- OptiGuide 论文：arXiv:2307.03875 · 代码：https://github.com/microsoft/optiguide  
- OptiGuide 项目页：Microsoft Research OptiGuide  
- skjolber 3D packing：https://github.com/skjolber/3d-bin-container-packing  
- InvAgent / Agentic supply chain：arXiv 相关 2024–2025 多 Agent 库存/供应链  
- CTU / 装箱实务：UNECE CTU Code；ICS/WSC Safe Transport of Containers；UK P&I Carefully to Carry Ch.41  
- SOLAS VGM：承运人/船检 2025–2026 实务综述  
- 物流 LLM 工作流：IJCTT 2025 等（Rate/Compliance/Visibility 分工）

---

## 8. 与 60t/80t 实测的挂钩

| 实测 | 研究解释 |
|------|----------|
| mid50 0.61–0.72、lat 很低、ship_ok | CoG 管线 + LNS/配额有效，对齐 CTU 中段 |
| 外廓 18–20%、订舱体积 12–13% | 空心当量架；双口径正确 |
| risk=WARN + 绑扎 28 项 | 行业「可讨论出运 + 填缝清单」模型 |
| multi_start_n=2 ~20s | 规模裁剪符合「大实例少候选」工程实践 |

---

*本纪要由多轮检索（论文/GitHub/航运土木）交叉归纳，供 Agent 产品路线对齐；非法律合规意见。*
