# 运行时协议

66 岗同一套 understand。默认 **chat**。提问不写盘。`submit_blocked=true`。

## 意图

| 值 | 何时 | 写盘 |
|----|------|------|
| `chat` | 问、解释、算不算、先别写 | 否。写盘工具 → `permission_denied` |
| `run` | 写/编制/出一份/解析招标 | 是，走 ToolEngine + 沙箱 |
| `both` | 解释完再出一份 | 先解释再写 |

入口：`POST /api/agent`（完整循环）· `POST /api/turn`（兼容）· `POST /api/understand`（只分类）。

## 会话上下文（Civil Buddy 管，不交给 DeepSeek）

DeepSeek `chat/completions` 无会话。客户端把 `session_id` 当工地/标段档案号一直带着。服务端每轮从 `demo/out/<session>/` 装配短槽，不把 66 岗 KB 或聊天全文当事实：

| 槽 | 文件 |
|----|------|
| 辖区 / 项目 / P0 / 压缩打标 | `session.summary.json` |
| 招标交接 | `tender.handoff.json` |
| 装箱投影 | `packing_summary.json` |

`POST /api/agent` 响应带 `context`。只读：`GET /api/context/{session_id}`。压缩后 `dropped_note` 进回复，禁止假装读过被丢细节。默认项目名「幕墙项目投标应答（草稿）」不得盖掉槽里已有项目。

## 状态机

`pending → planning → acting → waiting_tool → reflecting → done`  
高风险：`planning → waiting_hitl`。禁止 `done → acting`。同 `session_id` 串行。

确认句原文：`我明白，将由持证人员签认`。

## ToolEngine 错误码

| code | 含义 |
|------|------|
| `ok` | 成功 |
| `permission_denied` | 岗无权 / chat 写盘 / 沙箱拒 / 已取消 |
| `invalid_args` | schema 失败 |
| `timeout` | 单步超时 |
| `circuit_open` | 同工具连续失败 |
| `unspecified` | 未接通，字段写字面 UNSPECIFIED |
| `max_steps` | 步数用尽 |

装箱数字只抄 solver。断线：`utilization` / `can_fit` / `mid50` / `系固待办` 字面 `UNSPECIFIED`。禁止模型写 xyz。

## 沙箱（应用层，非内核 jail）

允许写根：`output/` · `demo/out` · `demo/kb` · `demo/data` · `workbench/out`。  
拒绝：`.env` / secret / `*.pem` `*.key`；`cmd` / PowerShell / 通用 spawn。

## 禁断言

禁止把可投标、开工断言、中标率写成产品能力。扫描命中则不得报成功。
