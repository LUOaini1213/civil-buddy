# fanout16x8 留档 · 2026-09-02

`python scripts/fanout16x8_online_cargo.py` 的一次完整运行产物：`rollup.md` / `rollup.json`（每 lane 通过数、wall 时间、fetch 状态）与 `fetch_meta.json`（联网抓取的公开货样元数据）。

结果：128/128 PASS，16 lane 全绿，wall 217.6 s。PASS 的判据是流水线跑通并返回 `can_fit` / 柜数字段（`scripts/fanout16x8_online_cargo.py` 的 `_pass_criteria`），**不是装得下**：逐次记录里 `can_fit=True` 71 次、`False` 57 次；终态 `done` 44、`need_revision` 84。`python scripts/render_eval_table.py` 从 `rollup.json` 直接算出这两组数，`--check README.md` 同时核对 PASS 数和 `can_fit=True` 数。

覆盖面：抓到的 4 个文件里只有 2 个 D-Wave 3D-BPP 样本能解析成货物（4 种和 7 种件；`data/external/sample_data_*.txt` 是同样两份的缓存副本），16 个 lane 是这 2 个样本的确定性变体；每个 lane 的 8 轮按轮次改输入（偶数轮每行数量 +1，第 3、6 轮长度 ×1.06、×1.12，奇数轮加 `prefer_single_row`），所以 8 轮里只有 4 种不同输入。128 次运行共 64 种不同输入，留档里只有 5 种（箱数、`can_fit`、柜数）结果。它是这 2 个公开样本上的稳定性检查，不是 128 个独立案例。`render_eval_table.py` 用评测时的同一组函数从 `fetch_meta.json` 和仓内缓存重算这些数，`--check` 一并核对。`fetch_meta.json` 里的 `path` 已于 2026-11-03 改成相对仓库根的路径（原为留档机器的绝对路径），其余字段未动。

运行期间 16 个并发 lane 写同一 sqlite trace 库触发外键约束，事件已按设计回退到 JSONL，不影响评测结果；该并发写问题记录在 issue #22。
