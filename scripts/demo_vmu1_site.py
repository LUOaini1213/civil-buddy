#!/usr/bin/env python3
"""
【比赛演示主路径 · 10 分钟内可复现】

导入 VMU 工地 Excel → 自主定柜 N0 + 3D + 双口径结论 → 标准产物包。

用法（仓库根目录）:
  python scripts/demo_vmu1_site.py
  python scripts/demo_vmu1_site.py --with-shipped   # 附带已发 FST0003 复算

不写死柜数；订柜用有效体积，外廓仅 3D。
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
sys.path.insert(0, str(ROOT))

OUT_DEMO = ROOT / "output" / "demo_package"
OUT_SITE = ROOT / "output" / "vmu1_site_only"
OUT_SHIP = ROOT / "output" / "vmu1_shipped"


def _run(cmd: list[str], timeout: int = 300) -> int:
    print(">>", " ".join(cmd))
    r = subprocess.run(cmd, cwd=str(ROOT), timeout=timeout)
    return int(r.returncode)


def assemble_package(*, with_shipped: bool) -> Path:
    OUT_DEMO.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    pack = OUT_DEMO / f"vmu1_site_{ts}"
    pack.mkdir(parents=True, exist_ok=True)

    # 主结论
    for name in (
        "VMU1_送工地_剩余装柜估算.md",
        "vmu1_site_only_pack.json",
        "materials_vmu1_site_remaining.xlsx",
    ):
        src = OUT_SITE / name
        if src.exists():
            shutil.copy2(src, pack / name)

    if with_shipped:
        for name in (
            "VMU1_已发货_FST0003_装柜复算.md",
            "vmu1_shipped_fst0003_pack.json",
        ):
            src = OUT_SHIP / name
            if src.exists():
                shutil.copy2(src, pack / name)

    # 最新侧视图（若有）
    side_dir = pack / "images"
    side_dir.mkdir(exist_ok=True)
    sides = sorted(ROOT.glob("output/side_*.png"), key=lambda p: p.stat().st_mtime, reverse=True)
    for p in sides[:6]:
        shutil.copy2(p, side_dir / p.name)

    # 叙事一页纸
    site_json = OUT_SITE / "vmu1_site_only_pack.json"
    n0 = used = can = "?"
    if site_json.exists():
        d = json.loads(site_json.read_text(encoding="utf-8"))
        book = (d.get("pack") or {}).get("booking") or {}
        snap = (d.get("pack") or {}).get("snapshot") or {}
        n0 = book.get("n0") or snap.get("n0")
        used = snap.get("containers_used")
        can = snap.get("can_fit")

    narrative = f"""# 演示产物包 · VMU1 送工地

生成时间：{datetime.now().isoformat(timespec="seconds")}

## 30 秒结论（对领导/评委）

| 口径 | 本包结果 | 怎么讲 |
|------|----------|--------|
| **订柜 N0** | **{n0}** | 重量 + 有效包装体积，**订舱用这个** |
| **3D 建议柜数** | **{used}**（can_fit={can}） | 当量外廓摆柜上界，可与 N0 不同 |
| 已发 FST0003 | 2 柜（装货单） | 对照样例，非写死约束 |

**创新点一句：** 多智能体成箱+拼柜；订柜用有效体积，外廓只做 3D；避免空心包装虚高柜数。

## 文件清单

- `VMU1_送工地_剩余装柜估算.md` — 主结论
- `vmu1_site_only_pack.json` — 可复现数字
- `materials_vmu1_site_remaining.xlsx` — 当量材料/箱输入
- `images/` — 最近侧视图（若本机曾出图）
- 可选：`VMU1_已发货_FST0003_装柜复算.md` — 已发 2 柜复算

## 复现命令

```bash
# 依赖：pip install -r requirements.txt
python scripts/demo_vmu1_site.py
# 或分步：
python scripts/run_vmu1_site_only.py
python scripts/run_vmu1_shipped_fst0003.py   # 可选已发
```

## 提交前必跑

```bash
python scripts/run_precommit_tests.py
```
"""
    (pack / "README.md").write_text(narrative, encoding="utf-8")

    # 固定 latest 软链式拷贝（Windows 用目录覆盖）
    latest = OUT_DEMO / "latest"
    if latest.exists():
        shutil.rmtree(latest, ignore_errors=True)
    shutil.copytree(pack, latest)
    print("PACKAGE", pack)
    print("LATEST ", latest)
    return pack


def main() -> int:
    ap = argparse.ArgumentParser(description="VMU1 工地演示主路径")
    ap.add_argument("--with-shipped", action="store_true", help="同时复算已发 FST0003")
    ap.add_argument("--skip-run", action="store_true", help="只打包已有 output，不重跑")
    args = ap.parse_args()

    print("=" * 60)
    print(" DEMO: VMU1 送工地 · 自主定柜（有效体积订柜）")
    print("=" * 60)

    if not args.skip_run:
        rc = _run([sys.executable, "scripts/run_vmu1_site_only.py"], timeout=600)
        if rc != 0:
            print("FAIL run_vmu1_site_only", rc)
            return rc
        if args.with_shipped:
            rc2 = _run([sys.executable, "scripts/run_vmu1_shipped_fst0003.py"], timeout=300)
            if rc2 != 0:
                print("WARN shipped script failed", rc2)

    pack = assemble_package(with_shipped=args.with_shipped or (OUT_SHIP / "VMU1_已发货_FST0003_装柜复算.md").exists())

    # 控制台摘要
    md = OUT_SITE / "VMU1_送工地_剩余装柜估算.md"
    if md.exists():
        text = md.read_text(encoding="utf-8")
        print("\n----- 结论摘录 -----")
        for line in text.splitlines():
            if "订柜 N0" in line or "3D 建议" in line or "N0=" in line or "按重量" in line:
                print(line)
        print("----- 产物 -----")
    print("标准产物包:", pack)
    print("快捷入口:  output/demo_package/latest/README.md")
    print("OK DEMO DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
