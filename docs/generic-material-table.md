# 通用材料表契约（MaterialTableIR）

> 12h 双线并行冻结文档 · 2026-08-05  
> 目标：任意材料表格 → 标准化行 → `boxes[]` → 拼柜；钢材仅为 profile 之一。

## 管道

```text
Excel / CSV / PDF / NL / JSON
    → MaterialTableIR（本契约）
    → materials[]（现有 API，兼容）
    → boxes[]（阶段 1/2 装载原语）
    → 大 Team A/B + critic
    → plan / risk / views / scorecard
```

## MaterialTableIR 行字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | string | 建议 | 行 ID；缺省自动 `M001`… |
| `name` | string | **是** | 品名/描述 |
| `quantity` | int | 是 | 默认 1 |
| `length_mm` | float | 建议 | 可缺 → 估算 + `dims_estimated` |
| `width_mm` | float | 建议 | 同上 |
| `height_mm` | float | 建议 | 同上 |
| `weight_kg` | float | 建议 | 单重 kg |
| `total_weight_kg` | float | 建议 | 缺省 = weight × qty |
| `category` | string | 否 | 自由文本；归一见下 |
| `spec` | string | 否 | 规格 |
| `part_no` | string | 否 | 件号 |
| `note` | string | 否 | 备注 |
| `meta` | object | 否 | 映射与置信度 |

### `meta` 建议子字段

| 键 | 说明 |
|----|------|
| `source` | `csv` / `xlsx` / `pdf` / `nl` / `json` |
| `source_path` | 原文件 |
| `column_map` | 原表头 → 标准字段 |
| `units_in` | 原始单位提示 |
| `confidence` | 0–1 解析置信度 |
| `dims_estimated` | bool |
| `profile_hint` | `generic_table` / `steel_structure` / … |

### category 归一枚举（软约束）

`carton` · `crate` · `long_item` · `pallet` · `bulk_bag` · `fragile` · `liquid_unit` · `generic`  
中文别名（如 纸箱/铁架/超长件）由 mapper 映射；未知保留原文并记 `generic`。

## 列名同义词（mapper 默认）

| 标准字段 | 同义词（节选） |
|----------|----------------|
| name | 名称, 品名, 货物名称, item, product, description, sku_name |
| quantity | 数量, 件数, 箱数, qty, qty., count, pcs |
| length_mm | 长, 长度, 外长, L, length, len, length_cm, length_m |
| width_mm | 宽, 宽度, 外宽, W, width, width_cm |
| height_mm | 高, 高度, 外高, H, height, height_cm |
| weight_kg | 单重, 重量, 毛重, 净重, weight, gross_weight, net_weight, kg |
| total_weight_kg | 总重, 合计重量, total_weight, total_kg |
| part_no | 件号, 料号, 图号, sku, part, item_no |
| id | 编号, 行号, line_id, row_id |
| category | 类别, 类型, 品类, type, class |
| spec | 规格, 型号, model |

单位：长度 `m`/`cm`/`mm` → mm；重量 `t`/`kg`/`g` → kg。

## Profile 插件

| profile | 何时用 | 额外行为 |
|---------|--------|----------|
| `generic_table` | **默认** | 不强制结构计算；passthrough 箱 |
| `steel_structure` | 建材/铁架 | 结构结论、铁架知识库、dims_override |

行业知识只进 profile / knowledge，**不进**主循环节点图。

## 双线目录所有权（12h）

| 线 | 主写 | 禁止擅改 |
|----|------|----------|
| **A 泛化** | `tools/table_mapper.py`、`test/generic_tables/`、解析入口 | `bin3d` / replan / competition 剧本主线 |
| **B 冲赛** | `bin3d`/`planner`/`evaluator`/`docs/competition*`/`scripts/*competition*` | 重写 mapper |
| **共享** | `adapters` 增量、`schemas`、profiles | 改契约须走 merge 分支 |

## 验收闸门

- G1：`test/generic_tables` G1–G6 全部可解析  
- 至少 4/6 `can_fit=true`（边界票可 warn）  
- `python scripts/run_excel_tests.py --only syn_` 不回归  
- LLM 不写 xyz（轨迹抽检）

## 入口

```bash
# 映射 + 可选 pipeline
python scripts/run_generic_table_tests.py
python scripts/run_generic_table_tests.py --pack

# 一键演示（线 B）
python scripts/competition_demo_one_shot.py
```
