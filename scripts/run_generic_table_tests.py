#!/usr/bin/env python3
"""通用材料表回归：解析 G1–G6，可选 pipeline 装柜。

用法:
  python scripts/run_generic_table_tests.py
  python scripts/run_generic_table_tests.py --pack
  python scripts/run_generic_table_tests.py --only G1,G6 --pack
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env")
    except Exception:
        pass


def discover_cases(only: Optional[List[str]] = None) -> List[Path]:
    base = ROOT / "test" / "generic_tables"
    idx = base / "INDEX.json"
    paths: List[Path] = []
    if idx.exists():
        data = json.loads(idx.read_text(encoding="utf-8"))
        for c in data.get("cases") or []:
            p = base / c["path"]
            if p.is_dir():
                paths.append(p)
    else:
        paths = sorted([p for p in base.iterdir() if p.is_dir() and p.name.startswith("G")])
    if only:
        keys = {x.strip().upper() for x in only if x.strip()}
        paths = [p for p in paths if any(k in p.name.upper() for k in keys)]
    return paths


def pick_table(case_dir: Path) -> Path:
    for name in ("materials.csv", "materials.xlsx", "materials.json"):
        p = case_dir / name
        if p.exists():
            return p
    for p in sorted(case_dir.glob("*.csv")) + sorted(case_dir.glob("*.xlsx")):
        return p
    raise FileNotFoundError(f"no table in {case_dir}")


def expand_materials(mats: List[Dict[str, Any]], cap: int = 80) -> List[Dict[str, Any]]:
    """quantity>1 时展开为件（上限 cap，避免爆炸）。"""
    out: List[Dict[str, Any]] = []
    for m in mats:
        qty = max(1, int(m.get("quantity") or 1))
        # 大数量：保留 quantity，pipeline 通常按行处理；展开仅用于小票
        if qty > 12:
            out.append(dict(m))
            continue
        for i in range(qty):
            item = dict(m)
            item["quantity"] = 1
            item["total_weight_kg"] = float(m.get("weight_kg") or 0)
            item["id"] = f"{m.get('id')}-{i+1}" if qty > 1 else m.get("id")
            out.append(item)
            if len(out) >= cap:
                return out
    return out


def run_case(case_dir: Path, *, pack: bool) -> Dict[str, Any]:
    from packing_assistant.tools.table_mapper import parse_table_file

    table = pick_table(case_dir)
    exp_path = case_dir / "expected.json"
    expected = json.loads(exp_path.read_text(encoding="utf-8")) if exp_path.exists() else {}

    t0 = time.time()
    parsed = parse_table_file(table)
    mats = parsed["materials"]
    min_rows = int(expected.get("min_rows") or 1)
    parse_ok = parsed["ok"] and len(mats) >= min_rows

    # unit sanity: lengths should be mm-ish
    bad_units = 0
    for m in mats:
        L = float(m.get("length_mm") or 0)
        if 0 < L < 10:  # likely failed m→mm
            bad_units += 1
        if L > 20000:
            bad_units += 1

    result: Dict[str, Any] = {
        "id": case_dir.name,
        "table": str(table.relative_to(ROOT)),
        "parse_ok": parse_ok,
        "n_rows": len(mats),
        "stats": parsed.get("stats"),
        "bad_units": bad_units,
        "story": expected.get("story"),
        "ms_parse": int((time.time() - t0) * 1000),
    }

    if not parse_ok or not pack:
        result["pack_ok"] = None
        result["pass"] = parse_ok and bad_units == 0
        return result

    from packing_assistant.harness import public_response, run_agent_pipeline

    run_mats = expand_materials(mats)
    t1 = time.time()
    st = run_agent_pipeline(
        f"generic table {case_dir.name}",
        materials=run_mats,
        container_type="40HQ",
        enable_auto_confirm=True,
        session_id=f"generic-{case_dir.name}",
        packing_options={"crate_passthrough": True, "multi_start": True},
    )
    pub = public_response(st)
    plan = pub.get("container_plan") or pub.get("plan") or {}
    can_fit = plan.get("can_fit")
    if can_fit is None:
        can_fit = bool(pub.get("ship_ok") or (plan.get("containers_used") or plan.get("used")))
    used = plan.get("containers_used") or plan.get("used") or pub.get("containers_used")
    require = bool(expected.get("require_can_fit", True))
    pack_ok = bool(can_fit) if require else True
    result.update(
        {
            "pack_ok": pack_ok,
            "can_fit": can_fit,
            "containers_used": used,
            "ship_ok": pub.get("ship_ok"),
            "phase": pub.get("phase") or st.get("phase"),
            "ms_pack": int((time.time() - t1) * 1000),
            "pass": parse_ok and bad_units == 0 and pack_ok,
        }
    )
    return result


def main() -> int:
    _load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("--pack", action="store_true", help="run full agent pipeline")
    ap.add_argument("--only", type=str, default="", help="comma ids e.g. G1,G6")
    ap.add_argument("--out", type=str, default="")
    args = ap.parse_args()
    only = [x for x in args.only.split(",") if x.strip()] or None
    cases = discover_cases(only)
    if not cases:
        print("NO_CASES")
        return 2

    rows = []
    for c in cases:
        try:
            r = run_case(c, pack=args.pack)
        except Exception as e:
            r = {"id": c.name, "pass": False, "error": str(e)}
        rows.append(r)
        flag = "PASS" if r.get("pass") else "FAIL"
        print(
            flag,
            r.get("id"),
            "rows=",
            r.get("n_rows"),
            "parse=",
            r.get("parse_ok"),
            "pack=",
            r.get("pack_ok"),
            "used=",
            r.get("containers_used"),
            r.get("error") or "",
        )

    n = len(rows)
    n_pass = sum(1 for r in rows if r.get("pass"))
    n_parse = sum(1 for r in rows if r.get("parse_ok"))
    n_pack = sum(1 for r in rows if r.get("pack_ok") is True)
    summary = {
        "n": n,
        "n_pass": n_pass,
        "n_parse_ok": n_parse,
        "n_pack_ok": n_pack,
        "pass_rate": round(n_pass / n, 3) if n else 0,
        "pack": args.pack,
        "cases": rows,
    }
    out = Path(args.out) if args.out else ROOT / "output" / "autonomy" / "generic_table_latest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print("SUMMARY", json.dumps({k: summary[k] for k in ("n", "n_pass", "n_parse_ok", "n_pack_ok", "pass_rate")}))
    print("WROTE", out)
    # gate: all parse; if pack, at least 4 pack ok
    if n_parse < n:
        return 1
    if args.pack and n_pack < min(4, n):
        return 1
    return 0 if n_pass == n or (not args.pack and n_parse == n) else 1


if __name__ == "__main__":
    raise SystemExit(main())
