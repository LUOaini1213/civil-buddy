# contract/ — 意图契约唯一真源

`intents.v1.json` 是 Civil Buddy 意图/选岗词表的**唯一真源（single source of truth）**。
Python（`packing_assistant/understand.py`、`packing_assistant/runtime/expert_skills.py`）
与 Rust（`workbench/src/agent.rs`）双栈都在启动时从本文件加载词表，仓库里不允许再有
第二份手工维护的词表副本。

## 规则

1. **改词表先改这里**，两侧代码只是消费者。改完跑：
   - `python scripts/test_stack_parity.py`（结构 + 行为金句）
   - `python scripts/run_precommit_tests.py --quick`
   - `cargo test --release --test intents_golden`（Rust 侧行为）
2. **语义字段**：`phrase_write`/`write_nouns`/`ask`/`tender`/`packish`/`pack_action_zh`
   为"子串包含"触发词；`strong_match` 是有序 `(phrase, expert_id)` 数组——顺序即优先级
   （最长优先），两侧遍历取首个命中；匹配为大小写不敏感的子串包含。
3. **英文 pack 是已知机制差异**：Python 用词边界正则 `\bpack\b`，Rust 用非字母数字切词后
   判等（`word_equals_pack`）。语义等价，靠两侧源码中的 `parity:pack-action-en` 注释锚点
   + parity 测试成对校验，不做机器互译。
4. **金句兜底**：`test/eval/intents_golden.json` 固化了 (text → intent, skill) 行为基线，
   Python 侧由 parity 测试实跑断言，Rust 侧由 `workbench/tests/intents_golden.rs` 断言。
   改词表导致金句变化时，必须先确认新行为是想要的，再同步更新金句文件并说明原因。
5. **版本**：`version` 字段向后不兼容时递增（v1 期间 schema 变化需同步 README 与两侧加载器）。
