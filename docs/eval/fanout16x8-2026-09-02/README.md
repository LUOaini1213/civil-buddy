# fanout16x8 留档 · 2026-09-02

`python scripts/fanout16x8_online_cargo.py` 的一次完整运行产物：`rollup.md` / `rollup.json`（每 lane 通过数、wall 时间、fetch 状态）与 `fetch_meta.json`（联网抓取的公开货样元数据）。

结果：128/128 PASS，16 lane 全绿，wall 217.6 s。PASS 的判据是流水线跑通并返回 `can_fit` / 柜数字段（`scripts/fanout16x8_online_cargo.py` 的 `_pass_criteria`），**不是装得下**：逐次记录里 `can_fit=True` 71 次、`False` 57 次；终态 `done` 44、`need_revision` 84。`python scripts/render_eval_table.py` 从 `rollup.json` 直接算出这两组数，`--check README.md` 同时核对 PASS 数和 `can_fit=True` 数。运行期间 16 个并发 lane 写同一 sqlite trace 库触发外键约束，事件已按设计回退到 JSONL，不影响评测结果；该并发写问题记录在 issue #22。
