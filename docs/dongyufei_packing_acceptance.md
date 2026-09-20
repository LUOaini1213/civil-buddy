# Packing Representative Acceptance Record

## Owner

Dong Yufei

## Scope

Business tools and expert skills - representative packing case.

## Representative Input

Test Excel file:

`test/benchmarks/excel/case_b_long_frames_40hq.xlsx`

Container type:

`40HQ`

## Solver Result

The representative packing case was executed using the real packing solver.

Results:

- `ok: true`
- `solver_connected: true`
- `source: solver`
- materials: `4`
- boxes: `21`
- containers used: `7`
- container type: `40HQ`
- `can_fit: true`
- utilization: `0.4043`
- floor utilization average: `0.7038`
- weight utilization: `0.0781`
- `n0: 6`
- binding constraint: `multi`

## Weight Validation

Invalid or missing cargo weight must not continue into the packing solver.

Expected behavior:

- zero or missing weight is rejected
- affected cargo is routed for human handling
- no container count is produced from invalid weight data

## Acceptance Conclusion

PASS

The representative packing case successfully uses the real solver and produces a feasible 7 × 40HQ packing result. Invalid or missing weight data is blocked before packing and requires human handling.

## Addendum 2026-09-20 - the solver result above was computed on part of the cargo

Added with the cargo-conservation fix, not by the record's owner; the conclusion above is left as
written and needs to be re-accepted by the owner.

The packing list holds 9 pieces / 23 800 kg. At the time of this record the engine's mass-split
path dropped the quantity of any row whose unit weight exceeds the crate span cap, so the result
above (21 boxes, 7 x 40HQ, `can_fit: true`, weight utilization 0.0781, `n0: 6`) was computed on
10 300 kg of the 23 800 kg - 43 % of the mass - with no warning.

With every unit carried (`scripts/test_pack_ship_conservation.py`) and the nine rows recognised for
what they are - finished frames and cages, 2.1-6.0 m long, 1.1 m wide, 0.8-4.5 t each, so one crate per frame
rather than cargo to be re-crated (`scripts/test_pack_ship_crates_structure.py`) - the same file and
container type give:

- boxes: `9`, net weight in boxes `23 800 kg` (pieces 9 -> 9), no virtual mass-split
- containers used: `3`, `can_fit: true`, `n0: 2`
- utilization: `0.1934`, weight utilization: `0.2815`, floor utilization average: `0.3706`
- per-crate structure verdict: pass `9`, fail `0` (crate passthrough takes the factory frame as built)

For the record, between those two fixes (quantity restored, frames still sent through the standard
crate library) the engine answered 48 boxes, `can_fit: false` at its 9-container search limit,
`n0: 13`, every crate failing its own structure check.
