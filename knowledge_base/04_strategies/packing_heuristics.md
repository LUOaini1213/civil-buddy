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

1. **默认标准铁架库**（1.1m–6m 档，见 `packing_knowledge_base.json`），短件可混入更长档。  
2. 薄板为主 → dense，避免 4m/6m 空心架充订舱体积。  
3. 当量已成箱（note 含 crate）→ passthrough，禁止二次撑外廓。  
4. 重钢优先底层；prefer_stack 抬高面积利用率。  
5. 单箱净重 cap 默认 **3200kg 量级**（`max_box_net_kg`，以代码 options 为准），超限拆分。  
6. heavy_steel **不要**默认 crate_passthrough（应用标准箱）。

## 代码默认

- `standard_boxes=True`（产品默认）
- 参数以 `packing_options` / config 为准，md 不双写魔法数表
