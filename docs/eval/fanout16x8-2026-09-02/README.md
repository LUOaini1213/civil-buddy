# fanout16x8 留档 · 2026-09-02

`python scripts/fanout16x8_online_cargo.py` 的一次完整运行产物：`rollup.md` / `rollup.json`（每 lane 通过数、wall 时间、fetch 状态）与 `fetch_meta.json`（联网抓取的公开货样元数据）。

结果：128/128 PASS，16 lane 全绿，wall 217.6 s。运行期间 16 个并发 lane 写同一 sqlite trace 库触发外键约束，事件已按设计回退到 JSONL，不影响评测结果；该并发写问题记录在 issue #22。
