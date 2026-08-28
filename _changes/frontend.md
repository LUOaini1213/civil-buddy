# 前端质量整改（frontend/index.html · frontend/workbench.html）

## bug 修复
- index：新增「有界辩论 · critic ↔ planner」卡片并在 `applyResult` 中接入 `bounded_debate` 数据，补齐 `test_bounded_debate.py::test_frontend_marker` 要求的 `boundedDebate` / `有界辩论` 标记（此前测试失败，现已通过）。
- index：`callApi` 对非 JSON 响应做安全解析（`res.json().catch`），错误条件补充括号明确优先级；错误文案统一走 `extractErr`，兼容 FastAPI `detail` 为字符串 / 对象 / 数组（422 校验错误）三种形态。
- index：文件上传 `onTenderFiles` 在完成后重置 `input.value`，修复「同一文件二次选择不触发 change」的问题；PDF 拦截分支同样重置。
- index：重新解析后清空旧的「成稿后再审」结果（`review`），避免陈旧审查结论挂在新矩阵旁。
- workbench：`fetchJson` 捕获 `AbortError`，超时改为中文提示（原来会直接显示英文 AbortError）；网络层失败（Failed to fetch）也给中文提示并提示确认网关已启动。
- workbench：WebSocket 增加 `sessionId` 变化监听自动重连（HITL 下发新 session、`?session=` 加载、checkpoint 恢复后原来仍订阅旧 session，收不到 live 事件）；旧 socket 的 onopen/onclose/onerror/onmessage 回调加 `this.ws === ws` 守卫，避免切换时状态互相覆盖。
- workbench：`reviseNl` 修复 `j.containerType || j.container_type` 笔误（`containerType` 字段不存在），改为直接取 `j.container_type`。
- workbench：`applyAgentSteps` 对空 payload 做空值守卫，避免异常路径下 `payload.public` 抛 TypeError。
- workbench：`pct()` 对非数值输入返回 `—`，避免界面出现 `NaN%`。

## 安全
- 复查两页所有服务端数据渲染路径：均为 Vue 文本插值（`{{ }}`）与 canvas `fillText`，无 `v-html` / `innerHTML` 拼接服务端数据，无需改动（保持现状即安全）。

## 结构优化
- workbench：删除死代码 `consumeSse`（无调用）、`isLikelyNext`、`scrollAgentConsole`、`fmtNum`、`revise()`（prompt 弹窗旧入口）及只写不读的 `skjolberLabel` 状态。
- workbench：抽取共用 SSE 读取器 `pumpSseResponse`，`replayRun` 改用之（消除与原 `consumeSse` 重复的流解析代码）；回放期间置 `sseActive`，修复回放与 WS 事件双份写入 `agentSteps` 的竞态。
- workbench：`beforeDestroy` 补充清理 `_drawTimer` 防抖定时器。
- 保留全部既有元素 ID、API 路径与测试依赖标记（`demoSimpleMode`、`data-demo-simple-mode`、`满载演示`、`href="/"`、`投标应答` 等均未改动）。

## 体验
- workbench：`cancel()` 取消确认原来无 loading 保护、无错误处理（失败静默且可连点），改为 `beginWork/endWork` + try/catch，失败给中文状态提示。
- workbench：`runPdf`、`restoreCheckpoint`、`replayRun` 统一接入 `beginWork/endWork` 连点保护（运行中再点只提示已运行秒数，不重复发请求），错误显示 `e.message` 而非对象序列化。
- index：复制按钮的「已复制」提示定时器改为可清理（连续复制不同导出时不再提前消失/串号）。
- index：OTEL 大盘加载失败的错误提示补中文前缀（原来直接显示英文异常文本）。

## 启动验证时追加的修复(2026-08-25)

- 【健壮性】Vue 2.7.16 本地化到 `frontend/vendor/vue.min.js`,两页改为优先加载 `/static/vendor/vue.min.js`、失败时回退 jsdelivr CDN。原先完全依赖外网 CDN,内网/离线或 CDN 不稳(国内常见)时整页只剩裸 `{{ }}` 模板。
- 【健壮性】`demo/static/app.js`:`/api/config`、`/api/threads` 在 Rust 工作台(8765)上不存在(原仓库即如此),原代码直接 `r.json()` 导致页面显示 "SyntaxError: Unexpected end of JSON input";现按 404 优雅降级,新建对话/并行任务按钮给出中文提示而非抛未捕获异常。
