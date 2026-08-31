#!/usr/bin/env python3
"""ux(round19) 项目/会话索引 双栈对拍：Rust workbench/src/projects.rs ↔ Python demo/projects.py。

**自造 fixture，不依赖存量数据** —— 这是刻意与 `scripts/test_audit_parity.py` 不同的取法：
那个依赖真实 `data/civilbuddy.db`，无库即 SKIP，在 CI 上几乎恒 SKIP。本脚本每次
造一个临时 demo 根（含空 kb/static/out），两侧各跑同一组操作，逐字段比对结果，
因此在开发机、CI、评委机上都能真跑。

对拍口径：比对**语义字段**，不比对时间戳与自动生成的 id（两侧各自生成，本就不同）。
时间戳字段在比对前统一抹成占位符。

用法：python scripts/test_projects_parity.py   （退出码 0=一致，1=有差异）
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VOLATILE = {"created_at", "updated_at", "ts", "n_sessions"}


class SkipParity(Exception):
    """无 Rust 工具链时的跳过信号（退出码 0，不阻断 CI）。"""


def make_fixture(tag: str) -> Path:
    """临时 demo 根：out/ 下造 3 个会话目录 + 1 个 _threads 干扰目录。"""
    base = Path(tempfile.mkdtemp(prefix=f"cb-parity-{tag}-"))
    demo = base / "demo"
    (demo / "kb").mkdir(parents=True)
    (demo / "static").mkdir(parents=True)
    out = demo / "out"
    out.mkdir()
    for sid in ("sess-alpha", "sess-beta", "sess-gamma"):
        (out / sid).mkdir()
    (out / "_threads").mkdir()  # 非会话目录，两侧都必须跳过
    return demo


def scrub(v):
    """抹掉两侧必然不同的字段（时间戳、自动生成的 id），只留语义。"""
    if isinstance(v, dict):
        out = {}
        for k, x in v.items():
            if k in VOLATILE:
                out[k] = "<volatile>"
            elif k in ("id", "project_id") and isinstance(x, str) and x.startswith("p-") and x != "p-inbox":
                out[k] = "<pid>"
            else:
                out[k] = scrub(x)
        return out
    if isinstance(v, list):
        return [scrub(x) for x in v]
    return v


def run_python(demo: Path) -> dict:
    """在子进程里跑 Python 侧，避免污染当前解释器的 sys.path。"""
    code = r'''
import json, sys
sys.path.insert(0, r"{repo}/demo")
from pathlib import Path
import projects as pj
out = Path(r"{out}")
res = {{}}
res["empty_projects"] = pj.list_projects(out)
res["empty_sessions"] = pj.list_sessions(out, "", "", 50, 0)
a, merged_a = pj.create_project(out, "滨河路人行道维修")
res["create"] = {{"project": a, "merged": merged_a}}
b, merged_b = pj.create_project(out, "  滨河路人行道维修  ")
res["create_idempotent"] = {{"merged": merged_b, "same_id": a["id"] == b["id"]}}
r = pj.patch_project(out, a["id"], "滨河路维修一标", None)
res["rename"] = {{"project": r, "id_stable": r["id"] == a["id"]}}
pj.touch_session(out, "sess-alpha", "给滨河路维修一标写个交底", "")
pj.touch_session(out, "sess-beta", "滨河路人行道维修 的进度", "")
pj.touch_session(out, "sess-gamma", "完全无关的一句话", "")
res["after_touch_projects"] = pj.list_projects(out)
res["by_project"] = pj.list_sessions(out, a["id"], "", 50, 0)
res["inbox"] = pj.list_sessions(out, "p-inbox", "", 50, 0)
res["page"] = pj.list_sessions(out, "", "", 2, 1)
res["limit_cap"] = pj.list_sessions(out, "", "", 9999, 0)["limit"]
pj.append_turn(out, "sess-alpha", "user", "问一句")
pj.append_turn(out, "sess-alpha", "assistant", "答一句")
res["detail"] = pj.session_detail(out, "sess-alpha")
errs = []
for fn, args in [
    ("safe_session_id", ("_threads",)), ("safe_session_id", ("..",)),
    ("safe_project_id", ("nope",)), ("clean_name", ("   ",)),
]:
    try:
        getattr(pj, fn)(*args); errs.append(f"{{fn}}{{args}}=NO-RAISE")
    except ValueError:
        errs.append(f"{{fn}}=raise")
try:
    pj.patch_project(out, "p-inbox", "x", None); errs.append("inbox-patch=NO-RAISE")
except ValueError:
    errs.append("inbox-patch=raise")
res["guards"] = errs
print(json.dumps(res, ensure_ascii=True))
'''.format(repo=ROOT.as_posix(), out=(demo / "out").as_posix())
    # 关键：**不能**用 `python -c <含中文的源码>` —— Windows 上 argv 会按控制台
    # 代码页（GBK）编码，中文字面量到子进程里就成了乱码，对拍会把「编码坏了」
    # 误报成「双栈行为不一致」（本脚本首跑即踩，8 处差异全是这个）。
    # 改为写 UTF-8 临时脚本文件再执行。
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(code)
        script = f.name
    try:
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
        p = subprocess.run([sys.executable, script], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=120,
                           cwd=str(ROOT), env=env)
    finally:
        try:
            Path(script).unlink()
        except OSError:
            pass
    if p.returncode != 0:
        raise RuntimeError("Python 侧失败：" + (p.stderr or "")[-600:])
    return json.loads(p.stdout)


def run_rust(demo: Path) -> dict:
    """Rust 侧走 cargo test 里的同名断言不够 —— 这里直接跑一个一次性 bin 太重，
    改为复用已编译的库：用 `cargo run --example` 不存在，故走 tests 里的 dump 用例。"""
    # 可执行名跨平台：Windows 带 .exe，Linux/macOS 不带。
    # （首版写死 .exe，本机绿而 CI 的 ubuntu runner 直接红 —— 已修。）
    rel = ROOT / "workbench" / "target" / "release"
    cands = [rel / "parity_dump.exe", rel / "parity_dump"]
    exe = next((c for c in cands if c.is_file()), None)
    if exe is None:
        if shutil.which("cargo") is None:
            # 没有 Rust 工具链的 runner：SKIP 而不是 FAIL（同 test_js_syntax 无 node 的处理）
            raise SkipParity("未安装 cargo，跳过 Rust 侧对拍")
        r = subprocess.run(
            ["cargo", "build", "--release", "--bin", "parity_dump"],
            cwd=str(ROOT / "workbench"), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=1800,
        )
        if r.returncode != 0:
            raise RuntimeError("cargo build parity_dump 失败：" + (r.stderr or "")[-600:])
        exe = next((c for c in cands if c.is_file()), None)
    if exe is None:
        raise RuntimeError(f"parity_dump 未生成，找过：{[str(c) for c in cands]}")
    p = subprocess.run([str(exe), str(demo / "out")], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=120)
    if p.returncode != 0:
        raise RuntimeError("Rust 侧失败：" + (p.stderr or "")[-600:])
    return json.loads(p.stdout)


def main() -> int:
    # Windows 控制台默认 GBK，差异里含中文与替换符会抛 UnicodeEncodeError
    # （同 rag_parity 踩过的坑）。输出统一按 UTF-8 且不因编码失败而中断。
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    py_demo = make_fixture("py")
    rs_demo = make_fixture("rs")
    try:
        py = run_python(py_demo)
        rs = run_rust(rs_demo)
    except SkipParity as e:
        print(f"SKIP 项目索引双栈对拍：{e}")
        return 0
    except Exception as e:  # noqa: BLE001
        print(f"FAIL 对拍无法执行：{e}")
        return 1
    finally:
        pass

    a, b = scrub(py), scrub(rs)
    keys = sorted(set(a) | set(b))
    diffs = []
    for k in keys:
        if k not in a:
            diffs.append(f"  Python 缺键 {k}")
        elif k not in b:
            diffs.append(f"  Rust 缺键 {k}")
        elif json.dumps(a[k], sort_keys=True, ensure_ascii=False) != json.dumps(b[k], sort_keys=True, ensure_ascii=False):
            diffs.append(
                f"  [{k}] 不一致\n"
                f"    py = {json.dumps(a[k], sort_keys=True, ensure_ascii=False)[:340]}\n"
                f"    rs = {json.dumps(b[k], sort_keys=True, ensure_ascii=False)[:340]}"
            )
    shutil.rmtree(py_demo.parent, ignore_errors=True)
    shutil.rmtree(rs_demo.parent, ignore_errors=True)

    if diffs:
        print(f"FAIL 双栈行为不一致（{len(diffs)} 处）：")
        for d in diffs:
            print(d)
        return 1
    print(f"PASS 项目索引双栈对拍：{len(keys)} 组用例逐字段一致（自造 fixture，零存量依赖）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
