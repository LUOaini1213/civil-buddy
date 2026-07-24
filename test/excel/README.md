# 钢结构业务测试集（Excel）

> 网上几乎没有同类型「材料→铁架→拼柜」真实数据集。
> 本目录由 `scripts/build_steel_test_set.py` 从远东项目 Excel 拆分 + 合成生成。

## 标准列

### materials（材料清单）
`id | name | spec | quantity | weight_kg | total_weight_kg | length_mm | width_mm | height_mm | part_no | source_sheet | note`

### boxes（已装铁架明细）
`box_group | box_type | seq | name | part_no | drawing_no | length_mm | width_mm | height_mm | weight_kg | quantity | total_weight_kg | source_sheet | note`

### full_flow
多 sheet：`materials` + `box_lines` + `containers` + `meta`

## 文件说明

| 文件 | 用途 |
|------|------|
| test_materials_01.xlsx | 报价单材料 → Team A 材料解析/选箱 |
| test_boxes_1.1m.xlsx 等 | 装货单按框型拆分 → 对照真实合箱 |
| test_full_flow.xlsx | 材料+箱子+建议柜型 |
| syn_*.xlsx | 合成：短件/超长/近限重/超重风险/混装 |

## 跑法

```bash
# 仅生成
python scripts/build_steel_test_set.py

# 用材料 Excel 跑拼柜
python scripts/run_excel_tests.py
```
