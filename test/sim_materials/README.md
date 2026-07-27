# 仿真材料 test/sim_materials

**假设/合成数据**，用于算法与 Agent 回归，**不是**真实工地提料。

## 生成

```bash
python scripts/gen_sim_materials.py
python scripts/gen_sim_materials.py --run-booking
python scripts/gen_sim_materials.py --case weight_bound_32t --case tiny
```

## 用例一览

| case_id | 说明 |
|---------|------|
| `weight_bound_32t` | 重量主导，体积不应抬高柜数（230 行，~32200.0 kg） |
| `volume_bound_light` | 轻泡货，体积可能主导（40 行，~600.0 kg） |
| `small_one_container` | 小票一柜可订（8 行，~400.0 kg） |
| `long_frames` | 超长件，柜型应倾向 40 尺（15 行，~1900.0 kg） |
| `overweight_risk` | 重货应力，重量柜应≥3（4 行，~64000.0 kg） |
| `near_payload` | 接近单柜载荷（含箱皮后可能 2 柜）（27 行，~27000.0 kg） |
| `mixed_realistic` | 混装真实感小票（35 行，~3200.0 kg） |
| `hollow_crate_lines` | 当量 1.1m 架行；配合 crate_passthrough 做 Agent 测（20 行，~25600.0 kg） |
| `glass_category` | 玻璃货种，pack_factor 应高于钢（12 行，~1152.0 kg） |
| `tiny` | 极小票，证明未写死 2 柜（1 行，~10.0 kg） |

## 怎么用

```python
import json
from pathlib import Path
from packing_assistant.tools.volume_estimate import estimate_containers

data = json.loads(Path("test/sim_materials/weight_bound_32t/materials.json").read_text(encoding="utf-8"))
r = estimate_containers(materials=data["materials"], container_type="40HQ")
print(r["containers_needed"], r["binding_constraint"])
```

```bash
# 注入 Agent 演示
python scripts/demo_nine_agents_trace.py   # 自带 demo 材料
# 或自己写脚本 materials=json.load(...)["materials"]
```

## 与真实案例

| 类型 | 路径 |
|------|------|
| 仿真 | `test/sim_materials/` |
| 真实工地 | `scripts/demo_vmu1_site.py` |
| 真实已发 | `scripts/run_vmu1_shipped_fst0003.py` |
