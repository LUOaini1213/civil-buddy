# 非标件新材料迭代 · 3h 切片（2026-08-06）

## 做了什么

在 `test/sim_materials/ns_*` 落地 **8 套新非标仿真夹具**（非 golden 内联复制），经真实 `inspect_nonstandard` 全覆盖：

| case | overall | 主 tags |
|------|---------|---------|
| ns_overlength_rail | WARN | GEO_OVERSIZE, SHAPE_CUSTOM |
| ns_heavy_cast | WARN | LOAD_HEAVY |
| ns_thin_sheet_stack | WARN | SHAPE_CUSTOM |
| ns_missing_dims_mix | **FAIL** | DATA_GAP |
| ns_factory_crate_path | WARN | PACK_PATH (+GEO/LOAD) |
| ns_fragile_process | WARN | PROCESS_SPECIAL |
| ns_over_container_width | **FAIL** | GEO_OVERSIZE |
| ns_mixed_industry_bundle | WARN | GEO+LOAD+PACK+PROCESS+SHAPE |

INDEX：`test/sim_materials/ns_INDEX.json`  
报告样例：`output/nonstandard_inspect/ns_new_suite/`  
回归：`scripts/test_nonstandard_new_fixtures.py`  
生成器：`scripts/gen_nonstandard_fixtures.py`

## 引擎缺口（观察）

- 超长薄板会同时打 SHAPE + GEO（合理）  
- 工厂架常伴随重/超长（叠加标签正常）  
- 未发现需改 rule 的误 FAIL；缺尺寸/超柜硬 FAIL 正确  

## 延期

- 每票全 pipeline pack 批量  
- 与 446t 级大票混编  
- 真项目提料导入（仍用仿真）  
