# 项目打包汇总

## 是什么

多智能体（LangGraph）钢结构 **装箱 + 拼柜** 系统：

| 阶段 | 内容 |
|------|------|
| 团队 A | 材料解析 → 结构约束 → 合箱/铁架木箱 + 半严格结构计算 |
| 确认 | HITL 选柜型 |
| 团队 B | 规划 → 3D 装载（python-laff-3d / 可选 skjolber）→ 评估 → 风险 → 三视图 |
| 主控 | 开头/结尾选柜（20GP/40GP/40HQ）、空间·重量双目标、二层堆码策略 |

## 目录

```
packing_assistant/   # 核心：agents / tools / harness / graph
gateway/             # FastAPI
frontend/            # Vue2 CDN 演示页
knowledge/           # 知识库 JSON
scripts/             # 批跑、基准、Excel 测试集、9 agent dump
docs/                # 架构与 API 说明
test/                # PDF 装箱单 + excel 业务测试集 + benchmarks
eval/                # 黄金用例
skjolber-service/    # 可选 Java 装载服务（需 JDK）
data/external/       # 公开 BPP 样例（D-Wave 等）
```

## 常用命令

```bash
pip install -r requirements.txt
python main.py --demo --trace
python scripts/run_test_shipments.py          # PDF 项目拼柜
python scripts/build_steel_test_set.py        # REDACTED-CLIENT Excel → test/excel
python scripts/run_excel_tests.py
python scripts/fetch_external_datasets.py
python scripts/convert_bpp_to_cases.py
python scripts/run_benchmark_cases.py
python scripts/compare_container_types.py     # 20/40/HQ 对比
python scripts/dump_nine_agents.py            # 9 步原文
python -m uvicorn gateway.app:app --host 127.0.0.1 --port 8000
```

## 容积指标

**箱体外廓实心长方体** Σ(L×W×H) / 柜内容积（`volume_basis=solid_outer_aabb`），非零件镂空体积。

## 未入库（本地敏感/可再生）

- API Key 文件、`.env`
- `output/**/*.png` 运行截图
- Python 缓存
