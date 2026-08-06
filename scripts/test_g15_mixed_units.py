#!/usr/bin/env python3
"""Parse G15 mixed unit stress table via shipped table_mapper."""
from __future__ import annotations
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from packing_assistant.tools.table_mapper import parse_table_file

def main() -> int:
    p = ROOT / "test" / "generic_tables" / "G15_mixed_units_stress" / "materials.csv"
    assert p.exists(), p
    r = parse_table_file(p)
    assert r["ok"] and r["stats"]["n_rows"] >= 3
    by = {m["name"]: m for m in r["materials"]}
    # Length (cm)=45 -> 450 mm; width_m=0.3 -> 300 mm; H_mm=280
    a = by["Stress carton A"]
    assert abs(a["length_mm"] - 450) < 1e-3, a
    assert abs(a["width_mm"] - 300) < 1e-3, a
    assert abs(a["height_mm"] - 280) < 1e-3, a
    # Length (cm)=580 -> 5800 mm for long bar column is Length (cm) so 580cm=5800mm
    b = by["Stress long bar"]
    assert abs(b["length_mm"] - 5800) < 1e-3, b
    print("ALL_PASS g15_mixed_units")
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
