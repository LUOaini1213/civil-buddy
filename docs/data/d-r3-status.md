# D-R3 状态与下一步计划（2026-08-30 · 已验证）

> 数据层三轮：D-R1 审计（docs/data/audit.md）✅ → D-R2 SQLite 统一持久层（commit 14ec2bd）✅
> → D-R3 RAG 检索引擎（本提交，红线全绿）✅

## 已完成并验证（data(round3)）

- **索引构建** `scripts/build_kb_index.py`：双库扫描（demo/kb 346 + knowledge_base 90 = 436 docs /
  1637 chunks）→ kb_index/kb_chunks/kb_fts（FTS5 unicode61 + CJK 预切 bigram，弃 trigram——2 字
  中文查询可命中索引）。全量重建 1.5s；`--check` 新鲜度校验 PASS。
- **检索层** `packing_assistant/kb_search.py`：FTS5 粗召回（top50）+ 现行评分公式精排
  （search_knowledge.py:153-188 逐字保留）；旧入口（demo/rag.py、search_knowledge.py、demo/app.py
  kb 端点）切新层，`CB_RAG=json|fts` 开关、异常回退 json 打 WARNING。
- **boost 数据化** `contract/kb_boosts.v1.json`：rag.rs 原 5 处硬编码 boost 迁入契约，构建脚本
  同源写入 kb_index.boost；rag.rs 源码 grep 0 残留。
- **写钩子** demo/kbio.py 落盘即时 upsert/删除（实测：编辑后可见、删除后消失）。
- **Rust 对齐（M4）**：rusqlite 0.40.2（bundled，只读）；rag.rs 重写读 kb_fts + kb_index.boost；
  `civil-rag-probe` 对拍二进制；CB_RUST_RAG=scan 回退开关。

## 验收红线实测（2026-08-30，全部 PASS）

| 红线 | 结果 |
|---|---|
| parity 新旧实现 top-3 重合 | **1.0000**（48/48 完美重合，阈值 ≥0.95） |
| 金句 recall（新实现） | **48/48** |
| Rust(fts) vs 旧扫描行为保持 | **1.0000**（33/33） |
| scorecard kb_search | recall@3 **22/22**，综合 **8.85** 门禁全 PASS |
| test_kb_k4_depth | **66/66** |
| 检索性能 | P50 knowledge_base=**1.4ms** / demo_kb=**5.1ms**（限 50ms） |
| eval_post_scorecard | 5/5 岗全 PASS |
| cargo lib + intents_golden | 17 + 2 全过 |
| 断网专项 test_offline_ui | PASS（外域 0 请求、零 JS 异常，D-R3 代码全新进程） |

已知行为差异（非缺陷，audit A3-1 既有）：Rust(fts) vs Python(fts) demo 侧 top-3 重合 0.6364——
Rust 保留 boost 数据（kb_index.boost），Python demo 公式逐字锁定不含 boost；两侧行为各自与
HEAD 基线一致（parity [1]/[3] 均 1.0），此差异显式记录不冒充消除。

## 排障记录

test_offline_ui 首跑失败（:8765 审计下载超时）定位为**环境残留**：凌晨一次运行留下的
demo/app.py python 进程占住 8765，测试实际连的旧进程；清理残留后全新进程 PASS。
隔离实验（stash→HEAD 重建→同败）证明非 D-R3 回归。

## 下一步（D-R3 收口后）

- dual→sqlite 读切换评审（plan §1.3：切换前重跑 `--import` + audit 对拍）。
- `storage.prune --days 90` 真跑一次回收（先 dry-run 列表确认）。
- per-post 记分卡扩岗（5→L2 批次，逐岗补 required_bars）。
- 66 岗全景 UI 可浏览（U-R13 遗留）；Rust audit duration_ms 补齐。
- CI 观察：rusqlite bundled 首次在 Ubuntu runner 编译（crates.io 可达，预期可行）。
