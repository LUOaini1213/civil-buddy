# 数据层审计（D-R1/3）——RAG 知识库 × SQL/持久层

> 审计基线：HEAD=6df7e1c，CI 绿。本文件只读审计，不改运行代码。
> 配套实施方案见 `docs/data/data-plan.md`（供 D-R2 统一持久层、D-R3 RAG 检索引擎照做）。

---

## 0. 现状总图（文字版）

```
两个知识库（服务两个应用，内容零重叠）
├─ demo/kb/（346 个 .md，1.7MB，17 顶层目录=16 大类+docs；company/ 公司层）
│    消费方：demo :8000（demo/rag.py）+ workbench :8765（workbench/src/rag.rs，Rust 重写）
│    结构：kb/<category>/<expert_id>/（私库）→ kb/<category>/_shared/（大类）→ kb/company/（公司）
└─ knowledge_base/（93 个文件，471KB，8 分区 01_rules…08_tender_delivery）
     消费方：packing_assistant（pack-ship 引擎，packing_assistant/tools/search_knowledge.py）

三套检索实现（同一"关键词打分"思想，三种 tokenizer、三种打分公式）
├─ demo/rag.py            正则整段 CJK 串为 token，bag 精确相等打分
├─ workbench/src/rag.rs   同核 + 多处硬编码 boost（已与 Python 漂移）
└─ packing_assistant/tools/search_knowledge.py  英文词+CJK bigram/trigram，分项加权

索引文件（生成≠消费，检索全都不用索引）
├─ knowledge_base/INDEX.yaml + .chunks_manifest.json ← scripts/gen_kb_index.py 生成
│    消费者仅 scripts/eval_knowledge_base_scorecard.py:52 与 scripts/test_constraints_frontmatter.py:41（都是校验，不是检索）
├─ knowledge_base/05_multi_agent/agent_kb_bindings.yaml ← packing_assistant/kb_bindings.py 加载（agent 窄接路由）
└─ demo/kb/ 没有任何索引文件，检索=查询时全盘 rglob 扫描

持久层（多处以 JSON 为库，0 个 .db 文件在用）
├─ output/sessions/*.json         session→run 索引（packing_assistant/session_store.py）
├─ output/runs/<id>/              session_state.json + checkpoint.json + trace.jsonl + 产物
├─ output/traces/stream.jsonl     全局事件流副本
├─ output/langgraph_checkpoints.db  代码里是默认路径，实际不存在（依赖未装，静默回退 MemorySaver）
├─ demo/out/<sid>/runs/<rid>/trace.json  workbench(Rust) 的 Run 对象落盘
├─ workbench/output/runs/<id>/    packing sidecar 以 workbench 为 cwd 时写出的同构目录（与根 output/ 双份）
├─ output/posts|phase0|kb/        eval 产物（JSON/MD）
└─ knowledge/packing_knowledge_base.json  数值知识库（JSON as DB）
```

---

## A. RAG 知识库审计

### A1. 库存点

**两库关系：不同应用、不同受众、零内容重叠。**

| | demo/kb/ | knowledge_base/ |
|---|---|---|
| 规模 | 346 个 .md / 1.7MB | 93 个文件 / 471KB |
| 组织 | 17 顶层目录（16 岗大类 + docs），每类下 `<expert_id>/` 私库 + `_shared/` + 顶层 `company/` | 8 分区：01_rules / 02_tools / 03_trajectories / 04_strategies / 05_multi_agent / 06_competition / 07_domain_knowledge / 08_tender_delivery |
| 服务 | 66 岗工作台（demo :8000 + workbench :8765） | pack-ship 引擎（packing_assistant / gateway :8199） |
| 层级路由 | expert → category(_shared) → company 三层（`demo/rag.py:24-29`） | agent_id → path_prefixes 窄接（`agent_kb_bindings.yaml`，`packing_assistant/kb_bindings.py:232/265/293`） |
| frontmatter | 无统一 frontmatter | 有（category/priority/tags/status，gen_kb_index.py 补全） |

**索引文件生成/消费链：**
- `knowledge_base/INDEX.yaml`、`knowledge_base/.chunks_manifest.json`：由 `scripts/gen_kb_index.py:247-252` 生成（含 `mysql_division` 规划分工声明，L182-186）。代码消费者只有两处且均为**校验**而非检索：`scripts/eval_knowledge_base_scorecard.py:52`（INDEX 覆盖率）、`scripts/test_constraints_frontmatter.py:41`。`.chunks_manifest.json` 无任何代码消费者。
- `knowledge_base/05_multi_agent/agent_kb_bindings.yaml`：`packing_assistant/kb_bindings.py:210 load_bindings` 加载（自带简易 YAML 解析器），`search_for_agent`（L293）用它把检索结果窄接到 `path_prefixes`；`default.fallback_path_prefixes` 兜底未列出的 agent。
- **demo/kb 没有索引**：`demo/rag.py:63-89` 与 `workbench/src/rag.rs:80-186` 每次查询都 `iter_text_files` 全盘读文件打分。

**金句集与测试判据：**
- `test/kb/rag_golden.json`：22 条金句（"重心 mid50 红线"→`01_rules/ctu_loading/safety_redlines.md` 等），口径"expect_paths 任一命中 top3 即算命中"。
- 消费者 1：`scripts/test_search_knowledge.py:31-55`——调 `search_knowledge(q, limit=3)`，断言 recall≥0.90（L54），另附坐标字段叙事守卫。
- 消费者 2：`scripts/eval_knowledge_base_scorecard.py:118-127`——同 22 条算"检索落地"维度分（`retr = 2.0 + reg_ok + 7.0*recall`，L172），目标各维 ≥9.5。两处口径一致，均只测 knowledge_base 栈。
- `scripts/test_kb_k4_depth.py` 是**另一套判据**：对 66 岗逐岗断言 `list_kb` 私库可见、`search_kb(expert.name)` 命中私库（L117-122）、兄弟岗私库不泄漏（L123-127）、faq≥5 问、README 字段表、outline 缺口标记（L85-105）。它驱动的是 **demo/rag.py**（L19 直接 import），即只测 demo/kb 栈。

### A2. 检索算法（三套实现对照）

| | demo/rag.py | workbench/src/rag.rs | packing_assistant/tools/search_knowledge.py |
|---|---|---|---|
| tokenizer | `re.findall(r"[\u4e00-\u9fff]{2,}\|[A-Za-z0-9_-]{2,}")`（L58-60）：**整段连续中文=1 个 token，无分词** | 同一正则（L68-71） | `re.findall(r"[a-z0-9_]+\|[\u4e00-\u9fff]+")` 再对 CJK 串追加 **bigram+trigram**（L73-100，dedupe 保序） |
| 词命中 | token∈doc.token_set 每 +2.0（L77） | 同 +2.0（L98） | token_set 命中 +1.0、title +2.5、body 子串 +0.8、path +1.2（L161-169） |
| 短语加分 | 原文含整句 query +8（L79-80） | 同（L100-102） | 无整句加分（靠 bigram） |
| 文件名 | 含 query token 每个 +3.0（L82） | 同 +3.0（L108-112） | path 命中 +1.2 |
| **Rust 独有硬编码** | 无 | `web-knowledge.md` +6、`web-portals.md` +5（L117-126）；正文含 `2026-08-14` +1.5、`APPBCA-2026-12` +2.0（L127-132）；新加坡类 query 对 order-37 -10（L133-149） | 无 |
| 元数据加权 | 无 | 无 | tags +1.5、tags_filter +2.0、×priority 权重（high=3.0）、category=rules ×1.15（L170-188） |
| 索引/缓存 | 无，查询时全盘扫 | 无，查询时全盘扫 | 进程内 `_CACHE`（L37/103-138），`status=deprecated` 排除 |
| 排序 | score desc → expert 层优先 → path（L90） | 同（L187-196） | score desc → path（L238） |
| 坐标守卫 | 无 | 无 | `_COORD_KEYS` 黑名单剥离（L22-24/263-267） |

- **中文分词现状**：全仓库无 jieba/任何分词器。demo/rag.py 栈整句中文是一个 token，命中依赖"文档里存在一模一样的连续串"，query 换个说法基本 miss，靠 +8 整句子串加分兜底；search_knowledge 的 bigram 显著缓解（金句 22/22 的基础）。
- **scorecard kb_search recall@3=22/22 的口径**：只对 knowledge_base 栈（search_knowledge）与 22 条金句，见上；**demo/kb 栈没有金句集**，只有 k4_depth 的"私库命中/兄弟隔离"结构断言。
- 三层路由保留情况：demo/kb 的 expert/category/company 三层在两栈都在（排序时 expert 层优先）；knowledge_base 侧三层被 agent 窄接（path_prefixes）替代。

### A3. 缺口

1. **两栈（实为三栈）算法不一致**：workbench/rag.rs 在共同核之外叠了 5 处硬编码 boost（日期、单号、文件名、新加坡惩罚），Python demo/rag.py 没有；同一 query 在 :8000 与 :8765 结果可以不同。这些是"数据写进了代码"，应数据化。
2. **中文检索质量**：无分词能力。search_knowledge 的 bigram 是目前唯一抗"说法变化"的手段，但也无同义/词序能力；无向量检索，同义改写 query 必然靠命中文档内整串。当前靠金句集 + 手工调文档兜住 22/22。
3. **更新链路**：改 .md 后**检索无需重建索引**（三套都是实时扫描）——这是现状的优点；但 `INDEX.yaml/.chunks_manifest.json` 需要手工跑 `python scripts/gen_kb_index.py --patch-fm`（knowledge_base/README.md:58），忘跑则 scorecard 元数据分掉档；`agent_kb_bindings.yaml` 手工维护，新增 agent 忘登记则落到 fallback 两文件。demo/kb 新增文件零登记（可写即检索）。
4. **检索范围不对称**：66 岗栈没有 golden 集、没有 deprecated/优先级概念、没有 frontmatter——knowledge_base 的工程化（frontmatter/绑定/守卫）没有反哺 demo/kb。
5. 性能余量：demo/kb 1.7MB 全盘扫描每次查询重读全部文件（`rag.rs:92 fs::read_to_string`），目前量级无感，但无缓存层。

---

## B. SQL/持久层审计

### B1. 全部持久点清单（谁写谁读）

| # | 路径 | 写者 | 读者 | 格式 |
|---|---|---|---|---|
| 1 | `output/sessions/<sid>.json` | `packing_assistant/session_store.py:125-163 save_session`（原子写，同 run 双写 sid+rid 两个索引） | `load_session`/`list_checkpoints`（L166-270）；gateway `/api/audit`、`/api/checkpoints` | JSON 索引：session_id/run_id/phase/status/resume… |
| 2 | `output/runs/<run_id>/session_state.json` + `checkpoint.json` | 同上（`_atomic_write_json` L56-69，os.replace 原子替换） | resume 流程（`graph_resume.py`）、`/api/confirm`、audit 端点 | 完整 state / 轻量 interrupt 元数据（schema `packing.checkpoint.v1`） |
| 3 | `output/runs/<run_id>/trace.jsonl` | `packing_assistant/trace_events.py:61-78 append_trace_event`（**append 无锁**），`also_global=True` 时同步追加 `output/traces/stream.jsonl` | `read_trace_jsonl`（L81-97）、`list_runs`（L100-120）、gateway `/api/runs/{id}/events`、`/api/runs/{id}/replay`、audit | JSONL 事件（schema `packing.stream.v1`，L26-58 规范化） |
| 4 | `output/runs/<run_id>/`（artifacts、index.json） | `packing_assistant/run_artifacts.py:37 save_run_artifacts` | `/api/runs/{id}`、审计面板 artifact 键 | JSON + 导出文件 |
| 5 | LangGraph checkpoint `output/langgraph_checkpoints.db` | `packing_assistant/lg_checkpoint.py:33-63`（`PACKING_LG_CHECKPOINT_PATH` 可覆盖；`sqlite3.connect(check_same_thread=False)`，**未设 WAL/busy_timeout**） | `get_thread_state`/`list_thread_ids`（L90-122） | SqliteSaver 表结构 |
| 6 | `demo/out/<sid>/runs/<rid>/trace.json` | **workbench(Rust)** `workbench/src/harness.rs:440-444 persist_trace`（单 JSON Run 对象，非事件流） | `/api/harness/audit/{session}`（`workbench/src/api.rs:74` → `harness.rs:814 audit_session`） | Run JSON（steps 数组，schema 与 #3 完全不同） |
| 7 | `workbench/output/runs/<id>/`（checkpoint.json、session_state.json） | packing sidecar：workbench 经 `packing_bridge.rs:286-293` 起 `run_packing_sidecar.py` **未改 cwd** → 相对路径 `output` 落到 `workbench/output/`（PACKING_OUTPUT_DIR 环境变量未设） | 无（孤儿数据，与根 `output/` 双份同构） | 同 #2 |
| 8 | `output/posts/*.json` | `scripts/eval_post_scorecard.py:38`（OUT_DIR） | 控制台摘要/人工 | JSON 评分 |
| 9 | `output/phase0/*.json` | `packing_assistant/phase0_benchmark.py` | README 记分卡命令 | baseline_latest.json 等 |
| 10 | `output/kb/SCORECARD.md` | `scripts/eval_knowledge_base_scorecard.py:226-228` | 人工/CI | MD |
| 11 | `demo/data/user_catalog.json` | demo `store.py:34 save_user` + workbench `store.rs:47-53 save_user`（两端各写同一文件） | 两端 `load_user` | JSON（岗位目录用户补丁） |
| 12 | `knowledge/packing_knowledge_base.json` | 人工维护 | `packing_assistant/knowledge.py:14-24 load_kb`（lru_cache） | 数值知识库 JSON |
| 13 | demo/kb、knowledge_base 的 .md | demo `kbio.py:174 write_text`（经 `packing_assistant/sandbox.guarded_write_text` 守卫）→ workbench `kbio.rs` 同构实现 | 三套检索 | Markdown |

**审计聚合端点现状（全靠扫文件）：**
- gateway `/api/audit`（`gateway/app.py:2314-2433`）：无 session → 扫 `output/sessions` 取 mtime 最新 24 个（L2326-2342）；有 session → `_audit_runs_for_session`（L2263-2311）**遍历 output/runs 全部目录（cap 200）**，对每个目录读 `checkpoint.json` 全文 + `trace.jsonl` 首行（8192 字节）比对 session 归属，再逐 run `read_trace_jsonl(limit=2000)` 全量解析事件（L2352-2353）。当前 613 个 run 目录，每次请求都是 O(N) 文件系统扫描 + JSON 解析。
- workbench `/api/harness/audit/{session}`（`harness.rs:814-975`）：扫 `demo/out/<session>/runs/*/trace.json`，逐个 `serde_json::from_str` 整个 Run，从 steps 合成审计节点。
- `session_store.list_checkpoints`（L214-270）同样 glob+逐文件读+逐文件 stat。

### B2. SQLite 现状

- **仓库当前没有任何 .db 文件**（`find . -name "*.db"` 零命中）。`lg_checkpoint.py` 是唯一的 SQLite 代码，但：
  - `requirements.txt` 只声明 `langgraph>=0.2.0`，**未装 `langgraph-checkpoint-sqlite`**（实测 `python -c "from langgraph.checkpoint.sqlite import SqliteSaver"` → `ModuleNotFoundError`）；
  - `lg_checkpoint.py:49-57` 捕获 ImportError 后**静默回退 MemorySaver**——即所谓"durable 断进程可 resume"的 LangGraph 通道实际是纯内存，进程重启即丢，磁盘上也永远不会出现 `langgraph_checkpoints.db`。durable 语义实际由 #1/#2 的手写 JSON checkpoint 承担。
- `knowledge_base/README.md:59-65` 与 gen_kb_index 生成的 `mysql_division` 已声明分工愿景（"MySQL / session_store 存 run_id、checkpoint、HITL、booking_id、评分、物料行"），但无任何实现。

### B3. 问题

1. **并发写风险**：
   - 单文件原子写（os.replace）只保证单文件一致；`save_session` 一次写 3~4 个文件（state、checkpoint、1~2 个 session 索引，session_store.py:136-155），中途崩溃会出现索引指向旧 state/半新半旧。
   - `trace_events.append_trace_event` 直接 `open("a")` 无文件锁；uvicorn 多 worker、workbench sidecar 与 gateway 并发写同一 run 时可交错。`also_global` 的 `stream.jsonl` 是全局单文件追加热点。
   - 若未来装上 langgraph-checkpoint-sqlite：当前连接未设 WAL/busy_timeout（lg_checkpoint.py:61），并发会直接 SQLITE_BUSY。
2. **查询能力缺失**：无法直接回答"某岗/某 session 的全部历史 run"——审计端点必须全盘扫 613 个目录读首行判断归属（gateway/app.py:2263-2311）；事件按 tool/type 聚合、跨 run 统计（错误率、耗时分布）都没有；事件里的 node/agent_id 有别名双写但无索引。
3. **清理/过期**：无任何保留策略（全仓 grep 无 prune/retention 实现）。output/runs 已 613 个、output/sessions 687 个、根目录还堆着数百张截图与 r7_* 调试残留；只增不减，audit 扫描成本随时间线性恶化。
4. **跨端（Python/Rust）口径差**：
   - 事件模型不同：Python=JSONL 事件流（trace.jsonl），Rust=单个 Run JSON（steps 数组），审计端点各自合成节点，规则相似但实现重复（gateway/app.py:2154-2260 vs harness.rs:814-975）。
   - 落盘根不同：入口是 gateway → `output/`；入口是 workbench sidecar → `workbench/output/`（同 schema 双份数据，互不可见）。
   - user_catalog.json 两端读写同一文件、无锁（demo/store.py 与 workbench/store.rs），后写覆盖先写。

---

## C. 联网对标结论（curl/WebSearch，2026-08）

### C1. SQLite FTS5 中文检索

- FTS5 内置 trigram tokenizer 可做**子串匹配**，官方文档明确要求查询**至少 3 个字符**（LIKE/GLOB 优化模式还要 10 字符）——中文 2 字词（"锁柜""塞实"这类金句核心词）**无法走 trigram 索引**，且 CJK 密集文本 trigram 索引膨胀明显。来源：SQLite FTS5 官方文档 http://www3.sqlite.org/fts5.html ；实践分析 https://zenn.dev/kanseilink/articles/kanseilink-fts5-trigram-cjk-20260507 ；内置 trigram 把 CJK 当普通字符的缺陷 https://github.com/streetwriters/sqlite-better-trigram
- 默认 unicode61 tokenizer 把每个 CJK 字符切成独立 token（无词边界），等价"字索引"，召回好精度差（https://dev.to/ahmet_gedik778845/building-a-search-system-with-sqlite-fts5-and-cjk-support-472f ）；FTS5 普通 token 索引**不能匹配词中间**，必须靠 trigram 或预分词（https://darksi.de/13.sqlite-fts5-structure/ ）。
- 社区成熟做法：**索引前自行把 CJK 预切 bigram、空格连接后入库，用 unicode61 检索**——2 字查询=1 个 bigram token 可精确命中，等效"jieba 效果"且零依赖零词典（多来源共识；亦见 https://stackoverflow.com/questions/75832600/ 的 MATCH+LIKE 混合方案）。
- **与 jieba 预分词对比**：jieba 需附带词典（MB 级）+ 新 Python 依赖，收益在"语义词边界"；对本库 437 篇、金句已 22/22 的体量，bigram 已达标且完全可复现。**结论：选 bigram 预分词，不引 jieba，不用 trigram。**

### C2. LangGraph SqliteSaver 与自建库共存

- `langgraph-checkpoint-sqlite` 是独立 PyPI 包（https://pypi.org/project/langgraph-checkpoint-sqlite/ ），实现 https://github.com/langchain-ai/langgraph/blob/main/libs/checkpoint-sqlite/langgraph/checkpoint/sqlite/__init__.py ；`setup()` 用 `CREATE TABLE IF NOT EXISTS` 迁移建自己的表（`checkpoint_migrations/checkpoints/checkpoint_blobs/checkpoint_writes`，与 Postgres saver 同布局，见 https://reference.langchain.com/python/langgraph.checkpoint.sqlite/SqliteSaver/setup ）。
- **结论：可以与自建业务表共存同一 .db 文件**——checkpointer 只碰自己命名空间的表，互不冲突；但它被官方定位"轻量同步场景"，单写者限制仍在。注意它**不自动设 WAL**，需要我们自己 `PRAGMA journal_mode=WAL`（连接由我方持有，lg_checkpoint.py:61 已是我方 `sqlite3.connect`）。

### C3. 单文件嵌入式库并发模式

- WAL=单写者+多读者并行，读写互不阻塞（官方论坛 https://sqlite.org/forum/info/b4e8b29ae409cd198652c6b7e70b53b702f269e67e1d2573d627feeba37bbf85 ；对比深读 https://tenthousandmeters.com/blog/sqlite-concurrent-writes-and-database-is-locked-errors/ ）。
- `busy_timeout` 必须**每个连接各自设置**，且要在并发连接建立前就设，否则仍会 SQLITE_BUSY（https://berthub.eu/articles/posts/a-brief-post-on-sqlite3-database-locked-despite-timeout/ ）；WAL+批量事务是社区标准组合（https://github.com/cashubtc/nutshell/issues/907 ）、常见参数 `busy_timeout=5000ms` + `wal_autocheckpoint=1000`（https://crackingwalnuts.com/database-internals/sqlite-locking-single-writer ）。
- **结论：Python 侧"进程内单写连接（模块级锁）+ 每连接 busy_timeout=5000 + WAL + synchronous=NORMAL"，Rust 侧只读连接；备份用 `VACUUM INTO`。**

---

## 附：审计中发现的高危小问题（供 D-R2 顺带修）

1. `lg_checkpoint.py` 静默降级 MemorySaver 无任何日志（L51-57）——"断进程可 resume"名不副实。
2. workbench sidecar 落盘根随 cwd 漂移（`workbench/output/` 孤儿数据），应显式设 `PACKING_OUTPUT_DIR`。
3. `/api/audit` 每 request 全扫 613 目录，随数据增长会从"慢"变"不可用"。
4. `user_catalog.json` 双端写无锁。
