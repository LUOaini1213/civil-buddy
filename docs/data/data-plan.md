# 数据层实施方案（给 D-R2 / D-R3）

> 依据 `docs/data/audit.md`（HEAD=6df7e1c 审计）。原则：离线可用硬约束（不引外部 API/CDN/云）、
> "tools compute numbers; the model only routes" 不变、JSON 降级为导出格式、回滚开关常在。
> 分工：**M1–M2 = D-R2（统一 SQLite 持久层）**；**M3–M4 = D-R3（RAG 检索引擎）**。

---

## 1. 统一 SQLite 库（D-R2）

### 1.1 库文件与连接纪律

- 路径：`data/civilbuddy.db`（repo 根已有 `data/` 目录；WAL 伴生 `-wal/-shm`）。
  环境变量 `CB_DB_PATH` 可覆盖（测试用 tmp 路径）。
- 连接纪律（每个连接初始化时执行，依据 audit C3）：
  ```sql
  PRAGMA journal_mode=WAL;          -- 单写多读，读写互不阻塞
  PRAGMA synchronous=NORMAL;
  PRAGMA busy_timeout=5000;         -- 每连接各设，防 SQLITE_BUSY
  PRAGMA foreign_keys=ON;
  ```
- Python 侧：**进程内单写**——`storage.py` 模块级 `threading.Lock` + 一个写连接
  （`check_same_thread=False`）+ 惰性 thread-local 读连接；FastAPI/uvicorn 单进程内串行写。
  workbench(Rust) 侧**只读**（见 1.5），消除跨进程写竞争。
- 备份：`storage.backup()` 用 `VACUUM INTO 'data/backup/civilbuddy-YYYYMMDD.db'`；
  gateway 启动时若距上次备份 >24h 自动执行一次；保留最近 7 份。
- LangGraph checkpointer **共存同一文件**（audit C2 结论）：安装 `langgraph-checkpoint-sqlite`
  （离线：预下载 wheel 进 `vendor/` 或内网 pip 源），`PACKING_LG_CHECKPOINT_PATH=data/civilbuddy.db`；
  其 `setup()` 用 `CREATE TABLE IF NOT EXISTS` 自建 `checkpoints/checkpoint_blobs/checkpoint_writes/checkpoint_migrations`，
  与业务表不冲突；我方持有的连接上补 `PRAGMA journal_mode=WAL`。

### 1.2 Schema 草案（字段级）

```sql
CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);

-- 会话与 HITL（吸收 output/sessions/*.json + checkpoint.json）
CREATE TABLE sessions(
  session_id     TEXT PRIMARY KEY,
  run_id         TEXT,                       -- 最新 run
  phase          TEXT,                       -- running|await_user_confirm|team_b_running|done|cancelled
  status         TEXT,                       -- running|interrupted|resumed|done|cancelled
  user_action    TEXT,                       -- confirm|cancel|NULL（审计"人工决策"来源）
  container_type TEXT, n_boxes INTEGER, n_materials INTEGER,
  packing_plan_id TEXT,
  saved_at       TEXT NOT NULL,              -- ISO8601 UTC
  state_json     TEXT NOT NULL               -- 完整 state 快照（= 现 session_state.json 原文，导出可复原）
);
CREATE INDEX idx_sessions_saved  ON sessions(saved_at DESC);
CREATE INDEX idx_sessions_status ON sessions(status);

-- 运行（吸收 output/runs/<id>/ 元信息；app/source 字段解决跨端口径）
CREATE TABLE runs(
  run_id       TEXT PRIMARY KEY,
  session_id   TEXT,
  app          TEXT NOT NULL DEFAULT 'packing',  -- packing | workbench | demo
  source       TEXT,                              -- gateway | workbench-bridge | cli | phase0 | eval
  expert_id    TEXT, category TEXT,               -- 66 岗语境（workbench 侧），支撑"某岗全部历史 run"
  started_at   TEXT, ended_at TEXT,
  phase        TEXT, status TEXT,
  container_type TEXT, n_boxes INTEGER,
  checkpoint_json TEXT,                           -- checkpoint.json 原文
  run_dir      TEXT,                              -- artifact 目录（大文件仍留磁盘，库里存引用）
  FOREIGN KEY(session_id) REFERENCES sessions(session_id)
);
CREATE INDEX idx_runs_session ON runs(session_id, started_at);
CREATE INDEX idx_runs_expert  ON runs(expert_id, started_at);
CREATE INDEX idx_runs_started ON runs(started_at DESC);

-- 事件（吸收 trace.jsonl / demo/out trace.json 的公共字段）
CREATE TABLE events(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT NOT NULL,
  seq INTEGER, ts TEXT, t_ms INTEGER,
  type TEXT NOT NULL,                             -- run_start|agent_start|tool_start|tool_end|hitl|replan|debate|done...
  node TEXT, agent_id TEXT, parent_node TEXT,     -- 别名归一（trace_events.py:36-42 的双写收敛为列）
  tool TEXT, status TEXT, duration_ms INTEGER,
  payload_json TEXT                               -- 规范化后事件其余字段全量（回放不丢信息）
);
CREATE INDEX idx_events_run  ON events(run_id, id);
CREATE INDEX idx_events_type ON events(type);
CREATE INDEX idx_events_tool ON events(tool);
CREATE INDEX idx_events_node ON events(node);

-- 审计决策（从 events/hitl + user_action 提取的冗余加速表，/api/audit 置顶区直查）
CREATE TABLE audit_decisions(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id TEXT, run_id TEXT,
  action TEXT NOT NULL, operator TEXT,            -- confirm|cancel；本地用户|引擎(自动确认)
  ts TEXT, detail_json TEXT
);
CREATE INDEX idx_decisions_session ON audit_decisions(session_id, ts);

-- 评分（吸收 output/phase0、output/posts、output/kb/SCORECARD）
CREATE TABLE scores(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  kind TEXT NOT NULL,                             -- phase0|post|kb_scorecard|gold_e2e|harness
  case_id TEXT, run_id TEXT, session_id TEXT,
  passed INTEGER, score REAL, detail_json TEXT, created_at TEXT
);
CREATE INDEX idx_scores_kind ON scores(kind, created_at DESC);

-- KB 索引（D-R3 用，schema 先随 M1 建好）
CREATE TABLE kb_index(
  path TEXT NOT NULL, kb TEXT NOT NULL,           -- 相对路径；kb ∈ demo_kb|knowledge_base
  title TEXT, display TEXT,
  layer TEXT,                                     -- expert|category|company|NULL
  category TEXT, expert_id TEXT,
  priority TEXT DEFAULT 'medium', tags_json TEXT, status TEXT DEFAULT 'active',
  mtime TEXT, size INTEGER, hash TEXT,            -- 增量构建判据
  boost REAL DEFAULT 0,                           -- 数据化硬编码加分（audit A3-1）
  PRIMARY KEY(kb, path)
);
CREATE TABLE kb_chunks(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  kb TEXT NOT NULL, path TEXT NOT NULL,
  heading TEXT, seq INTEGER, body TEXT,
  body_bigrams TEXT,                              -- CJK 切 bigram+英文词，空格连接（见 §2.1）
  FOREIGN KEY(kb, path) REFERENCES kb_index(kb, path) ON DELETE CASCADE
);
CREATE INDEX idx_chunks_path ON kb_chunks(kb, path);
-- FTS5（unicode61 + 预切 bigram；不用 trigram，见 §2.1 对比结论）
CREATE VIRTUAL TABLE kb_fts USING fts5(
  body_bigrams, kb UNINDEXED, path UNINDEXED, heading UNINDEXED, tokenize='unicode61'
);
```

### 1.3 迁移策略（首次启动导入，不做常驻双写长跑）

- **导入器** `scripts/migrate_json_to_sqlite.py`（+ `storage.import_json()`）：
  扫 `output/sessions/*.json` → sessions；扫 `output/runs/*`（checkpoint.json→runs，trace.jsonl→events，
  index.json/artifacts 清单→runs.run_dir）；`workbench/output/runs/*` 同样导入并打 `source='workbench-bridge'`；
  `output/phase0|posts/*.json` → scores。幂等：按 run_id/session_id UPSERT，重复导入零副作用。
  demo/out/<sid>/runs/* 属 workbench(Rust) Run 对象：解析 steps 合成 events（type 映射表写死在导入器）。
- **过渡模式** `CB_STORAGE=json|dual|sqlite`（默认 `dual`）：
  - `json`：完全走现行 JSON 代码路径（回滚开关，语义与 6df7e1c 完全一致）；
  - `dual`：写路径双写（JSON 先、SQLite 后；SQLite 失败仅告警不阻断业务，对齐 lg_checkpoint.py:85-87 的容错哲学），读路径仍 JSON；
  - `sqlite`：读路径切 SQLite，JSON 降级为导出格式。
  双写期预计 1~2 周（M2 验收通过即切 `sqlite` 并在 README 记录），**不做无期限双写**。
- JSON 保留为导出格式：`storage.export_json(out_dir)` 可从 DB 全量回导 output/ 布局
  （保证"DB 是权威、JSON 是快照"，`/api/runs/{id}/replay` 等消费方无需改协议）。

### 1.4 Python 侧 `packing_assistant/storage.py` 接口草案

```python
class Storage:  # 模块级单例 get_storage()；CB_STORAGE 控制 json/dual/sqlite 分派
    # 生命周期
    def __init__(self, db_path: Path | None = None) -> None: ...   # 建表跑 schema_migrations
    def close(self) -> None; def backup(self, dst: Path | None = None) -> Path  # VACUUM INTO
    # sessions（对齐 session_store.py 现有函数签名，调用方零改动）
    def save_session(self, session_id: str, state: dict) -> dict: ...
    def load_session(self, session_id: str) -> dict | None: ...
    def load_checkpoint_meta(self, session_id: str) -> dict | None: ...
    def list_checkpoints(self, *, limit: int = 50, pending_hitl_only: bool = False) -> list[dict]: ...
    def mark_checkpoint(self, session_id: str, *, status: str, extra: dict | None = None) -> dict | None: ...
    def delete_checkpoint(self, session_id: str) -> bool: ...
    # runs/events（对齐 trace_events.py）
    def append_trace_event(self, run_id: str, event: dict, *, also_global: bool = True) -> dict: ...
    def read_trace_jsonl(self, run_id: str, *, limit: int = 5000) -> list[dict]: ...
    def list_runs(self, *, limit: int = 50, session_id: str | None = None,
                  expert_id: str | None = None, tool: str | None = None) -> list[dict]: ...  # 新查询能力
    def audit_runs_for_session(self, sid: str, cap: int = 200) -> list[dict]: ...  # 替代 /api/audit 全盘扫描
    # scores / 维护
    def add_score(self, kind: str, case_id: str, **kw) -> None: ...
    def import_json(self, out_dir: Path | None = None) -> dict: ...   # 幂等迁移导入
    def export_json(self, out_dir: Path) -> None: ...                 # JSON 导出格式
    def prune(self, *, keep_days: int = 90, keep_min_per_session: int = 3) -> int: ...  # 清理
```

`session_store.py`/`trace_events.py` 改为薄壳：内部转调 storage（函数签名与返回结构不变，
`gateway/app.py`、`harness.py:137/297` 等调用方不动）。`/api/audit` 改为
`SELECT runs WHERE session_id=?` + `SELECT events WHERE run_id IN (...)` +
`SELECT audit_decisions WHERE session_id=?`，删除目录扫描。

### 1.5 Rust 侧共享同一库

- `workbench/Cargo.toml` **当前无 rusqlite**（audit B1），M4 新增
  `rusqlite = { version = "0.3x", features = ["bundled"] }`（bundled 内嵌 C 源，需 cc.exe——
  MSVC 环境已具备；**离线风险**：新增 crate 首次需拉取一次，要求 D-R3 先验证 CI 能否
  `cargo vendor` 或提前提交 vendor 目录；若 CI 拉不了 crate，Rust 侧 M4 降级为
  "维持扫描式检索 + 打分公式对齐 Python"，SQLite 只在 Python 侧落地，并在本文档记录取舍）。
- Rust 用途收敛为**只读**：`(a)` `rag.rs` 查 kb_index/kb_fts；`(b)` `harness.rs audit_session`
  可选改读 events 表（app='workbench'）。写路径（trace.json 落盘）M4 期间保留，
  由导入器增量吸收，**不在本轮做 Rust 写 SQLite**。
- 打包基线：release exe 随仓库分发（`dist/`），db 文件不进 exe；`Paths` 增加 `db_path`。

### 1.6 回滚开关与验收

- 回滚：`CB_STORAGE=json` 一键回到 6df7e1c 等价行为（json 代码路径保留至 M4 结束后才允许删）。
- 清理策略（M2 附带）：`storage.prune(keep_days=90)` + gateway 启动钩子；
  对 613 runs/687 sessions 首跑预期回收可观磁盘并让 audit 查询恒定 <50ms。

---

## 2. RAG 检索引擎（D-R3）

### 2.1 选型结论：FTS5 trigram vs 纯 Python n-gram

| 方案 | 中文 2 字查询 | 索引体积 | 依赖 | 结论 |
|---|---|---|---|---|
| FTS5 `tokenize='trigram'` | **不命中索引**（trigram 需 ≥3 字符，官方 http://www.sqlite.org/fts5.html ；实践 https://zenn.dev/kanseilink/articles/kanseilink-fts5-trigram-cjk-20260507 ） | CJK 密集文本膨胀明显 | 无 | **弃**（金句集大量 2 字核心词：塞实/锁柜/红马…） |
| unicode61 + **索引前 CJK 预切 bigram**（空格连接入库，查询同切法） | 2 字查询=1 个 bigram token，精确命中；≥3 字查询多 bigram AND，召回/精度可控 | 约 2× 原文 | 无（纯正则切分，`search_knowledge.py:73-100` 已有同款 tokenizer 可直接复用） | **选此** |
| jieba 预分词 | 词级命中 | 1× | jieba + MB 级词典，新增离线依赖 | 不做（收益不抵依赖，bigram 已 22/22） |
| 纯 Python 内存评分（现状 search_knowledge） | 已达标 | 0（现扫） | 无 | 保留公式；数据入 SQLite 后 Rust 可共享、audit/其他消费方可 SQL 查询 |

**落地形态**：索引构建时 CJK 切 bigram（可选带 trigram 以保 ≥4 字查询精度）+ 英文原词，
空格连接写入 `kb_chunks.body_bigrams` 并同步进 `kb_fts`；查询时同切法后
`SELECT path FROM kb_fts WHERE kb_fts MATCH ?` 取候选集（top 50），再用**现行公式**精排（§2.3）。
即"FTS5 粗召回 + 现行公式精排"，两层都在同一 db 文件里，离线零新依赖。

### 2.2 索引构建与更新触发

- 构建脚本 `scripts/build_kb_index.py`：
  扫 `demo/kb/**/*.md|txt`（kb='demo_kb'，layer/category/expert_id 由路径解析）+
  `knowledge_base/**/*.md`（kb='knowledge_base'，frontmatter 进 priority/tags/status）；
  按 `(mtime,size,sha1)` 增量：未变跳过、变了重写、消失删除（`kb_chunks` 级联）。
  输出统计到 `scores(kind='kb_index')` 或 stdout。
- 触发（三条，缺一不可）：
  1. gateway / workbench 启动时校验 stale（对比 `kb_index` 与磁盘 mtime，不一致自动重建，毫秒级增量）；
  2. 写钩子：`demo/kbio.py write_text/create_file/delete_file` 与 `workbench/src/kbio.rs` 同名函数
     落盘成功后即时 upsert/删除对应行（编辑岗知识即刻可检索）；
  3. 手工 CLI：`python scripts/build_kb_index.py [--full]`（CI 里跑 `--check` 模式断言索引新鲜）。
- `INDEX.yaml`/`.chunks_manifest.json` 保留为 gen_kb_index.py 产物（元数据校验用），
  检索不再依赖文件系统；`agent_kb_bindings.yaml` 继续作为**路由配置**（人维护），
  `path_prefixes` 在查询层照旧过滤。

### 2.3 评分公式与三层路由（金句不退步为硬约束）

- 精排公式**原样保留** `search_knowledge.py:153-188`：
  `score = Σ(1.0·token_set命中 + 2.5·title + 0.8·body子串 + 1.2·path + 1.5·tags)
  × priority权重(high=3.0/highest=3.5/medium=1.5/low=0.5) × (category=rules ? 1.15 : 1)`
  + tags_filter +2.0/项；坐标字段黑名单照旧。
- demo/kb 三层路由保留：`kb_index.layer`（expert/category/company）入库；
  查询时 scope 过滤 = 现行 `kb_layers()` 的三个根，排序 tie-break 仍 expert 层优先（`rag.rs:187-196`）。
- workbench/rag.rs 的 5 处硬编码 boost（audit A3-1：web-knowledge +6 / web-portals +5 /
  "2026-08-14" +1.5 / "APPBCA-2026-12" +2.0 / 新加坡 order-37 -10）**数据化**：
  写入 `kb_index.boost` 字段（构建脚本按文件名/内容规则计算），查询层统一
  `score += boost`。Python/Rust 从此同一份打分输入，两栈漂移消除。
- demo/rag.py 与 search_knowledge.py 收敛为**一个共享实现**：
  `packing_assistant/kbsearch.py`（或 storage 内视图函数），demo 栈与 packing 栈调同一函数，
  只是 scope 不同；workbench/rag.rs 走 SQL+同一公式（Rust 重写打分，字段对齐）。

### 2.4 Rust 侧共享

- `rag.rs` 重写为：构造查询 bigram 串 → `kb_fts MATCH` → 拉 `kb_index` 行 → 按 §2.3 打分
  （Rust 侧实现同一公式，单测用固定 fixture 对拍 Python 输出 top-3）。
- `kb_layers` 从路径推导改为 `SELECT ... WHERE kb='demo_kb' AND layer=? AND category=? [AND expert_id=?]`。
- 回退：`CB_RUST_RAG=scan` 环境变量保留旧的全盘扫描路径（对齐 1.6 回滚哲学）。

### 2.5 验收线（不退步红线）

1. `scripts/test_search_knowledge.py`：Recall@3 **≥ 22/22**（现状，阈值 0.90 是下限，实际必须满 分不回退）；
2. `scripts/test_kb_k4_depth.py`：66/66（私库命中 + 兄弟隔离 + 结构断言）；
3. `scripts/eval_knowledge_base_scorecard.py`：综合与各维 ≥9.5（检索落地维不降）；
4. 新增 `scripts/test_kbsearch_parity.py`：对金句 22 条 + 20 条随机 query，Python 新实现 vs
   Rust 实现的 top-3 重合率 ≥95%（允许浮点 tie-break 差异）；
5. 更新链路：改一个 md → 不重启服务 → 新内容 1s 内可检索（写钩子生效）。

---

## 3. 里程碑（D-R2 / D-R3 直接照做）

| 阶段 | 负责 | 内容 | 验收标准 |
|---|---|---|---|
| **M1 库与迁移** | D-R2 | `data/civilbuddy.db` schema（§1.2 全表）+ `storage.py`（§1.4）+ `scripts/migrate_json_to_sqlite.py` + `CB_STORAGE` 开关（默认 json） | ① 导入现存 613 runs/687 sessions 全量成功，二次导入零变更（幂等）；② 抽样 20 个 session：`load_session`/`list_checkpoints` JSON 模式 vs DB 模式结果 deep-equal；③ `CB_STORAGE=json` 下全测试套件与 6df7e1c 一致；④ 离线环境安装 langgraph-checkpoint-sqlite 成功，`langgraph_checkpoints` 表出现在同库，`get_checkpointer()` 不再回退 MemorySaver（加日志断言） |
| **M2 读切换+审计加速** | D-R2 | session_store/trace_events 双写（dual）；`/api/audit`、`/api/runs`、`/api/checkpoints` 在 sqlite 模式改 SQL 直查；`storage.prune` + 启动备份 | ① audit 端点响应与 JSON 模式逐字段 diff 一致（同 session 对比脚本）；② "某 session 全部 run"、"某岗全部 run"（workbench 数据）查询 <50ms（613 runs 体量）；③ prune 跑通（dry-run 列表 + 真跑回收）；④ CI 绿 + `test_no_external_urls.py` 不受影响（无新外链） |
| **M3 KB 索引与 Python 检索统一** | D-R3 | `build_kb_index.py`（双库扫描→kb_index/kb_chunks/kb_fts）+ 启动 stale 检测 + kbio 写钩子 + `search_knowledge`/`demo.rag` 切"FTS 粗召回+现行公式精排"（公式逐字保留） | ① §2.5 验收 1–3、5 全绿；② 索引构建全量 <5s、增量 <200ms；③ 写钩子单测（编辑→检索可见） |
| **M4 Rust 共享与收口** | D-R3（rusqlite 可行性前置验证；不可行则降级并记录） | rusqlite(bundled, 只读) + `rag.rs` 切 kb_fts+boost 数据化 + `parity` 测试 + 删除 Python 侧 json 旧路径（`CB_STORAGE=json` 移除前的最后清理评审） | ① §2.5-4 parity ≥95%；② workbench 检索结果与 :8000 对拍（同一 query top3 重合）；③ 离线 release 构建成功（`cargo build --release` 无网络）；④ 硬编码 boost 从源码消失（grep 断言进 CI）；⑤ 全测试套件 + scorecard 金线 8 项不回退 |

依赖顺序：M1 → M2（D-R2 线）；M3 依赖 M1 的 kb 表；M4 依赖 M3。
M3 可与 M2 并行（不同模块，唯一交点是 `data/civilbuddy.db` schema 版本号）。

---

## 4. 明确"不做"清单（内网与体量不需要）

| 不做 | 理由 |
|---|---|
| 向量库/嵌入模型（FAISS、Chroma、sqlite-vec、本地 embedding） | 语料 437 篇 ≈2.2MB，bigram 词法检索金句已 22/22；离线 embedding 模型数十~数百 MB + CPU 推理延迟，收益/成本倒挂；内网不可调云端 embedding |
| 云服务/外部 API（OpenAI、Pinecone、CDN） | 内网硬约束；`scripts/test_no_external_urls.py` 已把零外链进 CI，引云服务直接违反项目原则 |
| 重排模型（bge-reranker / cross-encoder） | CPU 推理慢 + 模型分发难；437 篇库上 priority/title/path 手工特征已够；精排公式保留即可 |
| jieba 等分词器 | +词典 MB 级 + 新依赖；bigram 无状态、可复现、已达标（§2.1） |
| FTS5 trigram tokenizer | 2 字中文查询不命中索引（官方 ≥3 字符限制）、索引膨胀（§2.1） |
| MySQL / Postgres | 单机单文件 SQLite 足够且零运维；README 的"MySQL 分工"是概念分层图，不是部署要求；SQLite 兼容同一套 SQL 查询能力 |
| Rust 侧写 SQLite（本轮） | 写路径集中在 Python（gateway/sidecar），Rust 只读即可消除跨语言写竞争；降低 bundled 编译与离线 CI 风险 |
| 常驻双写长期化 | dual 仅是 1~2 周过渡；长期双写=双真相源，必然漂移 |

---

## 5. 风险与对策

1. **rusqlite 离线构建失败**（M4 前置验证）：预提交 `cargo vendor/` 或降级方案（Rust 维持扫描检索，公式对齐），见 §1.5。
2. **dual 双写期 JSON 与 DB 不一致**：dual 模式下读仍走 JSON，DB 仅累积；切换 sqlite 前跑 `import_json` 重导一次 + 抽样对拍（M2 验收②）。
3. **trace.jsonl 事件无 seq 的乱序**：导入器按文件行序生成 seq；`events.id` 自增保证查询稳定。
4. **workbench/output 孤儿数据**（audit B1-#7）：导入器吸收历史，M2 起 sidecar 显式设置 `PACKING_OUTPUT_DIR` 指向统一输出根，根因修复随 D-R2 落地。
5. **金句回归**：任何 M3/M4 改动先跑 §2.5-1/2 两条红线，失败即回滚（环境变量级回退）。
