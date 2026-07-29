# 评估智能体 · 联网评审报告

模块：`packing_assistant/agents/evaluator.py`  
对照：3D-BPP / 装载 KPI 文献与工业实践、CTU 配载关切、钢结构铁架业务特征  

**总评：PASS（偏业务）— 指标拆分与行业「多利用率 KPI」同向，硬约束优先正确；评分权重与阈值属经验设计，非唯一标准。**

---

## 一、总

| 维度 | 判定 | 说明 |
|------|------|------|
| 硬约束（装下/超重） | **强** | can_fit、unpacked、weight>1 重扣 |
| 利用率 KPI 拆分 | **强** | 订柜有效体积 ≠ 外廓；重量；底面积 |
| 与钢结构虚高体积 | **对齐** | 禁止 outer 顶替 booking；外廓低仅轻罚 |
| 与学术「单一 space util」 | **有意识偏离** | 对铁架业务是优点 |
| 与 CTU 安全 | **部分** | 安全细项在 risk，评估侧重装载经济性 |
| 可解释 / replan | **中上** | suggestions + need_replan≤2 |

**综合（10 分）约 7.5～8.0（方案评估器）**；若当「全球最优 3D-BPP 基准打分器」约 5～6。

---

## 二、分：联网对照

### 1）行业/学术在评什么

装载与 3D bin packing 实践中常见 KPI：

| 指标族 | 含义 | 工业用途 |
|--------|------|----------|
| **Volume / space utilization** | 货或包络占柜容积 | 少柜、降运费 |
| **Weight / payload utilization** | 货重 / 额定载重 | 吃满限重、VGM |
| **Floor / base utilization** | 底面积占用 | 绑扎、稳定性相关 |
| **#containers / cost** | 柜数、费用 | 主决策 |
| **Feasibility** | can_fit、无溢出 | 硬约束 |
| **Stability / COG**（常另模块） | 偏心、重货在上 | 安全 |

文献与优化软件常把 **volume + weight** 作为多目标；钢结构/异形货若只用「外廓实心体积利用率」，会系统性 **虚高或虚低**。

### 2）你们评了什么

```text
硬分：can_fit / unpacked / 超重 / 体积可疑 / 结构不通过|待详设
软分：booking_vol 35% + floor 20% + weight 45%  → util_composite
外廓 outer：只展示 + 轻提示，不主导订柜分
融合：硬分 ×0.55 + 综合利用率 ×0.45（能装下时）
```

| 与行业对照 | 评价 |
|------------|------|
| 可行性优先 | **正确**（装不下先减 40） |
| 重量利用率 | **正确**（工业核心 KPI） |
| 体积拆成 booking vs outer | **强项**，对铁架/空心架比「单一 space%」更诚实 |
| 底面积 | **有价值**，与绑扎/摆满相关 |
| 柜数成本显式目标 | **弱**（靠 N0/replan，评分未直接罚「多用柜」） |
| 稳定性 | **交给 risk**（架构合理） |

### 3）权重与阈值（经验 vs 标准）

| 设定 | 你们默认 | 联网视角 |
|------|----------|----------|
| 重量 45% / 订柜体积 35% / 底面积 20% | 偏 **重货/钢结构** | 合理；轻泡货会压低体积权重不够 |
| weight soft 35% / good 60% | 偏松 | 业务可调；干货常希望更高 |
| space soft 20% / good 40%（订柜有效） | 对铁架 **刻意放宽** | 正确业务判断，勿与 3D-BPP 论文 80%+ 比 |
| outer <25% 仅 −3 | 防「铁架看起来空」误加柜 | **对齐你们订舱叙事** |

**评审：** 阈值不是国际统一标准，但是 **自洽的业务评分**；答辩应说「软目标可配置」，不要说「行业法定及格线」。

### 4）与 CTU / 安全

CTU 更关心：配载、偏心、绑扎、地板集中载荷。  
你们 **risk_compliance** 已做 COG/超重/结构；**evaluator** 偏 **装得下 + 利用是否合理**。  

**分工正确**，评估器不必重复全部安全规则。

### 5）replan 机制

`need_replan` 在装不下时建议加柜，最多 2 轮。  

| 点 | 评价 |
|----|------|
| 有限重试 | 符合工程可控（非无限自治） |
| 结构失败走 REJECT 不 replan 加柜 | **正确**（加柜解决不了结构） |
| 未对「能装但柜数过多」强优化 | 经济最优非主目标 |

### 6）已知弱点（联网 + 代码）

| P | 问题 | 影响 |
|---|------|------|
| P1 | 兼容字段 `space_subscore` 实际是订柜体积分，易被外部误读 | 对接混淆 |
| P1 | 评分未显式「柜数成本」项 | 多柜便宜路径不直接惩罚 |
| P2 | 轻泡货权重仍偏重量 | 类型未自适应 |
| P2 | `booking_vol_util` 可 >1（cap 9.99）时子分仍高 | 极端数据 |
| P2 | 与 risk 分两套 score | 需用户看 decision 链 |

---

## 三、总

### 一句话口径（答辩）

> 评估智能体按 **装得下、不超重、结构/详设合格** 为硬约束，  
> 再用 **订柜有效体积 + 重量 + 底面积** 评经济性；  
> **外廓摆柜率不计入订舱分数**，避免钢结构空心架被误判为「没装满」。  

### 与「结构计算」联网评审的关系

| 模块 | 角色 |
|------|------|
| structure | 箱是否安全（详设参数） |
| evaluator | 方案是否值得 / 要不要 replan |
| risk | 出运合规总闸 |

三者叠在一起才接近工业「计划→校核→放行」。

### 建议 → 已落地（代码）

> **复核（2026-07-28）**：对照 `packing_assistant/agents/evaluator.py` + `orchestrator.py` 默认 targets，下列六项均已在代码中生效；无未闭环缺口（Gaps=[]）。

| 优先级 | 动作 | 状态 |
|--------|------|------|
| 叙事 | 固定三指标表 `metrics_table` | ✅ evaluation.metrics_table（booking/weight/floor + outer `in_score=false`） |
| P1 | `space_subscore` 标废弃别名 | ✅ space_subscore_deprecated + means=booking_volume_subscore |
| P1 | 权重可配置 | ✅ targets.evaluation_weights / state.evaluation_weights |
| P2 | binding 自适应权重 | ✅ volume/weight/both 三套（`_resolve_weights`） |
| P2 | 柜数经济性 | ✅ used>N0 可配置扣分（penalize_extra_containers / extra_container_penalty） |
| 不做 | outer 进订舱主分 | ✅ 仍不进（仅展示/轻提示 −3） |

配置示例（主控 targets 或 state）：

```python
state["evaluation_weights"] = {
    "booking_volume": 0.50,  # 轻泡可加大
    "floor": 0.15,
    "weight": 0.35,
}
# 或关闭多柜惩罚
state["orchestrator"]["goals"]["targets"]["penalize_extra_containers"] = False
```

---

*本报告为工程对照，不构成某标准符合性认证。*
