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