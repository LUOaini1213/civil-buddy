# demo/ 质量整改记录（2026-08-25）

入口与全部 HTTP 路由保持不变（`uvicorn app:app --host 127.0.0.1 --port 8765`，demo/ 目录下启动）。
被 scripts/ 测试引用的公开 API（`agent.execute_tool` / `agent.build_expert_prompt` / `agent._plain_system` /
`agent.tools_for_expert` / `rag.search_kb` / `kbio.resolve_rel` / `catalog_seed.EXPERTS` / `mcp_stdio` 等）签名未变。

## bug 修复

- **app.py `/api/config`**：原实现先写 `os.environ["CIVIL_SANDBOX"] / ["CIVIL_APPROVAL"]` 再校验，
  非法值虽然返回 400 但环境变量已被污染，后续所有 `load_config()` 都带着坏值。
  改为先用 `_strip_mode` 归一校验（保留 `ro` / `write` 等别名），非法直接 400，合法才写入归一后的值。
- **app.py `/api/chat`**：新增输入校验，空白消息直接返回 400「消息不能为空。」，不再空跑一次流式会话。
- **rag.py `search_kb`**：删除永远不生效的 `idx = text.find(q[0])` 死分支（`q[0]` 未命中时得 -1，
  但该值从未被使用），摘要截取逻辑简化且行为不变。
- **kbio.py `delete_file`**：补上后缀白名单校验（只允许删 .md / .txt），与写入侧口径一致。

## 健壮性

- **llm.py**：出站 LLM HTTP 调用统一 `httpx.Timeout(120, connect=10)`（连接超时单列，网络不通时不再挂 2 分钟）；
  `httpx.TimeoutException` / `httpx.HTTPError` 统一转成带中文提示的 `LLMError`（「模型服务请求超时…」「无法连接模型服务…」），
  由 `/api/chat` 的 SSE error 事件呈现，不再落成裸 traceback；模型返回缺 `choices` 等格式异常也转 `LLMError`；
  base_url 未配置时给出中文报错。无 Key 时行为不变（启动即可用，`/api/chat` 返回 400 中文提示）。
- **store.py `load_user`**：`data/user_catalog.json` 损坏（JSON 解析失败 / 顶层不是对象 / 读取 IO 错误）时
  回退到出厂目录，不再让所有目录类接口 500。已用烟雾测试验证坏文件下 `/api/catalog` 仍 200。
- **config.py**：`packing_assistant.llm` 导入失败时回退为直接读环境变量的同口径实现，demo 可脱离仓库其余部分启动；
  `CIVIL_MAX_AGENT_STEPS` 非法值（非数字 / ≤0）不再让模块导入直接崩，回退默认 8。
- **kbio.py**：`file_stat` 读文件遇 OSError（列目录与读取之间被删）按空文件统计，不炸 `/api/catalog`、`/api/studio/tree`；
  `ensure_kb_root` 拷贝硬规则失败不再阻断启动。
- **rag.py `_read`**：知识库文件读失败按空文件处理，检索不中断（编码脏字节原有 `errors="ignore"` 保留）。
- **demo/tests/conftest.py（新增）**：仅测试环境把系统临时目录加入 `CIVIL_SANDBOX_ROOTS`，
  修复 `tests/test_kb_prompt.py::test_bid_tools_exclusive_and_shared_parse` 在本环境的既有失败
  （沙箱默认不允许写 pytest tmp_path，与本次改动无关，已用 git HEAD 版本代码复现同样的 PermissionError）。
  生产沙箱白名单不变。

## 结构优化

- **agent.py**：删除与 kbio 重复的 `_safe_write`（改为 `from kbio import safe_write as _safe_write`，
  行为一致：优先走 `packing_assistant.sandbox.guarded_write_text`，沙箱拒绝时抛 PermissionError，其余失败回退普通 UTF-8 写盘）；
  删除与 config.py 重复的 `sys.path` 注入；删除 `_exec` 里无意义的 `nonlocal`。
- **kbio.py**：新增 `ensure_category_kb(category)`，`ensure_expert_kb` 复用之；`write_text` 的沙箱写盘逻辑提取为公共 `safe_write`。
- **store.py / seed_missing_kb.py**：建大类不再用「先建 `_placeholder` 专家再 rmtree」的迂回写法，直接 `ensure_category_kb`；
  `KB_ROOT` / `remove_expert_kb` / `shutil` 等改为顶部导入，删除多处函数内重复导入；
  两处硬编码 `512 * 1024` 改用 `kbio.MAX_FILE_BYTES`。
- **mcp_surface.py**：删除与 config.py 重复的 `_REPO` sys.path 注入，改为显式 `import config` 说明依赖。
- **rag.py**：删除只转发一层的 `_iter_md`，直接用 `kbio.iter_text_files`。

## 清理

- **kbio.py `format_bytes`**：去掉 `f" {…} KB".strip()` 的多余前导空格再 strip 写法，输出不变。
- **seed_missing_kb.py**：`shutil` 循环内导入等清理（随占位目录写法一并删除）。

## kb/ 内容

- 全部 346 个 .md 逐一校验 UTF-8 编码，无坏文件；知识内容一字未改。

## 验证

- `python -m compileall -q demo`：通过。
- `cd demo && python -c "import app"`：通过（无 Key 也可导入、可启动）。
- `cd demo && python -m pytest tests/ -q`：19 passed（整改前 1 failed，见上）。
- `python -m pytest scripts/ -q`（仓库根）：48 passed / 0 failed（基线 46–47 passed / 1–2 failed，失败项均非 demo）。
- `uvicorn app:app --host 127.0.0.1 --port 8765` 实启：`/` 200、`/api/health` 200。
- 端点烟雾测试：空消息 400、坏 user_catalog.json 下目录接口 200、studio 增删改查与越权路径拦截、
  `/api/file` 越权 403、MCP resources/tools/prompts 200，全部通过。
