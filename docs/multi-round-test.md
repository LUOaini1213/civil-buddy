# 多轮测试 Workflow

## 脚本

```bash
# 默认 quick 套件 × 3 轮
python scripts/run_multi_round_tests.py

# 冒烟 2 轮
python scripts/run_multi_round_tests.py --suite smoke --rounds 2

# Agent 闭环 3 轮
python scripts/run_multi_round_tests.py --suite agent --rounds 3

# 全量（含 precommit --quick）2 轮
python scripts/run_multi_round_tests.py --suite full --rounds 2

# 失败即停
python scripts/run_multi_round_tests.py --stop-on-fail
```

## 套件

| suite | 内容 |
|-------|------|
| **smoke** | 体积门禁 + 评估权重 + 详设/待详设 + NL 解析 |
| **quick** | smoke + booking_regression + p2_volume_gates |
| **agent** | smoke + demo_agent_closed_loop |
| **full** | quick + agent + precommit --quick |

## 产物

```text
output/multi_round_tests/
  latest.json
  multi_round_<suite>_<ts>.json
  multi_round_<suite>_<ts>.md
```

## Workflow

`.grok/workflows/multi-round-test.rhai`

```text
args: { "suite": "quick", "rounds": 3 }
```

阶段：Plan → Run → Report。  
在 `/workflows` 查看；信任项目 workflows 后可 `/workflow multi-round-test`。
