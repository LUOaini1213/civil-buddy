# Façade demo pack (SYNTHETIC)

**Every file in this folder is a synthetic software fixture.** The tender, the project, the Main
Contractor, the panels, the weights, the site day and the people are invented for testing and for the
Civil Buddy demo. None of it comes from any contractor, and none of it may be shown as a real tender,
shipment or site record. The demo is built with a Singapore curtain-wall contractor as partner; that
partner supplied no document or number in this folder.

| File | What it is | Read by |
| --- | --- | --- |
| `facade_itt_doc.md` | Document-form ITT for a unitised curtain-wall subcontract: CR16 L4 workhead, 420 calendar days, 90-day validity, 10% performance bond, S$5,000/day LDs, 12-month DLP, 5% retention, PQM weightings, and a façade specification (PMU and VMU mock-ups, heat-soak test, 5% site water test, PE-endorsed calculations and shop drawings, warranties, A-frame delivery, insurance) | `解析招标 facade_itt_doc.md` (bid-parse), then bid-tech and bid-compliance from the session hand-off |
| `facade_panels.xlsx` | 24 unitised panels, 4200 × 1500 × 250 mm, 450 kg each (10,800 kg), east elevation L5–L8, English handling notes | pack-ship (`materials` sheet; a `README` sheet repeats this notice) |
| `facade_panels_zh.xlsx` | The same panels with Chinese handling notes (玻璃 易碎 禁翻 直立运输 禁叠) | pack-ship |
| `daily_report_input.txt` | One façade installation day as labelled lines: 6 panels on L5, 13 workers, a roof unit hoist, 2 gondolas (吊篮), 1 MEWP (曲臂车), a gasket defect, work above 3 m under a checked permit | pm-daily (项目日报) |
| `wah_briefing_input.txt` | Work-at-height toolbox briefing as labelled lines: panel landing and sealing L5–L8, fall height above 3 m, gondola and MEWP measures, stop conditions | safety-brief (安全交底, high risk) |
| `make_panels.py` | Regenerates the two workbooks: `python examples/facade-demo/make_panels.py` | — |

The two `.txt` inputs are in Chinese labelled lines because that is what the drafting posts read
today; an English sentence places almost nothing yet. In English: *daily report* — 24 Sep 2026, fine,
east elevation level 5, 6 panels installed (6 of 24), 13 workers, one roof unit hoist, two gondolas,
one MEWP, 12 panels delivered, two level-6 panels with an exposed stack-joint gasket (photos sent to the
factory), gondola and slab-edge work above 3 m with the work-at-height permit checked that day,
tomorrow level 6 east. *Briefing* — install and seal panels on the east elevation levels 5–8, fall height
above 3 m, façade gang with the WSH coordinator watching, hazards (fall from height, falling panel,
struck by load, gondola instability), measures (check the permit, harness on an independent lifeline,
separate gondola work and safety ropes checked daily, MEWP harness on the platform anchor, edge
barriers, exclusion zone below), stop in rain, high wind, hoist limit alarm or a gondola lock fault.

## Run it

```
python scripts/demo_facade.py
```

Offline, steps mode, no model key. It creates a new job folder (a temp folder unless `--job NEW_DIR`),
copies these files into `inputs/`, writes `CIVIL.md` with two stated facts (项目, 辖区 SG) and runs every
turn through `civil.run_task`, the function `civil exec` calls. It writes nothing outside that folder,
prints what each flow extracted and where a person must sign, and exits 1 if a flow errors.

The work-at-height briefing is a high-risk post: it writes nothing until a licensed person types
「我明白，将由持证人员签认」. The script never types it. That person reruns with
`--sign "我明白，将由持证人员签认"` (the same as `civil exec --confirm`, or the dialog in `civil desktop`).

By hand, in any empty folder: `civil init`, copy the files into an `inputs/` sub-folder (files in the
folder's top level are pasted into every draft), then `civil exec "解析招标 facade_itt_doc.md"`,
`civil exec "出一份技术标提纲"`, `civil exec "出一份废标检查表"`, `civil exec "按 facade_panels_zh.xlsx 装柜，柜型 40HQ"`,
`civil exec - < inputs/daily_report_input.txt`, `civil exec - < inputs/wah_briefing_input.txt`.
`scripts/test_facade_demo.py` checks the flows.

## What it does not show yet

The script computes these from the drafts instead of claiming them; on 2026-09-26 it printed:

- tender.parse.md shows 0 of the 8 façade specification clauses (PMU, VMU, heat soak, water test,
  PE endorsement, warranty, A-frame delivery, insurance), and no LDs or retention row;
- the plan was 6 × 40HQ, one panel per crate, and the same with Chinese notes, English notes and no
  notes at all (the script packs a copy with the notes removed as the control): the notes (glass,
  upright, no stacking) do not change it, and A-frame stillages are not modelled — that needs the
  contractor's real stillage size, tare and capacity;
- every crate's structure check reads 待详设: the engine does not invent a pass;
- the briefing body is generic (its cover still reads 待填); only the sign-off gate is façade-ready.

`facade_itt_doc.md` carries the same clauses as the ITT used in the 2026-09-26 repo study, so any score
measured on it is a development-set number, not a held-out figure.
