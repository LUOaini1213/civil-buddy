# 体积算法与自主定柜（与代码对齐）

## 原则

- **重量与体积都是硬约束**
- **订柜分子不用箱外廓实心**（空心铁架会虚高柜数）
- **outer 仅 3D 碰撞 / 外廓摆柜展示**
- **禁止写死目标柜数**（如 `target_containers=2`）；2 柜仅作某票回归样例

## 订柜公式（代码默认）

```text
η = fill_ratio ≈ 0.82          # 柜容积可用率（行业 80–85%），非 1.0
PAYLOAD = 柜铭牌，40HQ 默认 28610 kg
V_cont  = 理论容积，40HQ 默认 76.4 m³
usable  = V_cont × η

# 材料阶段
V_eff = Σ(件 AABB 体积 × 货种膨胀)，膨胀封顶 1.8

# 成箱后
V_eff = Σ min(outer_m3, content_m3 × k)   # k≤1.5–1.8，低填充更严
        # 无 content 时打折 outer×0.45，不是全 outer

N_weight = ceil(毛重 / PAYLOAD)
N_volume = ceil(V_eff / usable)
N0       = max(N_weight, N_volume)         # 自主定柜初值

3D：从 N0 起用 outer 摆柜，失败则 N+1，直至 can_fit 或上限
```

对应实现：

| 符号 | 代码 |
|------|------|
| η | `estimate_containers(..., fill_ratio=0.82)` |
| V_eff 材料 | `pack_effective_m3` |
| V_eff 成箱 | `booking_volume_from_boxes` / `box_pack_effective_m3` |
| N0 | `booking.compute_booking` → `n0` |
| 3D 递增 | `pack_with_auto_containers` / `loader` |

## 三层体积（不要混用）

| 层级 | 公式 | 用途 |
|------|------|------|
| **① 件实体** `piece_solid` | Σ(L×W×H×qty) | 分析下界 |
| **② 有效包装** `pack_effective` | 件×货种膨胀；成箱 min(outer, content×k) | **订柜体积分子** |
| **③ 成箱外廓** `crate_outer` / outer AABB | Σ 箱 L×W×H | **仅 3D 与外廓摆柜率展示** |

### 货种膨胀（封顶 1.8）

| 货种 | 系数 |
|------|-----:|
| steel | 1.30 |
| aluminum_profile | 1.35 |
| aluminum_panel | 1.50 |
| glass | 1.80 |
| hardware | 1.40 |
| general | 1.40 |

### `volume_mode` 门禁

| mode | 默认 | 说明 |
|------|------|------|
| `pack_effective` | **默认** | 正式订柜 |
| `piece_solid` | 可选 | 下界分析 |
| `crate_outer` | **默认禁用** | 须 `allow_crate_outer_debug=True`；结果标 `volume_source=crate_outer_DEBUG`，不可静默当 N0 |

误传 `volume_mode="crate_outer"` 且未开调试时：自动改回 `pack_effective`，并写 `crate_outer_redirected=True` + warning。

## 指标拆分（评估 / 风险 / 出图）

| 指标 | 含义 | 订柜？ |
|------|------|--------|
| `weight_utilization` | 重量利用率 | 是（硬） |
| `booking_volume_utilization` | V_eff / (用柜×usable) | 是（硬） |
| `outer_space_utilization` / 兼容 `space_utilization` | Σ 箱外廓 / 柜几何 | **否**，仅布局松紧 |

- 评估：订柜有效体积子分 + 底面积 + 重量；**禁止** book_u 缺失时用 outer 顶替  
- 出图：图注须同时标「订柜有效体积率」与「外廓摆柜率」，并注明外廓≠订柜  

## 代码入口

```python
from packing_assistant.tools.volume_estimate import estimate_containers
from packing_assistant.tools.booking import compute_booking, pack_with_auto_containers

# 材料估柜
r = estimate_containers(
    materials=mats,
    container_type="40HQ",
    fill_ratio=0.82,
    volume_mode="pack_effective",
)
# r["n0"] 语义 → containers_needed
# r["volume_source"]、r["fill_ratio"]

# 成箱后订柜 + 3D
b = compute_booking(boxes=boxes, container_type="40HQ", fill_ratio=0.82)
plan = pack_with_auto_containers(boxes, container_type="40HQ", n0=b["n0"])
# plan["booking_volume_utilization"]  订柜有效体积率
# plan["outer_space_utilization"]     外廓摆柜率
```

## 回归预期（非写死柜数）

| 场景 | 期望 |
|------|------|
| ~32t 铁件材料 | 重量柜≈2，N0≈2（回归样例） |
| 低填充大外廓 | V_eff≪outer，N0 不被抬到 10+ |
| 误开 crate_outer 无 debug | 重定向 pack_effective，带 WARN |

```bash
python scripts/test_booking_regression.py
python scripts/test_p2_volume_gates.py
```

## 相关文件

- `tools/volume_estimate.py` — 三层体积 + crate_outer 门禁  
- `tools/booking.py` — N0 + auto 3D  
- `tools/packing.py` / `adapters.py` / `schemas.py` — 箱体积字段  
- `agents/loader.py` / `evaluator.py` / `visualizer.py` — 双率与评分  
- `docs/architecture-update-plan.md` — 架构总览  
