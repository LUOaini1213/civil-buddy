---
category: strategies
subcategory: packing
priority: medium
type: strategy
tags: [heuristic, standard_box, dense, max_box_net_kg]
source: internal
updated: "2026-07-30"
harness: ">=0.6.3"
status: active
---
# 装箱启发式

> 策略 **低于** rules；与红线冲突时以 rules 为准。

## 外廓哲学（硬/软）

| 层级 | 规则 | 说明 |
|------|------|------|
| **硬** | 结构过 | `structure_calc` 结论 ≠ 不通过 |
| **硬** | 进柜 | 箱外廓 ≤ 目标柜内净空（知识库 containers） |
| **自由** | 宽高可定制 | 非 standard 时按货包络定 W/H；允许铁笼/定制架，不锁死 1100-only |
| **软** | 截面过大则拆箱 | 同时 `W>0.7×柜宽` 且 `H>0.85×柜高` → 拒绝合箱 / 压矮贴货，避免 2200×2650 封锁整截面 |
| **软** | 可 2 排 snappoint | `2×W + 50 ≤ 柜宽` 时优先对齐 **1100 / 1150**；仅货宽超半柜才出单排宽箱 |

标准箱库是 **优先推荐外廓**，不是唯一合法外廓。

1. **默认标准铁架库**（1.1m–6m 档，见 `packing_knowledge_base.json`），短件可混入更长档。  
2. 薄板为主 → dense，避免 4m/6m 空心架充订舱体积。  
3. 当量已成箱（note 含 crate）→ passthrough，禁止二次撑外廓。  
4. 重钢优先底层；prefer_stack 抬高面积利用率。  
5. 单箱净重 cap 默认 **3200kg 量级**（`max_box_net_kg`，以代码 options 为准），超限拆分。  
6. heavy_steel **不要**默认 crate_passthrough（应用标准箱）。  
7. 宽货不要虚跳满柜宽；**能两排就两排**（1100/1150 snappoint），避免 1300～1800 半废带。  
8. 单排宽箱高度贴货，不拔满柜/模块高，便于其它方向利用。  
9. **模块级大件**（半柜宽 + 中高 + 单件重）→ 当量直通/贴货，禁止拆成多只 6m 空心标准架（假多柜）。  
10. **多柜 N0\*** = max(重量柜, 有效体积柜, 底面几何, 槽位几何)；3D 实装 `used` 可 +0~1；末柜偏空可并回。  
11. **柜内 multi_start** 优化摆法；**柜级** 不是纯 FFD——是下界 + 递增试装；柜数由 tools 算，HITL 确认。

## 代码默认

- `standard_boxes=True`（产品默认；模块检测可覆盖为 passthrough）
- 多柜：`tools/booking.py`（N0\*、并回）· `bin3d` multi_start（柜内）
- 参数以 `packing_options` / config 为准，md 不双写魔法数表
