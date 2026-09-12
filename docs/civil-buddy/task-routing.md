# 工作台任务入口与岗位路由

工作台保留 66 岗目录，同时提供常用任务卡。卡片只预填任务，用户检查后发送；不自动提交、不自动确认高风险任务。

## 用户入口

- 「整理日报」「检查投标响应」「制定备份策略」「写钢构说明」可直接匹配岗位，无需先记住岗位全名。
- 显式选择或 `@岗位` 优先。单岗请求不会自动扩成三岗协作。
- 「设计变更」既可能是技术会审，也可能是商务签证。界面显示候选与职责，选中后预填原任务，等待用户发送。
- 综合投标响应检查采用 `tender-review`：先解析招标原文，技术响应与响应缺口两个子任务依赖解析结果并可并行，最后汇总。
- 「先招标解析，再准备施工方案」保留两个岗位和先后依赖。依赖描述执行计划，不保证任何未实现工具已经执行。
- 纯说明问题仍为问答，不启动写入或协作工作流。

附件旁可选「自动判断 / 招标原文 / 投标响应 / 参考资料」。只发送当前所选附件的显式用途；自动判断不提交枚举，服务端按文件名保守分类。业务问答无需强制指定用途。原文要求与响应候选分别展示，找到候选不表示已核验满足要求。

岗位名称旁和首页「岗位资料与工具」可查看本岗输入、工具可用性、步骤、交付结构、草稿检查标准和能力边界。工具可调用不等于连接了计算求解器，以该岗位能力边界为准。

## 接口约定

`packing_assistant/runtime/task_router.py` 的纯函数（`demo/task_router.py` 仅兼容导出）：

```python
route_task(message, expert_ids=None)
# expert_ids, workflow, candidates, reason, ambiguous, intent, steps
```

`intent` 保留 `chat/run/both`。`steps` 每项包括 `id, expert_id, label, depends_on`。调用方负责根据实时目录验证岗位可用状态，执行前必须重新路由和校验权限；路由本身不会执行工具或提供授权。原有 Python/Rust `match_skill` 与强词契约保持不变。

前端消费：

- `GET /api/experts/{id}/capability`：`expert_id,name,risk,inputs,tools,steps,output_sections,acceptance,limitations`；工具包含 `name,label,available`。
- SSE `status` 事件：`phase="routing"`，携带 `route`；`done.route` 可再次包含最终选择。
- SSE `collaboration` 事件及 `done.collaboration`：工作流状态、`children`、`review` 和 `aggregate_metrics`（或 `metrics`）。
- 子任务包括 `task_id,skill,status,conclusions,evidence,unresolved`。模型分析显式标未核实；证据按原文与来源显示。
- `review.response_comparison` 区分响应候选、未匹配和未提供；不得将候选呈现为合格结论。
- 汇总预算展示 `input_tokens,output_estimated,limit,reserved_tokens,estimated,counter`。UTF-8 字节口径标为保守估算，不称为供应商账单用量。
- 聊天请求的 `attachment_roles` 是所选附件 ID 到 `tender/response/reference` 的映射；会话详情用同名字段恢复。

## 回归

`scripts/test_task_router.py` 覆盖短任务、显式优先、歧义、复合依赖、问答边界和旧契约未改变。

`scripts/test_chat_stream.cjs` 覆盖任务卡、候选选择、协作状态和证据、预算、岗位能力读取、旧异步响应隔离以及附件用途的提交与恢复。测试不调用真实模型。
