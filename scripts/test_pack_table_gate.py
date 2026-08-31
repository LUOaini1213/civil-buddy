#!/usr/bin/env python3
"""把 exe 侧的表格装箱门禁（workbench/tests/pack_table.rs）接进 precommit。

为什么单独包一层而不直接在 precommit 里调 cargo：
  CI 目前**完全不跑 cargo**（ci.yml 里只有 `test_rag_parity.py --skip-rust`），
  所以 workbench/tests/ 下的所有 Rust 门禁从来没在 CI 上跑过。在本机 precommit
  里补上，是当下成本最低、又真能挡住回归的位置。

没有 cargo 时 SKIP 而不是 FAIL —— 与 scripts/test_projects_parity.py 同一约定，
免得没装 Rust 工具链的环境（含 CI）恒红。

用法：python scripts/test_pack_table_gate.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

    if shutil.which("cargo") is None:
        print("SKIP 表格装箱门禁：本环境没有 cargo")
        return 0

    r = subprocess.run(
        ["cargo", "test", "--release", "--test", "pack_table"],
        cwd=str(ROOT / "workbench"),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=1800,
    )
    tail = (r.stdout or "") + (r.stderr or "")
    if r.returncode != 0:
        print("FAIL 表格装箱门禁（exe 侧）：给了表格路径读不到时没如实说明")
        print(tail[-3000:])
        return 1
    for line in tail.splitlines():
        if line.startswith("test result:"):
            print("PASS 表格装箱门禁（exe 侧）：" + line.strip())
            return 0
    print("PASS 表格装箱门禁（exe 侧）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
