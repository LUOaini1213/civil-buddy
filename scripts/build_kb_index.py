#!/usr/bin/env python3
"""KB 索引构建 CLI（data-plan M3 · D-R3）。

扫 demo/kb/（66 岗三层，346 篇 md）+ knowledge_base/（8 分区，90 篇 md）→
data/civilbuddy.db 的 kb_index/kb_chunks/kb_fts（FTS5 unicode61 + CJK bigram 预切）。

用法：
  python scripts/build_kb_index.py              # 增量（mtime+size 判据，毫秒级）
  python scripts/build_kb_index.py --rebuild    # 全量重建（清空重灌）
  python scripts/build_kb_index.py --check      # 断言索引新鲜 + 行数量级（CI 用）

构建完成即断言行数量级（437 篇量级全部入索引），并同步生成
contract/kb_boosts.v1.json（rag.rs 5 处硬编码 boost 的数据化契约）。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packing_assistant.kb_search import (  # noqa: E402
    index_is_stale,
    rebuild_index,
    write_boost_contract,
)

MIN_ROWS = {"demo_kb": 340, "knowledge_base": 88}  # 437 篇量级（346+90）下限
MIN_TOTAL = 430


def main() -> int:
    ap = argparse.ArgumentParser(description="KB SQLite FTS5 索引构建")
    ap.add_argument("--rebuild", action="store_true", help="全量重建（默认增量）")
    ap.add_argument("--check", action="store_true", help="只校验新鲜度与行数，不重建")
    args = ap.parse_args()

    if args.check:
        if index_is_stale():
            print("FAIL: kb_index 与磁盘不一致（stale）—运行 python scripts/build_kb_index.py")
            return 1
        from packing_assistant.storage import get_storage

        st = get_storage()
        rows = {kb: st.count("kb_index") if kb == "demo_kb" else 0 for kb in ()}
        demo_n = st.read_conn().execute(
            "SELECT COUNT(*) FROM kb_index WHERE kb='demo_kb'").fetchone()[0]
        kb_n = st.read_conn().execute(
            "SELECT COUNT(*) FROM kb_index WHERE kb='knowledge_base'").fetchone()[0]
        ok = demo_n >= MIN_ROWS["demo_kb"] and kb_n >= MIN_ROWS["knowledge_base"]
        print(f"kb_index rows: demo_kb={demo_n} knowledge_base={kb_n} "
              f"(min {MIN_ROWS['demo_kb']}/{MIN_ROWS['knowledge_base']})")
        if not ok:
            print("FAIL: kb_index 行数低于量级下限")
            return 1
        print("PASS: kb_index 新鲜")
        return 0

    stats = rebuild_index(full=bool(args.rebuild))
    contract = write_boost_contract()
    stats["boost_contract"] = str(contract.relative_to(ROOT))

    demo = stats.get("demo_kb") or {}
    kb = stats.get("knowledge_base") or {}
    ok = (demo.get("total", 0) >= MIN_ROWS["demo_kb"]
          and kb.get("total", 0) >= MIN_ROWS["knowledge_base"]
          and stats.get("kb_index_rows", 0) >= MIN_TOTAL)
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    if not ok:
        print("FAIL: 索引行数低于 437 篇量级断言")
        return 1
    # 无损性断言：chunk body 拼回必须等于原文（Rust 短语加分依赖）
    bad = _verify_lossless()
    if bad:
        print(f"FAIL: {len(bad)} 篇 chunk 拼接不等于原文，如 {bad[0]}")
        return 1
    print(f"PASS: build_kb_index 全部入索引且 chunk 无损（{stats['kb_index_rows']} docs / "
          f"{stats['kb_chunks_rows']} chunks / {stats['kb_fts_rows']} fts rows）")
    return 0


def _verify_lossless(limit: int = 5) -> list[str]:
    from packing_assistant.kb_search import DEMO_KB_ROOT, KB_ROOT
    from packing_assistant.storage import get_storage

    st = get_storage()
    bad: list[str] = []
    for kb, root in (("demo_kb", DEMO_KB_ROOT), ("knowledge_base", KB_ROOT)):
        rows = st.read_conn().execute(
            "SELECT path, body FROM kb_chunks WHERE kb=? ORDER BY path, seq", (kb,)
        ).fetchall()
        joined: dict[str, list[str]] = {}
        for path, body in rows:
            joined.setdefault(path, []).append(body or "")
        for path, bodies in joined.items():
            raw = (root / path).read_text(encoding="utf-8", errors="ignore")
            if "".join(bodies) != raw and len(bad) < limit:
                bad.append(f"{kb}/{path}")
    return bad


if __name__ == "__main__":
    raise SystemExit(main())
