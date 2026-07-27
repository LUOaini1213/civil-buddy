# 提升后「完成态」清单（提交前勾）

```text
□ 一句话：系统曾因外廓虚高报 ~15，修正后与真实 ~2 对齐
□ 两分钟能跑：booking 数字 + Agent API 过程
□ 一张表：错误口径 vs 正确口径（docs/wrong-vs-right-narrative.md）
□ 一个例：装得下仍风险拒绝（agent trace REJECT）
□ 文档与数字、截图一致；测试命令可复现
```

## 命令核对

```bash
python scripts/run_precommit_tests.py --quick
python scripts/demo_vmu1_site.py --with-shipped
python scripts/build_judge_package.py
# Agent（另开网关）
powershell -File scripts/start_gateway.ps1
python scripts/demo_nine_agents_trace.py --via-api
```

## 产物包

`output/demo_package/latest/` 或 `output/judge_package/latest/`

## 明确不做

深度学习装箱、完整有限元、扩无关 Agent、写死目标柜数。
