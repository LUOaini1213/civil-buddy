# CHANGELOG — P2 体积门禁与展示（542b0c3 之后）

## P2-1 `volume_mode=crate_outer` 门禁

- **默认禁止**纯外廓订柜：误传 `crate_outer` 且未开调试时，**自动改回 `pack_effective`**
- 调试须显式 `allow_crate_outer_debug=True`，结果 `volume_source=crate_outer_DEBUG` + warning
- 单测：`scripts/test_p2_volume_gates.py::test_crate_outer_redirected_by_default`

## P2-2 BoxModel / schema 体积字段

- `BoxModel` 声明：`content_m3`、`crate_fill_ratio` / `fill_ratio`、`outer_m3`、`booking_volume_m3`
- `validate_packing_result`：API/中文箱归一；**缺体积字段 WARN**（不阻断）
- 与 `adapters.box_api_to_internal` 透传一致

## P2-3 visualizer 双率展示

- `display_metrics`：订柜有效体积率 vs 外廓摆柜率 vs 重量
- 图注/消息明确 **外廓≠订柜**；`visualize.py` 多柜标题同步
- **不改** 3D 几何算法

## P2-4 `docs/volume-algorithm.md` 对齐代码

- N0 = max(重量柜, 有效体积柜)；η=0.82；pack_effective；outer 仅 3D
- crate_outer 门禁与 loader/evaluator 行为说明

## 如何测

```bash
python scripts/test_booking_regression.py
python scripts/test_p2_volume_gates.py
```
