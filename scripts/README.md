# Scripts

## One-shot（新人 / 开源首页入口）

| 脚本 | 用途 |
|------|------|
| **`demo_one_shot.py`** | **一键演示**：默认 smoke；`--closed-loop` / `--eval-tiny` / `--all` |

```bash
python scripts/demo_one_shot.py
python scripts/demo_one_shot.py --all
```

## CI / 产品入口（保留在本目录）

| 脚本 | 用途 |
|------|------|
| `smoke_agent_product.py` | 产品冒烟（demo_one_shot 默认调用） |
| `demo_agent_closed_loop.py` | 闭环自检（感知→规划→工具→目标） |
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
python scripts/demo_one_shot.py
python scripts/smoke_agent_product.py
python scripts/eval_workteams_cli.py --tiny-only
python scripts/eval_harness_cli.py
```

## Windows 启动

见 `scripts/win/`（`start-gateway.bat` 等）。

## 本地实验

`scripts/dev/` 与 `scripts/_*.py` **不入仓**（gitignore），仅本机临时实验。

## 比赛回归（precommit --quick 已挂）

| 脚本 | 用途 |
|------|------|
| `run_precommit_tests.py` | booking + volume gates + 下列单测（`--quick` 跳过工地 Excel） |
| `test_booking_regression.py` | 订柜 N0* / 空心体积 / 铁架条带 |
| `test_nonstandard_tools.py` | nonstandard.inspect/enrich 实跑 |
| `test_cog_shift_mid_ok.py` | mid50 OK 贴墙不纵向拉开 |
| `test_phase0_task_success.py` | task_success 计分单元 |
| `test_facade_sme_mini.py` | 幕墙 SME 小票 A→B 闭环 |
| `test_hollow_volume_n0.py` | 空心 outer 不绑架订舱体积 |
| `competition_smoke.ps1` | 评委向 hard gates + scorecard |

