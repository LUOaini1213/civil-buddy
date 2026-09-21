# Unified workbench implementation

The three adjacent design documents are the agreed target, not evidence of completed features. This file records implementation and acceptance separately. Original local working trees remain untouched.

## Sources

- main `b3ccc72ef8e2a6894d683b8a9af4ef365d036dfb`
- CAD/engineering PR 58 `3e93025ee3794f96028ea8ce2067184a6af28a25`
- frontend PR 56 `ca145930487e8446609b148c503bdf2759b5f180`
- knowledge PR 57 `79bcb5833f7b87e7b04dac7e5b52aa6ae461165f` pending integration
- local planning/routing changes are under concurrent development; recheck before final integration.

## Required acceptance

- [ ] Existing 66 skills, CAD and engineering pages remain available in one launched product.
- [ ] Rust owns workspace scope, session exclusivity, task tree, shared budget, event persistence, cancellation and restart recovery.
- [ ] DeepSeek Flash completes actual tool loops; full requests fit context and provider usage is recorded. Scripted tests are separate from opt-in live acceptance.
- [ ] Jev off/shadow/assist adapter validates Choice/Score/Noul against host questions and cannot authorize writes or invent engineering facts.
- [ ] Child agents have isolated context, bounded tools, shared budgets and cancellation. Results distinguish missing inputs from success.
- [ ] PDF, XLSX and DOCX can be inspected and edited as validated copies with immutable source hashes, old-value checks and precise locators.
- [ ] End-to-end PDF requirements → spreadsheet mapping → Word revision yields reopened artifacts, diff and validation evidence.
- [ ] CAD selection → section tool → source-linked engineering result works through the Rust host.
- [ ] Retrieval scopes by workspace/source version; citations resolve to source and locator. Missing OCR/formula recalculation/rendering is explicit.
- [ ] Sandbox reports policy and actual OS controls separately; worker credentials are scrubbed and cancellation kills and reaps processes.
- [ ] Voice produces an editable draft, retains consent requirements for cloud/browser fallback, and cancels without late insertion.
- [ ] UI shows context occupancy, actual task phases, task history/recovery and downloadable outputs.
- [ ] `npm run check`, relevant full suite, Rust tests, browser acceptance and documented live-model acceptance pass.

Do not describe this checklist as completed until the corresponding evidence is recorded. A runnable document demo alone does not satisfy the full goal.
