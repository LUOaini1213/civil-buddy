#!/usr/bin/env python3
"""文件路径上的数量格：读不出件数的行留下并转人工，不装一个猜出来的件数。

修复前（fix/pack-ship-cargo-conservation 17192e7 实测）：table_mapper 在任何闸门看到之前就把
数量格改写了——`qty = max(1, int(_to_float(cell) or 1))`，<= 0 的行直接跳过。下面这张表

    编号,品名,数量,单重(kg),长(mm),宽(mm),高(mm)
    A,件A,2.7,50,1200,400,300
    B,件B,0,50,1200,400,300
    C,件C,-3,50,1200,400,300
    D,件D,abc,50,1200,400,300

load_materials 得到 [("A", 2), ("D", 1)]：2.7 装成 2 件，"abc" 装成 1 件，-3 的行整行消失，
run_plan 照出方案、ok=True。#49 的 rows_invalid_quantity 只看得到调用方直接给的行，
解析过的行到它手里已经是 2 和 1。

逐类的决定（证据见 test_fixtures_read_the_same_as_before）：
  明写 0          → 仍跳过并计 n_skip_zero_qty。照字面读就是 0 件，不是猜；三个夹具目录里
                    唯一的显式 0 是 G8 的全零占位行。
  负数/小数/非数值 → 行有尺寸或重量时留下，meta.quantity_invalid + quantity_raw，quantity 留 0；
                    既无尺寸又无重量的仍按全零占位行丢弃。
  没写            → 1 件，不变。

用法：python scripts/test_table_quantity_cells.py            （CI，约 2 s）
      python scripts/test_table_quantity_cells.py --numbers  （另外打印夹具前后对比的计数）
"""
from __future__ import annotations

import math
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PACKING_SKIP_SKJOLBER", "1")

from packing_assistant.tools import table_mapper  # noqa: E402
from packing_assistant.tools.pack_ship_mcp import ingest_tool  # noqa: E402
from packing_assistant.tools.pack_ship_solve import (  # noqa: E402
    draft_booking,
    draft_vgm,
    load_materials,
    plan_report_md,
    rows_invalid_quantity,
    run_plan,
)
from packing_assistant.tools.table_mapper import _quantity_cell, parse_table_rows  # noqa: E402

HEADER = "编号,品名,数量,单重(kg),长(mm),宽(mm),高(mm)"
REPRO = [HEADER, "A,件A,2.7,50,1200,400,300", "B,件B,0,50,1200,400,300",
         "C,件C,-3,50,1200,400,300", "D,件D,abc,50,1200,400,300"]
FIXTURE_DIRS = ("test/generic_tables", "test/excel/synthetic", "test/benchmarks/excel")


def _csv(lines: List[str]) -> str:
    fd, path = tempfile.mkstemp(suffix=".csv", prefix="qty_")
    with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
        f.write("\n".join(lines) + "\n")
    return path


def _parsed(lines: List[str]) -> Dict[str, Any]:
    path = _csv(lines)
    try:
        return load_materials(None, path)
    finally:
        Path(path).unlink(missing_ok=True)


def test_quantity_cell_reader() -> None:
    ok = {3: 3, 3.0: 3, "3": 3, " 3 ": 3, "3.0": 3, "8件": 8, "10 pcs": 10, "12PCS": 12, "6托": 6,
          "1,200": 1200, "1e3": 1000,
          # 修复前这三格因为正则留下字母 e/E、float() 失败，都被装成 1 件
          "3 EA": 3, "2 sets": 2, "4 pieces": 4}
    for cell, pieces in ok.items():
        assert _quantity_cell(cell) == ("ok", pieces), (cell, _quantity_cell(cell))
    for cell in (None, "", "   ", "　"):
        assert _quantity_cell(cell) == ("missing", 1), cell
    for cell in (0, 0.0, "0", "0.0", "0件", "-0"):
        assert _quantity_cell(cell) == ("zero", 0), (cell, _quantity_cell(cell))
    # 修复前的读法写在右边：没有一个是表上的意思
    invalid = (2.7, "2.7", -3, "-3", "abc", True, False, math.nan, math.inf, "nan", "-", "—",
               "1,5",      # 欧式小数，曾读成 15 件
               "10/12",    # 曾读成 1012 件
               "2-3", "约5", "10件/箱", "2026-01-05 00:00:00")
    for cell in invalid:
        assert _quantity_cell(cell) == ("invalid", 0), (cell, _quantity_cell(cell))


def test_repro_rows_are_kept_and_marked() -> None:
    loaded = _parsed(REPRO)
    mats = loaded["materials"]
    assert [(m["id"], m["quantity"]) for m in mats] == [("A", 0), ("C", 0), ("D", 0)], mats  # 修复前 [("A", 2), ("D", 1)]
    assert [m["meta"].get("quantity_raw") for m in mats] == ["2.7", "-3", "abc"], mats
    assert all(m["meta"]["quantity_invalid"] is True for m in mats)
    stats = loaded["stats"]
    assert stats["n_skip_zero_qty"] == 1 and stats["n_invalid_quantity"] == 3, stats  # 修复前 2 / 无此项
    # 件数不知道时不编总重：单重照抄，总重留 0（= 没写），也不因此被当成缺重量
    assert all(m["weight_kg"] == 50.0 and m["total_weight_kg"] == 0.0 for m in mats), mats
    assert not any(m["meta"]["weight_missing"] for m in mats)
    assert all(m["meta"]["confidence"] < 0.95 for m in mats)


def test_every_entry_point_asks_instead_of_packing() -> None:
    path = _csv(REPRO)
    try:
        for name, out in (("run_plan", run_plan(file_path=path)),          # 修复前 ok=True，装 2 + 1 件
                          ("draft_vgm", draft_vgm(file_path=path)),
                          ("draft_booking", draft_booking(file_path=path))):
            assert out["ok"] is False and out["error"] == "invalid_quantity", (name, out)
            assert out["source"] == "needs_human" and out["solver_connected"] is False, (name, out)
            asked = [(r["id"], r["raw"]) for r in out["needs_human"] if r["reason"] == "invalid_quantity"]
            assert asked == [("A", "2.7"), ("C", "-3"), ("D", "abc")], (name, asked)
            assert "can_fit" not in out and "containers_used" not in out, (name, out)
        report = plan_report_md(run_plan(file_path=path), "repro.csv")
        assert "「abc」" in report and "「-3」" in report and "「2.7」" in report, report

        ingest = ingest_tool(file_path=path)
        assert ingest["ok"] is False and ingest["n_rows"] == 3, ingest
        assert [r["id"] for r in ingest["needs_human"]] == ["A", "C", "D"], ingest
        assert ingest["stats"]["n_invalid_quantity"] == 3 and "数量" in ingest["next"], ingest
    finally:
        Path(path).unlink(missing_ok=True)


def test_corrected_file_plans_the_written_counts() -> None:
    fixed = [HEADER, "A,件A,3,50,1200,400,300", "B,件B,0,50,1200,400,300",
             "C,件C,3 EA,50,1200,400,300", "D,件D,,50,1200,400,300"]
    path = _csv(fixed)
    try:
        assert ingest_tool(file_path=path)["ok"] is True
        out = run_plan(file_path=path)
        assert out["ok"] is True, out
        # 3 + 3 + 1（没写 = 1 件）；B 明写 0 不发。修复前 "3 EA" 读成 1 件，这里是 5 件 / 250 kg
        assert out["conservation"]["pieces_in"] == 7 and out["conservation"]["kg_in"] == 350.0, out["conservation"]
        assert out["parse"]["stats"]["n_skip_zero_qty"] == 1 and out["parse"]["stats"]["n_invalid_quantity"] == 0
    finally:
        Path(path).unlink(missing_ok=True)


def test_noise_rows_are_still_dropped() -> None:
    # 读不出件数、又既无尺寸也无重量：全零占位行，是噪声不是货
    loaded = _parsed([HEADER, "X,待定,abc,0,0,0,0", "Y,待定2,-1,,,,", "Z,真货,2,50,1200,400,300"])
    assert [(m["id"], m["quantity"]) for m in loaded["materials"]] == [("Z", 2)], loaded["materials"]
    clean = loaded["stats"]["clean"]
    assert clean["n_skip_zero_placeholder"] == 2 and clean["n_invalid_quantity"] == 0, clean

    g8 = load_materials(None, str(ROOT / "test/generic_tables/G8_noise_rows/materials.csv"))
    assert [(m["name"], m["quantity"]) for m in g8["materials"]] == [("有效箱A", 8), ("有效箱B", 4), ("有效小件", 20)]
    assert g8["stats"]["n_invalid_quantity"] == 0 and rows_invalid_quantity(g8["materials"]) == []


def test_total_weight_only_row_does_not_invent_a_unit_weight() -> None:
    rows = [{"品名": "梁", "数量": "2.5", "总重(kg)": 900, "长(mm)": 6000, "宽(mm)": 300, "高(mm)": 300}]
    (m,) = parse_table_rows(rows)["materials"]
    # 修复前：数量读成 2，单重 = 900 / 2 = 450
    assert m["quantity"] == 0 and m["total_weight_kg"] == 900.0 and m["weight_kg"] == 0.0, m
    assert m["meta"]["quantity_invalid"] is True and m["meta"]["weight_missing"] is False, m


def test_xlsx_native_cells() -> None:
    import openpyxl

    fd, path = tempfile.mkstemp(suffix=".xlsx", prefix="qty_")
    os.close(fd)
    try:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["编号", "品名", "数量", "单重(kg)", "长(mm)", "宽(mm)", "高(mm)"])
        for row in (("A", "件A", 2.7), ("B", "件B", True), ("C", "件C", -3), ("D", "件D", 4.0), ("E", "件E", None)):
            ws.append([*row, 50, 1200, 400, 300])
        wb.save(path)
        wb.close()
        mats = load_materials(None, path)["materials"]
        # 修复前：A=2、B=1（True 当 1.0）、C 消失、D=4、E=1
        assert [(m["id"], m["quantity"]) for m in mats] == [("A", 0), ("B", 0), ("C", 0), ("D", 4), ("E", 1)], mats
        assert [r["id"] for r in rows_invalid_quantity(mats)] == ["A", "B", "C"]
        assert run_plan(file_path=path)["error"] == "invalid_quantity"
    finally:
        Path(path).unlink(missing_ok=True)


def test_mark_survives_without_meta_and_meta_alone_is_enough() -> None:
    (parsed,) = _parsed([HEADER, "A,件A,2.7,50,1200,400,300"])["materials"]
    bare = {k: v for k, v in parsed.items() if k != "meta"}  # 下游把 meta 丢了：quantity=0 自己就过不了闸门
    assert [r["reason"] for r in rows_invalid_quantity([bare])] == ["invalid_quantity"]
    # 反过来，数值看着正常、只有标记：仍然拦
    marked = dict(bare, quantity=2, meta={"quantity_invalid": True, "quantity_raw": "2.7"})
    (asked,) = rows_invalid_quantity([marked])
    assert asked["raw"] == "2.7" and "「2.7」" in asked["ask"], asked
    assert run_plan(materials=[marked])["error"] == "invalid_quantity"
    # 调用方直接给的行没有标记：#49 的行为与措辞不变
    (plain,) = rows_invalid_quantity([dict(bare, quantity=-3)])
    assert "raw" not in plain and "「" not in plain["ask"], plain


# ---- 夹具：新旧读法逐格对比 -------------------------------------------------------------------

def _reading_before_the_fix(cell: Any) -> Tuple[str, Optional[int]]:
    """table_mapper 17192e7 第 596–601 行的原样读法，留在这里作对照。"""
    qty_f = table_mapper._to_float(cell)
    if qty_f is not None and qty_f <= 0:
        return "skip", None
    return "keep", max(1, int(qty_f or 1))


def _reading_now(cell: Any) -> Tuple[str, Optional[int]]:
    state, pieces = _quantity_cell(cell)
    if state == "zero":
        return "skip", None
    return ("keep", pieces) if state in ("ok", "missing") else ("ask", None)


def _fixture_quantity_cells():
    """三个夹具目录里每一个有品名的原始行的数量格（走解析器自己的读表与列映射）。"""
    real = table_mapper.rows_to_ir
    seen: Dict[str, Any] = {}

    def spy(rows, *, headers=None, **kwargs):
        seen["rows"], seen["headers"] = list(rows), headers
        return real(rows, headers=headers, **kwargs)

    table_mapper.rows_to_ir = spy
    try:
        for folder in FIXTURE_DIRS:
            for path in sorted((ROOT / folder).rglob("*")):
                if path.suffix.lower() not in (".csv", ".xlsx") or not path.is_file():
                    continue
                seen.clear()
                parsed = table_mapper.parse_table_file(path)
                headers = [str(h) for h in (seen["headers"] or [])]
                by_std = {std: raw for raw, std in table_mapper.build_column_map(headers).items()}
                cells = [r.get(by_std.get("quantity")) for r in seen["rows"]
                         if str(r.get(by_std.get("name")) or "").strip()]
                yield folder, path, parsed, cells
    finally:
        table_mapper.rows_to_ir = real


def test_fixtures_read_the_same_as_before(show: bool = False) -> None:
    """干净的表一格都不该变。2026-09-20 实测：33 个文件、116 个有品名的原始行、解析出 114 行
    （差的 2 行是 G8 的注释行与占位行），新旧读法 0 格不同，0 行被标记；唯一的显式 0
    （G8「无效空行应跳过」，尺寸重量全 0）新旧都是跳过。"""
    totals: Dict[str, Dict[str, int]] = {}
    for folder, path, parsed, cells in _fixture_quantity_cells():
        t = totals.setdefault(folder, {"files": 0, "cells": 0, "rows": 0, "differ": 0, "marked": 0, "zero": 0})
        t["files"] += 1
        t["cells"] += len(cells)
        t["rows"] += len(parsed["materials"])
        t["zero"] += sum(1 for c in cells if _quantity_cell(c)[0] == "zero")
        differ = [c for c in cells if _reading_before_the_fix(c) != _reading_now(c)]
        assert not differ, (path, differ)
        marked = [m for m in parsed["materials"] if m["meta"].get("quantity_invalid")]
        assert not marked and parsed["stats"]["n_invalid_quantity"] == 0, (path, marked)
        assert all(type(m["quantity"]) is int and m["quantity"] >= 1 for m in parsed["materials"]), path
        t["differ"] += len(differ)
        t["marked"] += len(marked)
    assert set(totals) == set(FIXTURE_DIRS) and all(t["files"] and t["rows"] for t in totals.values()), totals
    if show:
        for folder in FIXTURE_DIRS:
            print(f"  {folder}: {totals[folder]}")
        print("  total:", {k: sum(t[k] for t in totals.values()) for k in next(iter(totals.values()))})


def main() -> int:
    show = "--numbers" in sys.argv[1:]
    tests = [
        test_quantity_cell_reader,
        test_repro_rows_are_kept_and_marked,
        test_every_entry_point_asks_instead_of_packing,
        test_corrected_file_plans_the_written_counts,
        test_noise_rows_are_still_dropped,
        test_total_weight_only_row_does_not_invent_a_unit_weight,
        test_xlsx_native_cells,
        test_mark_survives_without_meta_and_meta_alone_is_enough,
    ]
    for test in tests:
        test()
        print(f"[OK] {test.__name__}")
    test_fixtures_read_the_same_as_before(show)
    print("[OK] test_fixtures_read_the_same_as_before")
    print("TABLE QUANTITY CELLS PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
