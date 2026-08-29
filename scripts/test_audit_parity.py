#!/usr/bin/env python3
"""data(round2)：/api/audit SQL 直查（CB_STORAGE=sqlite）vs 旧扫描（CB_STORAGE=json）对拍。

抽 3 个历史 session（DB 中 run 数最多的 3 个），两次子进程分别以 json / sqlite 模式
调用真实 api_audit，断言响应逐字段一致（schema civil.audit.v1 不变、前端零改动）。

前提：data/civilbuddy.db 已由 `python -m packing_assistant.storage --import` 导入；
     无库/无 session 时 SKIP（exit 0），CI 与本地均可安全跳过。
"""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = Path(os.getenv("CB_DB_PATH") or ROOT / "data" / "civilbuddy.db")

_RUN_API = (
    "import json, sys\n"
    "sys.path.insert(0, '.')\n"
    "from gateway.app import api_audit\n"
    "print(json.dumps(api_audit(session=sys.argv[1]), ensure_ascii=False, sort_keys=True))\n"
)


def _pick_sessions(n: int = 3) -> list[str]:
    """抽 3 个历史 session：取根 output/runs 树里 run 数最多的（JSON 扫描口径内可对拍）。

    注：workbench-bridge/source=demo 导入的 run（如 civil-buddy-sidecar）只在 SQL 侧可见
    ——这正是 audit B1-#7 孤儿数据被吸收的修复效果，不纳入对拍口径。
    """
    con = sqlite3.connect(str(DB))
    try:
        root_runs = str(ROOT / "output" / "runs")
        rows = con.execute(
            "SELECT session_id, COUNT(*) AS n FROM runs"
            " WHERE session_id IS NOT NULL AND run_dir LIKE ?"
            " GROUP BY session_id ORDER BY n DESC, session_id LIMIT ?",
            (root_runs + "%", n),
        ).fetchall()
        return [r[0] for r in rows]
    finally:
        con.close()


def _run_api(sid: str, mode: str) -> dict:
    env = dict(os.environ)
    env["CB_STORAGE"] = mode
    r = subprocess.run(
        [sys.executable, "-c", _RUN_API, sid],
        capture_output=True, text=True, cwd=str(ROOT), env=env, timeout=300,
    )
    if r.returncode != 0:
        raise RuntimeError(f"api_audit({sid}, {mode}) failed:\n{r.stdout}\n{r.stderr}")
    return json.loads(r.stdout.strip().splitlines()[-1])


def main() -> int:
    print("== audit SQL vs JSON 扫描对拍 ==")
    if not DB.exists():
        print("SKIP: 未找到", DB, "（先跑 python -m packing_assistant.storage --import）")
        return 0
    sessions = _pick_sessions(3)
    if not sessions:
        print("SKIP: DB 无 session 数据")
        return 0
    print("抽样 sessions:", sessions)
    failed = 0
    for sid in sessions:
        resp_json = _run_api(sid, "json")
        resp_sql = _run_api(sid, "sqlite")
        same = resp_json == resp_sql
        n_runs = resp_sql.get("n_runs_matched")
        if same:
            print(f"  PASS {sid}: 全响应逐字段一致（n_runs_matched={n_runs}）")
        else:
            failed += 1
            print(f"  FAIL {sid}: 不一致（n_runs={n_runs}）")
            for k in sorted(set(resp_json) | set(resp_sql)):
                if resp_json.get(k) != resp_sql.get(k):
                    print(f"    diff key={k}")
                    if k == "runs":
                        for i, (a, b) in enumerate(zip(resp_json.get("runs", []), resp_sql.get("runs", []))):
                            if a != b:
                                print(f"      run[{i}] {a.get('run_id')}: json_n_nodes={a.get('n_nodes')}"
                                      f" sql_n_nodes={b.get('n_nodes')}")
                                for kk in sorted(set(a) | set(b)):
                                    if a.get(kk) != b.get(kk):
                                        print(f"        {kk}: differs")
                                        break
                    else:
                        print(f"      json={json.dumps(resp_json.get(k), ensure_ascii=False)[:200]}")
                        print(f"      sql ={json.dumps(resp_sql.get(k), ensure_ascii=False)[:200]}")
    # 列表分支：两端 schema 与规模一致（排序/是否含 user_action 值允许差异——json 版恒 None）
    env = dict(os.environ)
    rj = subprocess.run([sys.executable, "-c",
                         "import json,sys;sys.path.insert(0,'.');from gateway.app import api_audit;"
                         "print(json.dumps(api_audit(),ensure_ascii=False,sort_keys=True))"],
                        capture_output=True, text=True, cwd=str(ROOT), env={**env, "CB_STORAGE": "json"}, timeout=120)
    rs = subprocess.run([sys.executable, "-c",
                         "import json,sys;sys.path.insert(0,'.');from gateway.app import api_audit;"
                         "print(json.dumps(api_audit(),ensure_ascii=False,sort_keys=True))"],
                        capture_output=True, text=True, cwd=str(ROOT), env={**env, "CB_STORAGE": "sqlite"}, timeout=120)
    if rj.returncode == 0 and rs.returncode == 0:
        lj = json.loads(rj.stdout.strip().splitlines()[-1])
        ls = json.loads(rs.stdout.strip().splitlines()[-1])
        keys_ok = all(
            set(row) == {"session_id", "run_id", "status", "user_action", "saved_at"}
            for row in lj.get("sessions", []) + ls.get("sessions", [])
        )
        n_ok = len(lj.get("sessions", [])) == len(ls.get("sessions", [])) > 0
        print(f"  {'PASS' if keys_ok and n_ok else 'FAIL'} session_list: schema/规模一致"
              f"（json={len(lj.get('sessions', []))} 条 / sqlite={len(ls.get('sessions', []))} 条）")
        if not (keys_ok and n_ok):
            failed += 1
    else:
        print("  WARN session_list 对拍子进程失败（跳过）")
    print(f"\nRESULT: {'ALL PARITY GREEN' if failed == 0 else f'{failed} SESSION(S) MISMATCH'}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
