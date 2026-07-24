## 1 主控智能体 `orchestrator`

【主控·开头】9 智能体启动 | intent=full_process | 材料=5 行 | 推荐柜型=40GP（采纳=True，当前=40GP）| 理由：体积适合 1×40GP 装下；对照：原先倾向 40HQ，综合体积/重量后推荐 40GP | 策略：二层堆码优先 + 空间/重量双利用率

## 2 材料解析智能体 `material_parser`

材料解析完成(inject)：249 件 / 2310.0 kg

## 3 结构计算智能体 `structure`

结构约束完成：4 组推荐箱型约束（本步仅建议；半严格校核在装箱成箱后执行）

## 4 装箱方案智能体 `box_scheme`

装箱完成：4 箱 — 全部箱结构计算通过（标准箱库+混装 外廓32.1475m³/货6.893m³ 填充均21% [4米铁架×4]）

```json
{
  "box_count": 4,
  "pass": 4,
  "reinforce": 0,
  "fail": 0,
  "total_net_weight_kg": 2310.0,
  "total_gross_weight_kg": 3061.4,
  "structure_overall": "全部箱结构计算通过",
  "max_box_net_kg": 1500.0,
  "revision_mode": false,
  "dense_mode": false,
  "standard_boxes": true,
  "mix_mode": true,
  "packing_mode": "standard_box_library+cross_length_mix",
  "boxes_outer_volume_m3": 32.1475,
  "cargo_item_volume_m3": 6.893,
  "avg_crate_fill": 0.2144,
  "standard_box_type_counts": {
    "4米铁架": 4
  }
}
```
- **BOX-01** 4米铁架(标准加长) outer={'length': 4350.0, 'width': 1100.0, 'height': 1750.0} struct=通过 solid=8.3737m3
  content: [{'material_id': 'M002-S2', 'name': '镀锌钢通长件(拆2)', 'quantity': 2}, {'material_id': 'M001-S1', 'name': '镀锌钢通(拆1)', 'quantity': 8}]
- **BOX-02** 4米铁架(标准加长) outer={'length': 4350.0, 'width': 1100.0, 'height': 1750.0} struct=通过 solid=8.3737m3
  content: [{'material_id': 'M002-S1', 'name': '镀锌钢通长件(拆1)', 'quantity': 6}]
- **BOX-03** 4米铁架 outer={'length': 4000.0, 'width': 1100.0, 'height': 1750.0} struct=通过 solid=7.7m3
  content: [{'material_id': 'M003', 'name': '幕墙支撑', 'quantity': 6}, {'material_id': 'M001-S3', 'name': '镀锌钢通(拆3)', 'quantity': 4}]
- **BOX-04** 4米铁架 outer={'length': 4000.0, 'width': 1100.0, 'height': 1750.0} struct=通过 solid=7.7m3
  content: [{'material_id': 'M001-S2', 'name': '镀锌钢通(拆2)', 'quantity': 8}, {'material_id': 'M005', 'name': '短支撑', 'quantity': 15}, {'material_id': 'M004-S1', 'name': '铁垫片(拆1)', 'quantity': 88}, {'material_id': 'M004-S2', 'name': '铁垫片(拆2)', 'quantity': 88}, {'material_id': 'M004-S3', 'name': '铁垫片(拆3)', 'quantity': 24}]

##  确认闸门 present_team_a `present_team_a`

团队A完成，自动确认 40GP

## 5 规划智能体 `planner`

规划完成：40GP ×≤2，优先序 4 箱

## 6 装载执行智能体 `loader`

装载完成 engine=python-laff-3d can_fit=True 容积(实心外廓)24% 货32.15m³/柜67.5m³ 最满柜25% 底面积32% 重量6% [python-laff-3d]

can_fit=True used=2 space=0.2382 floor=0.3246 wt=0.0574 engine=python-laff-3d
- layout {'box_id': 'BOX-04', 'container_no': 1, 'position': {'x': 4000, 'y': 0, 'z': 0}, 'size': {'dx': 4000, 'dy': 1100, 'dz': 1750}, 'rotation': 'LWH', 'layer': 1}
- layout {'box_id': 'BOX-03', 'container_no': 1, 'position': {'x': 4000, 'y': 1252, 'z': 0}, 'size': {'dx': 4000, 'dy': 1100, 'dz': 1750}, 'rotation': 'LWH', 'layer': 1}
- layout {'box_id': 'BOX-01', 'container_no': 2, 'position': {'x': 3500, 'y': 0, 'z': 0}, 'size': {'dx': 4350, 'dy': 1100, 'dz': 1750}, 'rotation': 'LWH', 'layer': 1}
- layout {'box_id': 'BOX-02', 'container_no': 2, 'position': {'x': 3500, 'y': 1252, 'z': 0}, 'size': {'dx': 4350, 'dy': 1100, 'dz': 1750}, 'rotation': 'LWH', 'layer': 1}

## 7 评估优化智能体 `evaluator`

评估：score=61.1 passed=True replan=False | 实心容积24%(子分57) 底面积32%(子分56) 重量6%(子分10) 综合36

```json
{
  "passed": true,
  "score": 61.1,
  "decision": "PASS",
  "structure_fail_box_ids": [],
  "space_utilization": 0.2382,
  "space_best": 0.2481,
  "floor_utilization_avg": 0.3246,
  "weight_utilization": 0.0574,
  "space_subscore": 57.2,
  "floor_subscore": 55.6,
  "weight_subscore": 9.8,
  "util_composite": 35.6,
  "volume_basis": "solid_outer_aabb",
  "targets": {
    "space_soft_min": 0.25,
    "weight_soft_min": 0.35,
    "space_good": 0.45,
    "weight_good": 0.6
  },
  "risks": [
    "实心外廓容积 24%（底面积 32%）与重量 6% 双低，建议合箱/并排装载或减少柜数"
  ],
  "suggestions": [
    "tighter_pack",
    "merge_boxes"
  ],
  "need_replan": false
}
```

## 8 风险合规智能体 `risk_compliance`

风险合规：level=medium score=49 passed=False decision=WARN blockers=0

```json
{
  "passed": false,
  "compliance_score": 49,
  "level": "medium",
  "risks": [
    "BOX-01 超长件，沿柜长摆放并加强绑扎",
    "BOX-02 超长件，沿柜长摆放并加强绑扎",
    "BOX-03 需加固：纵向加强或铁架",
    "BOX-04 需加固：纵向加强或铁架",
    "空隙率 76%（大件稀疏常见），注意填充绑扎；底面积利用 32%",
    "实心外廓容积 24%（货32.1m³）与重量 6% 双低于软目标，柜资源浪费",
    "实心外廓容积 24%（底面积 32%）与重量 6% 双低，建议合箱/并排装载或减少柜数",
    "加固建议（6米铁架）：纵向加强或铁架",
    "加固建议（4米铁架）：纵向加强或铁架"
  ],
  "blockers": [],
  "explanation": "**结论：**  \n本次4件4米铁架可装入集装箱（can_fit=true，无阻挡），但装载效率极低：空间利用率仅24%、重量6%，属严重资源浪费。超长件（BOX-01/02）及需加固件（BOX-03/04）风险已标注，需按方案沿柜长摆放并加强纵向绑扎。  \n**建议：**  \n- 优先合箱或并排装载，或选用更小柜型以减少浪费。  \n- 针对76%空隙率，务必填充绑扎，防止运输中移位。  \n- 加固措施（纵向加强/铁架）须严格执行。",
  "cog": {
    "gx_mm": 5830.7,
    "gy_mm": 1176.0,
    "gz_mm": 875.0,
    "lateral_eccentricity": 0.0,
    "longitudinal_position": 0.4846,
    "height_ratio": 0.3669
  }
}
```

## 9 可视化智能体 `visualizer`

三视角数据已生成（elements=4，柜数=2，侧视图2张+总览）

image_paths: {'top': None, 'side': 'output\\side_20260724_191227_overview.png', 'front': None, 'side_per_container': ['output\\side_20260724_191227_c01.png', 'output\\side_20260724_191227_c02.png'], 'side_overview': 'output\\side_20260724_191227_overview.png'}

##  主控汇总 finalize `finalize`

根据拼柜方案结果，实际柜型为**40GP**，主控建议维持40GP（不换柜）。容积利用率**24%**（货32.15 m³/柜67.5 m³），重量利用率**6%**，均严重低于软目标。几何装下（True），合规出运（是），但合规分49（medium/WARN），**可出运但效率极低**。

**主控裁决**：可讨论出运，需注意以下风险：
- 4件4米铁架含2件超长件（BOX-01/02）须沿柜长摆放并加强绑扎；BOX-03/04需纵向加固。
- 空隙率76%，底面积利用率32%，建议合箱/并排装载或改用更小柜型以减少资源浪费。
- 加固措施（纵向加强/铁架）必须严格执行。

**结论**：可装入并出运，但属严重资源浪费，建议优化装载方案或换小柜。

---
<details><summary>结构化原文</summary>

# 拼柜方案结果

## ✅ 主控裁决：可讨论出运

**能否出运**：**是**（规则侧通过；正式前仍需 VGM 与人工复核）

**主控流水线**：9 智能体（含主控，首尾选柜）
**方案编号（装箱）**：PKG-20260724_191222_f66a6aeb
**柜型（实际）**：40GP
**主控开头推荐**：40GP
**主控结尾推荐**：40GP（维持）
**箱数**：4
**能否装下（几何）**：True
**能否出运（合规）**：是
**用柜数**：2
**空间利用率（箱体外廓实心长方体）**：24%（最满柜 25%，底面积均 32%；货 32.15 m³ / 柜 67.5 m³）
**重量利用率**：6%
**堆码**：二层箱数 0/4；策略=优先二层（矮箱/铁笼上二层，超长仅底层）
**装箱模式**：标准箱库外廓+跨长度档混装；箱型分布 4米铁架×4；箱外廓合计 32.1475 m³，货件 6.893 m³，箱内填充均 21%
**利用综合分**：35.6 （空间子分 57.2 / 重量子分 9.8）
**评估分**：61.1（passed=True decision=PASS）
**合规分**：49（level=medium decision=WARN）

## 主控选柜说明
- 体积适合 1×40GP 装下

## 风险摘要
- BOX-01 超长件，沿柜长摆放并加强绑扎
- BOX-02 超长件，沿柜长摆放并加强绑扎
- BOX-03 需加固：纵向加强或铁架
- BOX-04 需加固：纵向加强或铁架
- 空隙率 76%（大件稀疏常见），注意填充绑扎；底面积利用 32%
- 实心外廓容积 24%（货32.1m³）与重量 6% 双低于软目标，柜资源浪费
- 实心外廓容积 24%（底面积 32%）与重量 6% 双低，建议合箱/并排装载或减少柜数
- 加固建议（6米铁架）：纵向加强或铁架
- 加固建议（4米铁架）：纵向加强或铁架

## 合规说明
**结论：**  
本次4件4米铁架可装入集装箱（can_fit=true，无阻挡），但装载效率极低：空间利用率仅24%、重量6%，属严重资源浪费。超长件（BOX-01/02）及需加固件（BOX-03/04）风险已标注，需按方案沿柜长摆放并加强纵向绑扎。  
**建议：**  
- 优先合箱或并排装载，或选用更小柜型以减少浪费。  
- 针对76%空隙率，务必填充绑扎，防止运输中移位。  
- 加固措施（纵向加强/铁架）须严格执行。

## 布局
- 三视角数据：views.top/side/front 已生成
- 侧视 PNG：output\side_20260724_191227_overview.png
- 装载引擎：python-laff-3d

---
主控复核：当前 40GP，推荐 40GP（维持）
团队B 完成。如需改柜型请重新确认。

</details>

*LLM: deepseek-v4-flash*

根据拼柜方案结果，实际柜型为**40GP**，主控建议维持40GP（不换柜）。容积利用率**24%**（货32.15 m³/柜67.5 m³），重量利用率**6%**，均严重低于软目标。几何装下（True），合规出运（是），但合规分49（medium/WARN），**可出运但效率极低**。

**主控裁决**：可讨论出运，需注意以下风险：
- 4件4米铁架含2件超长件（BOX-01/02）须沿柜长摆放并加强绑扎；BOX-03/04需纵向加固。
- 空隙率76%，底面积利用率32%，建议合箱/并排装载或改用更小柜型以减少资源浪费。
- 加固措施（纵向加强/铁架）必须严格执行。

**结论**：可装入并出运，但属严重资源浪费，建议优化装载方案或换小柜。

---
<details><summary>结构化原文</summary>

# 拼柜方案结果

## ✅ 主控裁决：可讨论出运

**能否出运**：**是**（规则侧通过；正式前仍需 VGM 与人工复核）

**主控流水线**：9 智能体（含主控，首尾选柜）
**方案编号（装箱）**：PKG-20260724_191222_f66a6aeb
**柜型（实际）**：40GP
**主控开头推荐**：40GP
**主控结尾推荐**：40GP（维持）
**箱数**：4
**能否装下（几何）**：True
**能否出运（合规）**：是
**用柜数**：2
**空间利用率（箱体外廓实心长方体）**：24%（最满柜 25%，底面积均 32%；货 32.15 m³ / 柜 67.5 m³）
**重量利用率**：6%
**堆码**：二层箱数 0/4；策略=优先二层（矮箱/铁笼上二层，超长仅底层）
**装箱模式**：标准箱库外廓+跨长度档混装；箱型分布 4米铁架×4；箱外廓合计 32.1475 m³，货件 6.893 m³，箱内填充均 21%
**利用综合分**：35.6 （空间子分 57.2 / 重量子分 9.8）
**评估分**：61.1（passed=True decision=PASS）
**合规分**：49（level=medium decision=WARN）

## 主控选柜说明
- 体积适合 1×40GP 装下

## 风险摘要
- BOX-01 超长件，沿柜长摆放并加强绑扎
- BOX-02 超长件，沿柜长摆放并加强绑扎
- BOX-03 需加固：纵向加强或铁架
- BOX-04 需加固：纵向加强或铁架
- 空隙率 76%（大件稀疏常见），注意填充绑扎；底面积利用 32%
- 实心外廓容积 24%（货32.1m³）与重量 6% 双低于软目标，柜资源浪费
- 实心外廓容积 24%（底面积 32%）与重量 6% 双低，建议合箱/并排装载或减少柜数
- 加固建议（6米铁架）：纵向加强或铁架
- 加固建议（4米铁架）：纵向加强或铁架

## 合规说明
**结论：**  
本次4件4米铁架可装入集装箱（can_fit=true，无阻挡），但装载效率极低：空间利用率仅24%、重量6%，属严重资源浪费。超长件（BOX-01/02）及需加固件（BOX-03/04）风险已标注，需按方案沿柜长摆放并加强纵向绑扎。  
**建议：**  
- 优先合箱或并排装载，或选用更小柜型以减少浪费。  
- 针对76%空隙率，务必填充绑扎，防止运输中移位。  
- 加固措施（纵向加强/铁架）须严格执行。

## 布局
- 三视角数据：views.top/side/front 已生成
- 侧视 PNG：output\side_20260724_191227_overview.png
- 装载引擎：python-laff-3d

---
主控复核：当前 40GP，推荐 40GP（维持）
团队B 完成。如需改柜型请重新确认。

</details>

*LLM: deepseek-v4-flash*
