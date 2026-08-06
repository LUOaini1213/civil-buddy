# 扩大装箱范围迭代 · 2026-08-06

**Baseline HEAD**: `07fbc87`  
**目标**: 无人值守扩大 pack 覆盖（非 inspect-only）+ 可选 mid50 舒适区

## 覆盖 before → after

| 范围 | before | after |
|------|--------|-------|
| ns pack-path 夹具 | 3 pack + 2 fail = **5** | **6 pack + 2 fail = 8**（全 INDEX） |
| 非 ns 货族 | 0（本轮冒烟） | generic G1/G2/G12 + high_util + steel + five_containers |
| 合计 expand_pack_scope | 5 | **14** 全绿 |

## 交付

### 1. 全量 ns pack smoke
- `scripts/test_nonstandard_pack_smoke.py`：PACK×6 + FAIL×2
- 硬 FAIL 仍诚实拦截（ship_ok/can_fit/incomplete/blocks_auto）

### 2. 多货族 expand scope
- `scripts/test_expand_pack_scope.py`
  - ns×8 · gtable×3 · demo×3
- 证据：`{SCRATCH}/expand_pack_smoke.log`

### 3. 通用表 pack 路径
- `run_generic_table_tests.py --only G1,G2,G12 --pack`
- 证据：`{SCRATCH}/expand_scope_extra.log`

### 4. high_util mid50 舒适区（实测）
- R4 加强（更密 rigid/slide、Phase D、高目标加倍迭代）
- 物料中段偏重 + 几何 1100mm；`r4_target_mid50=0.72`
- **实测 mid50=70.02%**（`expand_mid50_probe.log` / `test_mid50_cog.py`）
- 可报 **≥0.70 舒适线**；steel mid50=100%

## 门禁

`{SCRATCH}/expand_iter_gates.log`：competition 硬门 + expand 回归全 exit 0

## 延期

- 承运人真 VGM / TMS
- 全 G1–G15 全量 pack 矩阵（本轮 3 代表 + parse 15）
- 446t / t80 大票矩阵
- 联网总分重打

## 演示只说

> 装箱覆盖：非标 8 套全走真实拼柜；通用表 G1/G2/G12 可 parse→pack；满载 mid50 **70%** 实测过舒适线。
