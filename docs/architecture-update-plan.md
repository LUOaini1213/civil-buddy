# 完整更新方案（已落地）

面向：材料 → 成箱 → **自主定柜** → 拼柜 → 风险 → 出图  

原则：**不写死柜数**；领导「2 柜」仅作某票验收回归，不作系统约束。

---

## 一、联网 Review 共识（已吸收）

| 行业共识 | 系统含义 |
|----------|----------|
| 订柜看 **重量 + 可用/有效体积**，取更紧约束 | `N0 = max(N_weight, N_volume)` |
| 柜理论容积实务 **80–85%** 可用 | `η ≈ 0.82`（`fill_ratio`） |
| 重货/钢材外廓利用率 **40–60% 仍正常** | `outer_space_util` 低 ≠ 没装够 |
| 区分 **货体积 / 包装体积 / 外廓 AABB** | 三层体积 |
| LLM 只解释，数字由规则/算法出 | finalize 润色不改柜数/can_fit |

**核心坑（已修）：** 用 Σ 箱外廓实心订柜 → 空心铁架虚体积 → 柜数被抬高。  
修复重点是 **体积定义与指标拆分**，不是推翻多智能体架构。

---

## 二、目标能力

```text
输入材料清单（可过滤目的地/批次/已发）
  → 自主成箱（标准箱+结构）
  → 自主定柜 N0 = max(重量柜, 有效体积柜) + 3D 校验加柜
  → 自主布局 + 风险 + 三视图
  → 可解释：为何 N 柜、各约束贡献
```

无任何业务 `target_containers = 2`。

---

## 三、架构（保留骨架）

```text
用户输入
    ↓
【主控】意图 / 过滤策略 / 调度（不定死柜数）
    ↓
【团队 A】材料解析 → 结构建议 → 装箱方案
    boxes[] 含：outer + content_m3 + fill_ratio + booking_volume_m3 + structure
    ↓
【确认闸门】展示成箱方案；可改柜型偏好/过滤（可选确认）
    ↓
【订柜引擎】tools/booking.py
    N0 = max( ceil(W/PAYLOAD), ceil(V_eff/(V_cont×η)) )
    ↓
【团队 B】规划(N0) → 装载(从N0递增 can_fit) → 评估 → 风险 → 可视化
    ↓
【主控 finalize】方案评分、解释、图、可选 LLM 摘要（不改数字）
```

---

## 四、关键算法

### 4.1 三层体积

| 层级 | 定义 | 用途 |
|------|------|------|
| 件实体 | 材料几何体积 | 分析 |
| **pack_effective** | 材料：件×货种膨胀≤1.8；成箱：`min(outer, content×k)` | **订柜分子** |
| outer AABB | 箱外廓 L×W×H | **仅 3D 碰撞与出图** |

```text
V_eff = Σ pack_effective
N_weight = ceil(总货重 / PAYLOAD)          # 40HQ 铭牌 28610 kg
N_volume = ceil(V_eff / (柜容积 × η))     # 76.4 × 0.82
N0 = max(N_weight, N_volume)
```

### 4.2 自主定柜 + 3D

```text
N ← N0
while N ≤ N_max:          # N_max 默认 N0+8，用户 cap 仅封顶
    跑 3D 装载（outer）
    if can_fit and 不超重: break
    N ← N + 1
输出：N、layout[]、各柜重量
```

### 4.3 指标拆分

| 指标 | 用途 |
|------|------|
| `weight_util` | 订柜、超重 |
| `booking_volume_util` | 订柜（基于 V_eff） |
| `outer_space_util` | 仅展示摆柜几何，铁架常见偏低 |
| `can_fit` | 可行性 |
| `volume_suspicious` | `N_volume ≥ 2 × N_weight` → WARN |

### 4.4 LLM 边界

仅：材料文本辅助、风险润色、finalize 摘要。  
**禁止**改柜数、改 can_fit、改重量体积数字。

---

## 五、模块对照（仓库）

| 优先级 | 模块 | 状态 | 说明 |
|--------|------|------|------|
| P0 | `tools/volume_estimate.py` | ✅ | pack_effective / booking_volume / η / 铭牌 |
| P0 | `tools/packing.py` | ✅ | content_m3 / outer_m3 / booking_volume_m3 / fill |
| P0 | `tools/booking.py` | ✅ | compute_booking + pack_with_auto_containers |
| P0 | `agents/planner.py` | ✅ | 写 N0；max_containers=搜索上限非目标 |
| P0 | `agents/loader.py` | ✅ | 自 N0 递增至 can_fit |
| P0 | `tools/bin3d.py` | ✅ | outer 碰撞；PAYLOAD 28610；**贴端墙+长架条带**（禁居中碎片） |
| P1 | evaluator / risk / finalize | ✅ | 三指标 + VOLUME_SUSPICIOUS |
| P1 | knowledge 40HQ | ✅ | COSCO PAYLOAD/CU.CAP |
| P2 | material 过滤（目的地/已发） | ⏳ | 脚本侧已有 site-only；通用入主控待做 |
| P2 | structure 箱型升级防死循环 | 部分 | 已有 upgrade 限制，可再打磨 |
| P3 | visualizer 多柜 | ✅ | layout 驱动，与 N 解耦 |

---

## 六、验收

```bash
python scripts/test_booking_regression.py
```

| 用例 | 期望 |
|------|------|
| ~32t 铁件材料 | 自主 **N≈2**（回归，非约束） |
| 低填充大外廓箱 | V_eff≪outer，**N0≤3** |
| 仅虚大 outer 无 content | 打折 + 可能 volume_suspicious，**不到 10+** |
| 小批 3D | 自 N0 递增至 can_fit |

---

## 七、一句话

**保留多智能体与确认闸门；订柜改为「重量 + pack_effective」自主算 N，3D 用 outer 校验并自动加柜；指标与出图与 N 解耦；领导 2 柜只作回归样例。**
