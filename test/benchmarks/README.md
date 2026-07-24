# 公开 3D-BPP / 拼柜基准用例

| 来源 | 文件 | 用途 |
|------|------|------|
| D-Wave sample_data_1/2 | `sample_data_*.json` | 单柜/多柜冒烟 |
| Case A | `case_a_small_cartons_20gp.json` | 小件易装 |
| Case B | `case_b_long_frames_40hq.json` | 长件/铁架风格 |
| Case C | `case_c_payload_stress_40hq.json` | 限重压力 |
| 40HQ style / overweight | 对应 json | 混装 / 超重风险 |

```bash
python scripts/convert_bpp_to_cases.py
python scripts/run_benchmark_cases.py
```

Excel 在 `excel/` 子目录。
