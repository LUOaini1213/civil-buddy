# workbench 质量整改记录（2026-08-25）

基线：`cargo check` 通过、`cargo test` 99/99、clippy 约 60 条警告。
终态：`cargo clippy --all-targets` 0 警告（无新增 `#[allow]`）、`cargo test` 126/126（原 99 项集成测试全部保留，新增 6 项单元测试）。

## bug 修复

- `src/agent.rs`：专家解释模式按 40 字节切 token 流，切断多字节中文字符会产生 U+FFFD 乱码；改为按字符切分（新增 `chunk_by_chars`），并加测试 `chunk_tests` 保证中文分块无损。
- `src/llm.rs`：SSE 流式解析按到达的网络分片逐段 split('\n')，跨分片被截断的 `data:` 行（以及被截断的多字节字符）会被静默丢弃/损坏，导致丢 token；改为字节级 carry 缓冲，只在完整行处解析。
- `src/websearch.rs`：`urlencoding_decode` 中 `&s[i+1..i+3]` 在 `%` 后紧跟多字节字符时切在非字符边界上会 panic；改为纯字节十六进制解码，并加测试 `percent_decode_survives_multibyte_neighbors`。
- `src/agent.rs`：`done_from_run` 的 JSON 里重复出现两次 `"intent"` 键，删去重复项（serde_json 取后者，输出值不变）。

## 健壮性

- `src/store.rs`：目录锁 `catalog_lock().lock().ok()` 在锁中毒（持锁线程 panic）后会静默拿不到守卫，写操作在无锁状态下竞争；新增 `catalog_guard()` 用 `into_inner()` 恢复守卫（数据本体在磁盘上，无内存状态可疑），4 处调用点全部替换。
- `src/store.rs`：`save_user` 改为「写临时文件 + rename」原子落盘，避免崩溃中途留下截断的 user_catalog.json（读取端会静默回退默认目录，丢失用户自建专家/大类）。
- `src/mcp.rs`：stdio 帧解析对 `Content-Length` 直接 `vec![0u8; len]`，恶意/损坏的头可触发任意大内存分配；新增 16MB 上限（超限报错）；空行处理由递归改为循环（避免大量空行栈溢出）；加 3 项帧解析测试。
- `src/attach.rs`：PDF zlib 解压与 docx/xlsx 的 zip 条目读取无上限（20MB 上传可解压成 GB 级，zip bomb）；统一加 64MB 解压上限（`MAX_INFLATED_BYTES`、`read_zip_text`）。
- `src/websearch.rs`：`web_open` 抓取网页正文 `resp.text()` 无上限，超大页面可耗尽内存；改为 `Read::take` 限制 8MB。
- `src/api.rs`：`/api/harness/expert`、`/api/eval/shadow`、`/api/eval/shadow-expert`、`/api/firm/bid` 及聊天流中的成套分支，原先在异步执行器上同步跑重型 harness（大量磁盘写 + CPU），会阻塞其他请求；统一经 `run_heavy` / `spawn_blocking` 移到阻塞线程池，失败时返回「后台任务失败：…」。
- `src/agent.rs`：`run_expert` 里同步调用 `harness::run_expert_steps` 同样移入 `spawn_blocking`。

## clippy 清理（全部 60 条归零）

- `src/packs.rs`：33 处 `format!` 嵌套 `format!`（SG/CN 辖区脚注拼接）统一收敛为新助手函数 `jur_notes(jur, sg, cn)`，输出字节不变。
- `src/packs.rs`：2 处循环内编译正则（比价单价剥离、日报部位剥离）改为 `std::sync::LazyLock` 静态正则。
- `src/packs.rs`：`mix_outline` 的 identical-if（两个分支都返回「砂浆」）合并为一个条件。
- `src/packs.rs`：`parse_resource_items` 的三元组复杂返回类型引入 `type ResourceRow = (String, String, String)` 别名；`tests/workbench.rs` 的用例元组同样引入局部 `WriterCase` 别名。
- `src/harness.rs`：9 参数的 `exec_step` 改为 `StepSpec` 参数结构体（name/expert/category/risk/confirm/tool），6 处调用点同步更新。
- `src/mcp.rs`：`loop + let-else` 改写为 `while let`。
- 其余机械项（17 处连续 `str::replace`、`contains` vs `iter().any`、可折叠 if、手写大小写比较等）由 `cargo clippy --fix` 完成，涉及 `src/extract.rs`、`src/packs.rs`、`tests/workbench.rs`、`tests/mcp_protocol.rs`。
- `src/websearch.rs`：`parse_ddg` / `strip_tags` / `html_to_text` 每次调用重编译正则，统一改为 `LazyLock` 静态正则（逐标签剥离语义保持不变）。

## 结构优化

- `src/agent.rs`：`run_expert_explain` 与 `talk_after_run` 中两段几乎完全相同的「LLM 只读工具循环」（约 60 行 × 2）抽出为共用 `read_only_tool_loop`，仅拒绝文案与阶段动词（解释/说明）参数化，对外事件与消息文本不变。
- `src/harness.rs`：3 处重复的 run_id 生成（`HHMMSS-xxxxxx` 带前缀）抽出为 `new_run_id(prefix)`。
- `src/api.rs`：5 处重复的「session_id 为空则生成 12 位随机 id」抽出为 `session_or_new`。

## 兼容性说明

- HTTP 路由、MCP 协议表面（tools/resources/prompts）、CLI 参数、所有对外中文文案与产出文件内容均未改变；原 99 项集成测试与 4 项 MCP 协议测试全部原样通过。
