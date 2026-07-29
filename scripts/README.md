# Scripts

## CI / 产品入口（保留在本目录）

| 脚本 | 用途 |
|------|------|
| `smoke_agent_product.py` | 产品冒烟 |
| `eval_harness_cli.py` | tiny/20t 评测 |
| `eval_workteams_cli.py` | steps vs llm 影子评测 + KPI |
| `test_agent_auto_mode.py` | 自动模式 |
| `test_whatif_accept.py` | what-if |
| `test_continue_improve.py` | 持续改进项 |
| `test_p0_p1_p2_full.py` | P0–P2 链 |
| `test_single_team_loop.py` | 闭环（命名历史） |
| `run_t60_main.py` / `run_t80_main.py` | 大料试跑 |
| `compare_pack_engines.py` | 引擎 A/B |

```bash
python scripts/smoke_agent_product.py
python scripts/eval_workteams_cli.py --tiny-only
python scripts/eval_harness_cli.py
```

## Windows 启动

见 `scripts/win/`（`start-gateway.bat` 等）。

## 本地实验

`scripts/dev/` 与 `scripts/_*.py` **不入仓**（gitignore），仅本机临时实验。
