# 自我迭代至 13:30 · 2026-08-06

**Baseline HEAD**: `119a6b9`  
**Wall start**: 2026-08-06 **12:52:48**  
**Wall end**: 2026-08-06 **13:30:02**（28 轮持续回归环，见 timeline）  
**Scratch**: `{SCRATCH}/selfiter_until_1330_*`

## 选型（残差）

| # | 项 | 状态 |
|---|-----|------|
| A | UI 简洁演示模式（首屏减负） | **已交付** |
| B | 通用表 pack 覆盖扩至 **12** 族（parse 可装样本） | **已交付** |
| C | 均匀重货 mid50 诚实 probe | **已交付**（≥0.60；**未**达 0.70） |
| D | path_honesty `used_containers` 字段 | **已交付** |

## 交付 A · demo simple UI

- 默认 `demoSimpleMode: true`：收侧栏、精简 pill/按钮，主 CTA **满载演示**
- 切换「简洁演示」可回完整控制台
- 证据：`scripts/test_demo_simple_ui.py` → ALL_PASS  
  `{SCRATCH}/selfiter_until_1330_improve_ui.log`
- health features: `demo_simple_mode` / `demo_simple_default`

## 交付 B · G-table pack 扩面

- `test_expand_pack_scope` gtable：**12** 族（G1–6,G9–14 可装样本；缺 G7 缺尺寸/G8 噪声/G15 压力另轨）
- 总覆盖 **14 → 23**（ns8 + gtable12 + demo3）
- 证据：`{SCRATCH}/selfiter_until_1330_improve_gtable.log` ALL_PASS

## 交付 C · 均匀 mid50

- `materials_high_util_uniform` + preset `high_util_uniform`
- `scripts/test_mid50_uniform.py`：uniform **mid50≈0.6667**（CTU 过线，几何 1000mm）· biased **0.7002**
- **不声称**均匀货 ≥0.70 舒适
- 证据：`{SCRATCH}/selfiter_until_1330_improve_mid50u.log`

## 门禁

`{SCRATCH}/selfiter_until_1330_gates.log`：competition 硬门 + expand + mid50_uniform + demo_ui 全 exit 0

## 交付 D · path_honesty used_containers

- public path_honesty 带 `used_containers`（steps / policy_fallback 均可见）
- 证据：`{SCRATCH}/selfiter_until_1330_improve_path.log`

## 延期

- 均匀重货 mid50 稳到 ≥0.70
- G7/G8/G15 全量 pack 语义特化
- 承运人真 VGM
- 联网总分重打

## 演示只说

> 默认简洁演示一键满载；高级状态可切换回控制台。通用表 8 族可 pack。满载中段偏重 mid≈70%；**均匀重仍约 60%**，不夸大。
