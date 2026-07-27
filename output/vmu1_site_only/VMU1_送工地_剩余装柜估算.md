# VMU1 送工地装柜（柜型按 COSCO 40HQ 铭牌）

## 柜型参数（你提供的 COSCO 铭牌）

| 项 | 铭牌 | 程序采用 |
|---|---:|---:|
| MAX.WT（最大总重） | 32,500 kg | 32,500 |
| TARE（皮重） | 3,890 kg | 3,890 |
| **PAYLOAD（最大货重）** | **28,610 kg** | **28,610** |
| HIGH | 2.9 m | 内高约 2,698 mm |
| **CU.CAP（容积）** | **76.4 m³** | **76.4** |

重量与体积**都是硬约束**（自主定柜，不写死 2 柜）：
- 重量柜数 = ceil(货重 / 28610)
- 体积柜数 = ceil(V_eff / (76.4 × η))，η=0.82，V_eff=Σ min(outer, content×k)
- N0 = **max(重量柜, 有效体积柜)**；3D 自 N0 递增至 can_fit
- **不要用虚大当量外廓当订柜分子**（outer 仅 3D 碰撞）

- **数据源**：`Material_Summary_VMU送工地.xlsx`
- **范围**：VMU1 送工地

## 结论（算法自主）

| 项 | 值 |
|---|---|
| 建议柜型 | **40HQ（COSCO 铭牌级）** |
| **算法推荐用柜** | **3**（can_fit=True） |
| 自主 N0 | **2**（重量柜 2 / 有效体积柜 2 / 绑定 both） |
| V_eff 订柜体积 | 71.5252 m³（箱外廓合计 140.7095 m³，已打折） |
| 净重（当量） | 44358.0 kg |
| 外廓摆柜率 | 0.6143 |
| 订柜有效体积率 | 0.3806 |
| 底面积 / 重量利用率 | 0.8176 / 0.6231 |
| 体积可疑 | False  |
| **REDACTED-REF 装货单（人工对照）** | **2 柜**（约 19.8 t + 12.7 t，仅回归样例） |

> **订柜主结论：N0=2（重量+有效体积，自主，未写死 2）。**  
> 3D 当量箱几何 can_fit 用柜=3（外廓碰撞上界；铁架已按装货单 1.1/2/4m 混型，仍含五金/瓦楞等其它 POR）。  
> REDACTED-REF 人工装货单对照为 2 柜，作回归而非约束。

## 纳入 POR（VMU1·工地·有剩余量）

| POR | 物料组 | 当量箱数 | 原料件数 |
|---|---|---:|---:|
| REDACTED-CODE-VMU-0001-BBF0007 | 23—紧固件/螺丝 | 44 | 8762 |
| REDACTED-CODE-VMU-0001-BBF0022 | 23—紧固件/螺丝 | 4 | 702 |
| REDACTED-CODE-VMU-0001-BGK0015 | 19—胶条、垫块、胶皮 | 3 | 110 |
| REDACTED-CODE-VMU-0001-BGK0055 | 19—胶条、垫块、胶皮 | 2 | 100 |
| REDACTED-CODE-VMU-0001-BOM0016 | 28—杂项配件 | 4 | 80 |
| REDACTED-CODE-VMU-0001-BOM0019 | 28—杂项配件 | 18 | 702 |
| REDACTED-CODE-VMU-0001-FAC0011 | 11—铝板 | 5 | 128 |
| REDACTED-CODE-VMU-0001-FSS0005 | 14—不锈钢 | 2 | 2 |
| REDACTED-CODE-VMU-0001-REDACTED-REF | 13—铁件 | 25 | 1998 |
| REDACTED-CODE-VMU-0001-FST0017 | 13—铁件 | 4 | 4 |
| REDACTED-CODE-VMU-0001-FST0022 | 13—铁件 | 3 | 189 |

## 未纳入

- **送工厂**全部（FAC0008/BAL/BGL/FAC0007 等）— 不在本次范围
- **VMU02/03/04** 送工地行（本表有，但领导只问 VMU1）
- 已到=未到=0 的空量行（BBF0006/BOM0013/BSS0010 等）

## 说明

1. 件数→当量箱：铁件约 30 件/架、铝板约 25 片/架、紧固件约 200 件/箱等（实务粗算）。
2. 若 **REDACTED-REF / FAC0011** 已部分发运，请用真实剩余件数替换后重跑，柜数会下降。
3. 正式订柜前建议对照提料单尺寸与已发货目录再校一版。

产物：`E:\REDACTED-PATH\output\vmu1_site_only\vmu1_site_only_pack.json`  /  `E:\REDACTED-PATH\output\vmu1_site_only\materials_vmu1_site_remaining.xlsx`