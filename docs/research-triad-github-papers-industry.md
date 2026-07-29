# 三路深研：GitHub · 论文 · 行业（2026-07）

> 由 3 个并行 research agent 完成（GitHub / 论文 / 行业），再综合到本产品。

## 一、现在 Agent 有什么用？

| 角色 | 做什么 | 不做什么 |
|------|--------|----------|
| **产品多智能体**（material→box→loader→evaluator→risk→visualizer） | 把「材料表 → 成箱 → 3D 摆柜 → 订柜 N0 → 合规/重心 → 视图」跑成**可交付装柜方案** | 不用 LLM 编坐标；不替代 CTU 验箱/绑扎证书 |
| **开发 Agent 闭环**（审计→改代码→冒烟） | 按 GitHub/论文/行业缺口改 `bin3d`/`cog`/评分 | 不替代人工验收出运 |
| **商业价值** | 销售预估柜型、工厂 HITL、合规预检、claim 举证材料 | 不替代验船师 FR 绑扎计算 |

**一句话**：Agent 把**确定性工具**串成流程；叠高/60-50/间隙是引擎能力；Agent 负责编排、评估、风险叙事与人机确认。

### 当前已可用的价值

1. **可叠优先叠高** + 限高/限层（对齐层/塔装载文献与 skjolber LAFF）
2. **支撑比 + 绑扎间隙**（对齐 jerry/hyperpack 思路与 CTU 加固余量）
3. **CTU 纵中 60/50 + CoG 软/硬钩子**（GitHub 少有，是我们差异点）
4. **multi_start + CoG 选优**（轻量；论文 GRASP 的简化版）
5. **双利用率订柜**（booking vs outer，防虚高）
6. **HITL / SSE / 会话**（销售-工厂确认闸门）
7. **结构半严格校核**（成箱，非纯摆柜）

---

## 二、GitHub 要点

| 仓库 | 启发 |
|------|------|
| [skjolber/3d-bin-container-packing](https://github.com/skjolber/3d-bin-container-packing) | LAFF+多层；已可作后端；CoG/support_ratio 仍在我们侧 |
| [jerry800416/3D-bin-packing](https://github.com/jerry800416/3D-bin-packing) | `support_surface_ratio` + 四点支撑；最接近我们 support 语义 |
| [timschmidt/hyperpack](https://github.com/timschmidt/hyperpack) | clearance 校验 + multi_start + EP/LAFF 组合（Rust，借思想） |
| Smart-Stowage 类 | LLM+启发式双引擎；CoG 公式；**不可**让 LLM 独占坐标 |
| OR-Tools | **无**成熟 3D 装箱；维护者强调支撑稳定性 |

**差异**：GitHub 几乎没有 **CTU mid50 质量比** API → 我们 `cog.py` 是产品护城河之一。

---

## 三、论文要点

- **Bortfeldt & Wäscher**：CLP 约束谱系（支撑/承重/稳定/CoG）
- **Alonso 等**：多柜 + 重量/轴荷/CoG/动态稳定（间隙、邻高）
- **Ramos / Montes-Franco 2025**：力学平衡 + GRASP
- **DRL（O4M-SP, PCT…）**：支撑/承重作 **action mask**，不单靠学物理

**算法阶梯**：EP/层/墙构建 → GRASP → ILP →（可选）DRL  
**稳定阶梯**：全支撑 → 面积比 → CoM∈凸包 → 静力平衡 → 动力学

---

## 四、行业（CTU）要点

| 规则 | 实践含义 |
|------|----------|
| **60/50** | ≥60% 货重在柜长中段 50% |
| 纵偏 | 一般 ≤±5% 柜长（特殊 ≤±10%） |
| 竖向 CoG | 宜低于半舱高 |
| 重下轻上 | 层堆码承重 |
| 空隙 | 水平累计空隙宜 ≤约 **15cm**，否则加固 |
| 载荷 | ≤ payload；集中载荷垫梁到纵梁 |
| 软件对标 | EasyCargo：不可叠/重心/轴荷/HITL 报告 |

---

## 五、可执行路线图（映射到我们的 Agent/工具）

| 优先级 | 工作 | 归属 |
|--------|------|------|
| **P0 已做** | prefer_stack / 限层 / clearance / support_ratio / mid50 / multi_start CoG | bin3d + cog + loader |
| **P0 下一拍** | 出运模式：mid50&lt;0.60 或 lat_ecc 过大 → risk **block** | risk_compliance + evaluator |
| **P1** | 四点/CoM-in-hull 支撑；下层承重 kg | bin3d `_stack_ok` |
| **P1** | 空隙>15cm 检测 + 可视化高亮 | risk + visualizer |
| **P1** | 集中载荷/垫梁提示（钢结构） | risk + structure |
| **P2** | 完整 GRASP/RCL 局部搜索 | bin3d multi_start |
| **P2** | 力学/动态指标离线报告 | risk（非热路径） |
| **P2** | LLM 只做文案/方案评论 | evaluator 旁路 |

---

## 六、推荐的行业工作流（多智能体）

```
销售询价 → Loader 草案 → Risk(CoG/间隙) → Evaluator 门禁
         → Visualizer 3D/报告 → HITL 工厂确认
         → 成箱结构/VGM 摘要 →（FR 另出验船师包）
```

钢结构出口优先序：柜型 → 垫梁集中载 → 60/50 → 近零空隙+支撑 → 绑扎 MSL → 再谈利用率。
