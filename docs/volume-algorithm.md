# 体积算法怎么改

## 问题

原先估柜/选柜把「体积」算虚了：

- 材料阶段：`件体积 × 2.6`（过大）
- 或用 `4m×1.1m×1.2m` 当量架外廓 × 架数当分子  
→ 体积约束**过紧**，柜数虚高（如 15 柜），而重量只需 2 柜。

**重量与体积都是硬约束**，正确写法：

```text
柜数 = max(
  ceil( 货重 / PAYLOAD ),                    # 如 28610 kg
  ceil( 有效体积 / (柜容积 × 可用率) )         # 如 76.4 × 0.62
)
```

## 三层体积（不要混用）

| 层级 | 公式 | 用途 |
|------|------|------|
| **① 件实体** `piece_solid` | Σ(L×W×H×qty) | 下界；提料真实尺寸 |
| **② 有效包装** `pack_effective` | Σ(件体积 × 货种膨胀) | **估柜体积分子（推荐）** |
| **③ 成箱外廓** `crate_outer` | Σ(箱外 L×W×H) | **仅 3D 摆柜几何**；已成真实箱才用 |

### 货种膨胀（封顶 1.8）

| 货种 | 系数 | 说明 |
|------|-----:|------|
| steel 铁件/钢通 | 1.30 | 合箱间隙，勿 2.5+ |
| aluminum_profile | 1.35 | |
| aluminum_panel | 1.50 | 叠层防护 |
| glass | 1.80 | 木箱偏大 |
| hardware | 1.40 | 五金箱 |
| general | 1.40 | 默认 |

柜可用容积：`76.4 × fill_ratio`，`fill_ratio` 默认 **0.62**（绑扎/不规则），不是 100%。

## 代码入口

```python
from packing_assistant.tools.volume_estimate import estimate_containers, pack_effective_m3

# 材料清单估柜（推荐）
r = estimate_containers(
    materials=mats,           # length_mm/width_mm/height_mm/quantity/weight
    container_type="40HQ",    # PAYLOAD 28610 / 76.4 m3
    fill_ratio=0.62,
    volume_mode="pack_effective",
)
# r["containers_by_weight"]
# r["containers_by_volume"]
# r["containers_needed"] == max(上两者)
# r["binding_constraint"]  # weight | volume | both
```

摆柜后的 `space_utilization`（bin3d）仍是 **箱外廓÷柜**，用来看布局松紧；  
**订柜数不要只用这个指标反推**（铁件会显得空）。

## 改完后对照

| 场景 | 重量柜数 | 体积柜数（pack_effective） | 结论 |
|------|--------:|--------------------------:|------|
| REDACTED-REF 约 32 t 铁件 | 2 | ~1–2（真实件尺寸） | **2 柜** |
| 虚当量 4m 架 ×67 | 2 | 十几 | 错误分子，废弃 |

## 文件

- `packing_assistant/tools/volume_estimate.py` — 新算法
- `container_select.py` — 材料估体积改为 pack_effective
- `bin3d.py` — 标明外廓利用率仅用于摆柜几何
