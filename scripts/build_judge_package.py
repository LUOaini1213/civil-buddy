#!/usr/bin/env python3
"""
评委/提交用标准产物包（提分项 1～4 一次打包）。

含：
  - 错误 vs 正确口径对照
  - 主案例 N0/3D 数字
  - 已发 2 柜对照
  - 风险 REJECT 样例（若有/可生成）
  - 启动命令 A/B
  - 双轨说明

  python scripts/build_judge_package.py
  python scripts/build_judge_package.py --refresh   # 先跑 demo + agent trace
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "judge_package"


def run(cmd: list[str], timeout: int = 600) -> int:
    print(">>", " ".join(cmd))
    return subprocess.run(cmd, cwd=str(ROOT), timeout=timeout).returncode


def load_json(p: Path) -> dict:
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="重跑 site + shipped + agent trace")
    ap.add_argument("--skip-agent-trace", action="store_true")
    args = ap.parse_args()

    if args.refresh:
        run([sys.executable, "scripts/demo_vmu1_site.py", "--with-shipped"])
        if not args.skip_agent_trace:
            run([sys.executable, "scripts/demo_nine_agents_trace.py"])

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    pack = OUT / f"pack_{ts}"
    pack.mkdir(parents=True, exist_ok=True)

    # 1) 对照叙事
    for rel in (
        "docs/wrong-vs-right-narrative.md",
        "docs/submission-demo-A-B.md",
        "docs/agents-vs-tools.md",
        "docs/completion-checklist.md",
        "docs/volume-algorithm.md",
    ):
        src = ROOT / rel
        if src.exists():
            shutil.copy2(src, pack / src.name)

    # 2) 主案例数字
    site = load_json(ROOT / "output/vmu1_site_only/vmu1_site_only_pack.json")
    ship = load_json(ROOT / "output/vmu1_shipped/vmu1_shipped_REDACTED-REF_pack.json")
    trace = load_json(ROOT / "output/agent_trace_demo.json")

    book = (site.get("pack") or {}).get("booking") or {}
    snap = (site.get("pack") or {}).get("snapshot") or {}
    n0 = book.get("n0") or snap.get("n0")
    used = snap.get("containers_used")
    can = snap.get("can_fit")
    n_wt = book.get("containers_by_weight")
    n_vol = book.get("containers_by_volume")
    bind = book.get("binding_constraint")
    v_eff = book.get("volume_m3")
    outer_sum = book.get("crate_outer_m3")
    book_u = snap.get("booking_volume_util")
    outer_u = snap.get("space")
    wt_u = snap.get("weight")

    ship_n0 = (ship.get("booking") or {}).get("n0")
    ship_used = (ship.get("layout_3d") or {}).get("containers_used")
    ship_doc = ship.get("doc_cabinet_gross_kg") or {}

    risk = (trace.get("summary") or {}).get("risk")
    risk_can = (trace.get("summary") or {}).get("can_fit")

    # 复制原始产物
    for src in (
        ROOT / "output/vmu1_site_only/VMU1_送工地_剩余装柜估算.md",
        ROOT / "output/vmu1_site_only/vmu1_site_only_pack.json",
        ROOT / "output/vmu1_shipped/VMU1_已发货_REDACTED-REF_装柜复算.md",
        ROOT / "output/agent_trace_demo.json",
        ROOT / "output/vmu1_nine_passthrough.json",
    ):
        if src.exists():
            shutil.copy2(src, pack / src.name)

    img = pack / "images"
    img.mkdir(exist_ok=True)
    for p in sorted(
        ROOT.glob("output/side_*.png"), key=lambda x: x.stat().st_mtime, reverse=True
    )[:8]:
        shutil.copy2(p, img / p.name)

    # 3) 一页总览 INDEX.md
    index = f"""# 评委产物包 · VMU 主案例

生成：{datetime.now().isoformat(timespec="seconds")}

## 0. 一句话

系统曾因**外廓虚高**报约 **15** 柜（错误口径）；修正体积定义后，与业务真实约 **2** 柜对齐。  
**不是**创造运力，而是**纠正错算**。详见 `wrong-vs-right-narrative.md`。

## 1. 错误口径 vs 正确口径

| 项 | 错误（旧） | 正确（现） |
|----|------------|------------|
| 订柜分子 | Σ 外廓实心 | V_eff = pack_effective / min(outer, content×k) |
| ~15 柜 | 像真要 15 柜 | **系统错算** |
| ~2 柜 | 像硬凑 | **重量+有效体积 + 装货单** |
| 外廓利用率 | 当订舱依据 | 仅 3D 展示 |

## 2. 主案例数字（剩余工地）

| 口径 | 值 |
|------|-----|
| **订柜 N0** | **{n0}**（重量柜 {n_wt} / 有效体积柜 {n_vol} / 绑定 {bind}） |
| **3D 用柜** | **{used}**（can_fit={can}） |
| V_eff / 外廓合计 | {v_eff} m³ / {outer_sum} m³ |
| 订柜有效体积率 | {book_u} |
| 外廓摆柜率 | {outer_u}（非订舱） |
| 重量利用率 | {wt_u} |

## 3. 已发 REDACTED-REF 对照

| 口径 | 值 |
|------|-----|
| 装货单分柜毛重 | {ship_doc} |
| 算法 N0 / 3D | {ship_n0} / {ship_used} |

## 4. Agent 价值样例（装得下仍可能拒）

| 项 | 值 |
|----|-----|
| can_fit | {risk_can} |
| 风险 decision | **{risk}** |
| 说明 | 纯 booking 脚本只报 can_fit；Agent 可 **REJECT** 重心/结构等 |

完整 steps：`agent_trace_demo.json`（本地 `python scripts/demo_nine_agents_trace.py`）

## 5. 双轨（不打架）

| 轨 | 命令 | 证明 |
|----|------|------|
| A 数字 | `python scripts/demo_vmu1_site.py` | 订舱 N0 |
| B Agent+API | `uvicorn gateway.app:app --port 8000` 后 `POST /api/pipeline/trace` | 闭环过程 |

**共用 tools 算数**；详见 `agents-vs-tools.md`、`submission-demo-A-B.md`。

## 6. 启动与测试（复制进说明文档）

```bash
pip install -r requirements.txt

# 数字
python scripts/demo_vmu1_site.py --with-shipped

# 回归
python scripts/run_precommit_tests.py --quick

# Agent API
python -m uvicorn gateway.app:app --host 127.0.0.1 --port 8000
# 另窗：
python scripts/demo_nine_agents_trace.py --via-api
```

### 三个测试请求

1. `GET  http://127.0.0.1:8000/api/health`
2. `POST http://127.0.0.1:8000/api/pipeline/trace`  body: `{{"user_input":"demo","container_type":"40HQ"}}`
3. `POST /api/team-a` → `POST /api/confirm`（`max_containers`: 0）

## 7. 创新点一句

多智能体成箱+拼柜；订柜用有效体积、外廓只做 3D；避免空心包装虚高柜数。

## 8. 本包文件

- `INDEX.md`（本页）
- `wrong-vs-right-narrative.md`
- `VMU1_送工地_剩余装柜估算.md` / `vmu1_site_only_pack.json`
- `VMU1_已发货_REDACTED-REF_装柜复算.md`（若有）
- `agent_trace_demo.json`（风险样例）
- `images/` 侧视图
- 其它说明 md
"""
    (pack / "INDEX.md").write_text(index, encoding="utf-8")

    # machine-readable summary
    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "narrative": "15=wrong outer booking; 2=true business after fix",
        "site": {
            "n0": n0,
            "n_weight": n_wt,
            "n_volume": n_vol,
            "binding": bind,
            "containers_used": used,
            "can_fit": can,
            "v_eff": v_eff,
            "outer_sum": outer_sum,
            "booking_volume_util": book_u,
            "outer_space_util": outer_u,
            "weight_util": wt_u,
        },
        "shipped_REDACTED-REF": {
            "n0": ship_n0,
            "containers_used": ship_used,
            "doc_cabinets": ship_doc,
        },
        "agent_risk_example": {
            "can_fit": risk_can,
            "decision": risk,
        },
        "commands": {
            "demo_a": "python scripts/demo_vmu1_site.py --with-shipped",
            "precommit": "python scripts/run_precommit_tests.py --quick",
            "gateway": "python -m uvicorn gateway.app:app --host 127.0.0.1 --port 8000",
            "demo_b": "python scripts/demo_nine_agents_trace.py --via-api",
            "build_this": "python scripts/build_judge_package.py --refresh",
        },
    }
    (pack / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    latest = OUT / "latest"
    if latest.exists():
        shutil.rmtree(latest, ignore_errors=True)
    shutil.copytree(pack, latest)

    print("JUDGE PACKAGE", pack)
    print("LATEST", latest)
    print("N0", n0, "3D", used, "ship", ship_n0, "risk", risk)
    print("Open:", latest / "INDEX.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
