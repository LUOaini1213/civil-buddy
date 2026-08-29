#!/usr/bin/env python3
"""RAG 三栈对拍 + 金句守卫 + 性能红线（data-plan M3/M4 · D-R3）。

对拍基准（任务红线）：test/eval/rag_golden_cases.json（≥30 条，中英/2字短查/长问/跨层）
  1) parity：旧实现（CB_RAG=json 全盘扫描）vs 新实现（CB_RAG=fts，FTS5 粗召回+现行公式精排）
     top-3 重合率 ≥95%（逐案 |old∩new| / max(len) 取均值）；
  2) 金句守卫：新实现 top-3 必须命中 expect_paths 任一（demo_kb 侧首个金句资产，audit A3-4）；
  3) Rust 对拍（M4）：workbench/target/release/civil-rag-probe.exe 存在时，
     Rust FTS 实现 vs Python 新实现 demo_kb top-3 重合率 ≥95%（exe 缺失则 SKIP 并说明）；
  4) 性能红线：kb 检索 P50 < 50ms（timeit 20 次，两栈各测）；
  5) 写钩子：kbio 落盘 → reindex_kb_file 即时可见（编辑→检索）。

用法：python scripts/test_rag_parity.py [--skip-rust]
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "demo"))

GOLDEN = ROOT / "test" / "eval" / "rag_golden_cases.json"
PROBE = ROOT / "workbench" / "target" / "release" / ("civil-rag-probe.exe" if os.name == "nt" else "civil-rag-probe")
PARITY_THRESHOLD = 0.95
P50_LIMIT_MS = 50.0


def _overlap(a: list[str], b: list[str]) -> float:
    if not a and not b:
        return 1.0
    return len(set(a) & set(b)) / max(len(a), len(b), 1)


def main() -> int:
    os.environ.setdefault("CB_DB_PATH", str(ROOT / "data" / "civilbuddy.db"))
    from catalog import get_expert  # noqa: E402  (demo stack)

    from packing_assistant.kb_search import reindex_kb_file, rag_mode  # noqa: E402
    from packing_assistant.tools.search_knowledge import search_knowledge  # noqa: E402
    import rag as demo_rag  # noqa: E402

    cases = json.loads(GOLDEN.read_text(encoding="utf-8"))["items"]
    print(f"golden cases: {len(cases)} "
          f"(demo={sum(1 for c in cases if c['stack'] == 'demo_kb')}, "
          f"kb={sum(1 for c in cases if c['stack'] == 'knowledge_base')})")

    def run_top3(case: dict, mode: str) -> list[str]:
        os.environ["CB_RAG"] = mode
        assert rag_mode() == mode
        if case["stack"] == "demo_kb":
            e = get_expert(case["expert_id"])
            return [h.path for h in demo_rag.search_kb(e.id, e.category, case["q"], limit=3)]
        return [h["path"] for h in search_knowledge(case["q"], limit=3)["hits"]]

    # ---------- 1) parity 旧 vs 新 ----------
    rows, bad_recall = [], []
    for c in cases:
        old, new = run_top3(c, "json"), run_top3(c, "fts")
        exp = c["expect_paths"]
        if not set(new) & set(exp):
            bad_recall.append((c["id"], c["q"], new, exp))
        rows.append((c["id"], c["stack"], c["q"], _overlap(old, new), old, new))
    mean_overlap = sum(r[3] for r in rows) / len(rows)
    perfect = sum(1 for r in rows if r[3] >= 1.0)
    for rid, stack, q, ov, old, new in rows:
        if ov < 1.0:
            print(f"  DIFF {rid} [{stack}] {q!r} overlap={ov:.2f}\n    old={old}\n    new={new}")
    print(f"[1] parity old(json) vs new(fts): mean top-3 overlap = {mean_overlap:.4f} "
          f"({perfect}/{len(rows)} perfect) threshold>={PARITY_THRESHOLD}")
    ok = mean_overlap >= PARITY_THRESHOLD

    # ---------- 2) 金句守卫（新实现 recall） ----------
    print(f"[2] golden recall (new impl, expect_paths any-in-top3): "
          f"{len(rows) - len(bad_recall)}/{len(rows)}")
    for rid, q, new, exp in bad_recall:
        print(f"  MISS {rid} {q!r} got={new} expect_any={exp}")
    ok = ok and not bad_recall

    # ---------- 3) Rust 对拍 ----------
    if os.getenv("SKIP_RUST") == "1" or (len(sys.argv) > 1 and "--skip-rust" in sys.argv):
        print("[3] rust parity: SKIP (--skip-rust)")
    elif not PROBE.is_file():
        print(f"[3] rust parity: SKIP (probe not built: {PROBE}; cargo build --release 后重跑)")
    else:
        import re as _re

        contract = json.loads(
            (ROOT / "contract" / "kb_boosts.v1.json").read_text(encoding="utf-8"))["rules"]

        def _old_rust_top3(case: dict) -> list[str]:
            """HEAD(14ec2bd) rag.rs 扫描语义的等价模拟：demo 公式 + 硬编码 boost
            （数据源=contract/kb_boosts.v1.json，验证数据化前后行为一致）。"""
            e = get_expert(case["expert_id"])
            q = _re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z0-9_\-]{2,}", case["q"].lower())
            qstrip = case["q"].strip()
            sg = "sg" in " ".join(q) or "singapore" in " ".join(q) or "ptw" in " ".join(q) \
                or "wsh" in " ".join(q) or "scdf" in " ".join(q) or "pub" in " ".join(q) \
                or "新加坡" in case["q"]
            scored = []
            for layer, root in demo_rag.kb_layers(e.id, e.category):
                for p in demo_rag._iter_md(root):
                    text = p.read_text(encoding="utf-8", errors="ignore")
                    bag = set(demo_rag._tokens(text))
                    s = sum(2.0 for t in q if t in bag)
                    if qstrip and qstrip in text:
                        s += 8.0
                    name = p.name.lower()
                    s += sum(3.0 for t in q if t in name)
                    for r in contract:
                        if r["kind"] == "filename_eq" and name == r["value"].lower() \
                                and r.get("scope", "demo_kb") == "demo_kb":
                            s += r["boost"]
                        elif r["kind"] == "body_contains" and r["value"] in text:
                            s += r["boost"]
                    if sg:
                        for r in contract:
                            if r["kind"] == "sg_query_penalty" and (
                                r["match_filename"] in p.name or r["match_body"] in text
                            ):
                                s += r["boost"]
                    if s <= 0:
                        continue
                    scored.append((-s, layer != "expert",
                                   str(p.relative_to(demo_rag.KB_ROOT)).replace("\\", "/")))
            scored.sort()
            return [p for _, _, p in scored[:3]]

        rust_rows, drift_rows = [], []
        for c in cases:
            if c["stack"] != "demo_kb":
                continue
            new = run_top3(c, "fts")
            out = subprocess.run(
                [str(PROBE), c["expert_id"], c["category"], c["q"], "3"],
                capture_output=True, text=True, timeout=60, cwd=str(ROOT),
            )
            try:
                hits = json.loads(out.stdout)["hits"]
            except Exception:
                print(f"  PROBE-FAIL {c['id']}: rc={out.returncode} err={out.stderr.strip()[:200]}")
                rust_rows.append((c["id"], 0.0))
                continue
            rust = [h["path"] for h in hits]
            rust_rows.append((c["id"], _overlap(_old_rust_top3(c), rust)))
            drift_rows.append((c["id"], _overlap(new, rust)))
        rmean = sum(v for _, v in rust_rows) / max(len(rust_rows), 1)
        rperfect = sum(1 for _, v in rust_rows if v >= 1.0)
        for rid, v in rust_rows:
            if v < 1.0:
                print(f"  RUST-REGRESS {rid} overlap={v:.2f}")
        print(f"[3] rust(fts) vs HEAD-scan 模拟（boost 数据化行为保持）top-3 overlap = {rmean:.4f} "
              f"({rperfect}/{len(rust_rows)}) threshold>={PARITY_THRESHOLD}")
        dmean = sum(v for _, v in drift_rows) / max(len(drift_rows), 1)
        print(f"[3b] rust(fts) vs python(fts) demo top-3 overlap = {dmean:.4f}"
              f"（信息项：Rust 侧保留 boost 数据（kb_index.boost），Python demo 公式逐字锁定"
              f"不含 boost——即 audit A3-1 记录的 HEAD 既有漂移，本轮数据化非消除）")
        ok = ok and rmean >= PARITY_THRESHOLD

    # ---------- 4) 性能 P50 ----------
    def p50_ms(fn, n: int = 20) -> float:
        fn()  # warmup（含索引新鲜度检查）
        ts = []
        for _ in range(n):
            t0 = time.perf_counter()
            fn()
            ts.append((time.perf_counter() - t0) * 1000)
        ts.sort()
        return ts[len(ts) // 2]

    os.environ["CB_RAG"] = "fts"
    kb_q = p50_ms(lambda: search_knowledge("集装箱柜型常识", limit=5))
    e = get_expert("safety-brief")
    demo_q = p50_ms(lambda: demo_rag.search_kb(e.id, e.category, "安全交底", limit=6))
    print(f"[4] perf P50 of 20: knowledge_base={kb_q:.1f}ms demo_kb={demo_q:.1f}ms limit={P50_LIMIT_MS}ms")
    ok = ok and kb_q < P50_LIMIT_MS and demo_q < P50_LIMIT_MS

    # ---------- 5) 写钩子：编辑→检索可见 ----------
    tmp_rel = "company/__parity_write_hook_tmp.md"
    token = "PARITYTMPZZTOKEN"
    tmp_abs = ROOT / "demo" / "kb" / tmp_rel
    try:
        tmp_abs.parent.mkdir(parents=True, exist_ok=True)
        tmp_abs.write_text(f"# 写钩子探针\n\n{token} 唯一标记。\n", encoding="utf-8")
        assert reindex_kb_file(tmp_rel, kb="demo_kb"), "reindex_kb_file upsert 失败"
        os.environ["CB_RAG"] = "fts"
        e2 = get_expert("structure")
        hits = demo_rag.search_kb(e2.id, e2.category, token, limit=6)
        seen = any(h.path == tmp_rel for h in hits)
        tmp_abs.unlink(missing_ok=True)
        assert reindex_kb_file(tmp_rel, kb="demo_kb"), "reindex_kb_file delete 失败"
        hits2 = demo_rag.search_kb(e2.id, e2.category, token, limit=6)
        gone = not any(h.path == tmp_rel for h in hits2)
        print(f"[5] write hook: edit-visible={seen} deleted-gone={gone}")
        ok = ok and seen and gone
    finally:
        tmp_abs.unlink(missing_ok=True)
        reindex_kb_file(tmp_rel, kb="demo_kb")

    # ---------- 6) M4 grep 门禁：rag.rs 硬编码 boost 必须为消失态（data-plan M4④） ----------
    rag_rs = (ROOT / "workbench" / "src" / "rag.rs").read_text(encoding="utf-8")
    hardcodes = ["web-knowledge", "web-portals", "2026-08-14", "APPBCA-2026-12",
                 "order-37", "永远标", "+ 6.0", "+= 6.0", "+= 5.0", "+= 1.5", "+= 2.0", "-= 10.0"]
    left = [h for h in hardcodes if h in rag_rs]
    print(f"[6] rag.rs hardcode boost grep: {len(left)} 残留 {left if left else '(clean)'}")
    ok = ok and not left

    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
