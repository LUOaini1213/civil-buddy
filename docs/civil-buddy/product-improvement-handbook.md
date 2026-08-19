# Civil Buddy 产品改进手册

> 版本：2026-08-19  
> 对象：要把 Civil Buddy 从「垂直场景 harness」抽成 **可讲、可测、可挂业务的 Agent 运行时**，同时不越界成投标机器人或电视 AgentOS 克隆。  
> 对照：创维智能体平台岗所考的 Scheduler · Bus · ToolEngine · Memory · Auth · Trace。  
> 领域皮肤：土木工作搭子 + 投标矩阵 + 装箱交付。数字仍只许工具算。

全量产品规划书（总入口）：[product-plan.md](product-plan.md)。

相关文档：

- 现状内核叙事：[architecture-as-harness.md](../architecture-as-harness.md) · [harness-design.md](../harness-design.md)
- 主线 C：[product-mainline-tender-delivery.md](../product-mainline-tender-delivery.md)
- 66 岗下一刀：[post-horizon-2026-08-17.md](post-horizon-2026-08-17.md)
- 已做短刀：[next-steps.md](next-steps.md)
- 联网评测：[industry-agent-eval-2026-08-17.md](industry-agent-eval-2026-08-17.md)

**本手册不实现缺口，只规定怎么改、先改哪、怎样算做完。**

---

## 0. 一句话诊断

Civil Buddy **已经有护栏**（工具独占数字、chat/run、HITL、草稿门、评测脚本），**还没有平台内核**（通用调度、工具流水线、记忆 API、事件总线）。

面试官和用户听到「66 专家 / 装柜 / 矩阵」会当业务 demo。改进目标是：这些业务变成 **挂在同一套运行时上的插件**，运行时本身有接口、状态机、错误码和回放。

```
现在：  业务流（招标/装箱/岗） ──焊死──► 若干 Python 函数
目标：  应用插件 ──► Agent 运行时（Scheduler/Bus/Tool/Mem）──► LLM / Solver / KB
```

---

## 1. 产品身份（改之前先锁死）

### 1.1 我们是

内部讨论用 **AI 起草搭子 + 交付证据工作台**：

- 模型：理解、编排、解释  
- 工具：算柜、抽招标原文、写草稿文件  
- 运行时：谁跑、何时停、谁确认、留下痕迹  

默认产出永远是 **AI 草稿**。`submit_blocked=true`。不判定可投标，不判定可以开工。

### 1.2 我们不是

| 禁止当成产品能力 | 原因 |
|------------------|------|
| GeBIZ 代交 / 自动中标 | 门户不是评分办法；无签章 |
| 法定专项方案 / PE·QP·RTO 签认 | 须持证人员 |
| 十万字写标、标书查重产品化 | 易标 AGPL 路线，且会编业绩 |
| 模型手写 xyz / N0 / 条款号 | 不可评测、不可追责 |
| 「中标率 +N%」 | 没有、也不许编 |

### 1.3 改进成功的样子（对内）

一个人坐在默认页：

1. 提问 → 只聊，不写盘  
2. 要稿 → 该岗独有工具或招标矩阵  
3. 装箱 → **真 solver**，断线四个字段字面 `UNSPECIFIED`  
4. 每一步能指出 `run_id`、工具名、是否合法、耗时  
5. 高风险没有确认句就写不了盘  

对平台叙事：能在白板上画出 Scheduler / ToolEngine / Memory / Trace，并指到具体模块，而不是只讲幕墙故事。

---

## 2. 现状测绘（2026-08 现网）

### 2.1 五层对照

```
┌─────────────────────────────────────────────┐
│ 应用层  经营岗 UI · 66 岗 · /workbench 装箱  │  有
├─────────────────────────────────────────────┤
│ 编排层  understand chat|run|both · 大TeamA/B │  有（焊在业务里）
├─────────────────────────────────────────────┤
│ 运行时  缺独立 Scheduler / Bus / ToolEngine │  半套
├─────────────────────────────────────────────┤
│ 协议层  MCP 名齐、Skills 一份 SKILL.md       │  半套
├─────────────────────────────────────────────┤
│ 底座    应用沙箱 · OTEL 文件 · 脚本评测      │  半套
└─────────────────────────────────────────────┘
```

### 2.2 模块级诚实表

| 手册模块 | 现网落点 | 完成度 | 缺口一句话 |
|----------|----------|--------|------------|
| 任务调度 | `runtime/scheduler.py` + `runtime/agent_loop.py` 挂 `/api/agent` | 70% | 进程内串行；无跨进程队列/优先级 |
| 消息通信 | FastAPI + `runtime/bus.py` 进程内事件 | 40% | 无 Agent↔Agent 中间件，无端云 correlation id |
| 工具引擎 | `runtime/tool_engine.py`：allow/超时/熔断/沙箱 | 75% | 66 岗 run 仍多为 `write_deliverable` 骨架 md |
| 记忆 | Run.messages 工作记忆、`demo/out` 工件、分层 KB | 45% | 无长期记忆 API、无 user/device 隔离写入过滤 |
| 可观测 | `agent_steps`、OTEL jsonl、`/api/otel/dashboard`、Run 回放 | 55% | SDK 可选；Rust live eval 仍绑链接器 |
| 沙箱/权限 | ToolEngine.execute 调 `check_write` / `request_spawn` | 70% | 应用层；无多租户 ACL；非内核 jail |
| 评测 | 脚本 + shadow + `GET /api/eval/live` 离线针 | 70% | 联网评测仍是发版闸，不是日常 CI |
| 装箱接通 | `/api/tender/delivery` 与 `/workbench` **会真算** | 70% | **pack-ship 专家 turn 仍 `connected=False`** |
| 招标主线 | ingest + matrix + review + submit_blocked | 75% | 扫描 PDF 仍拒绝（可选 CLI，失败即拒） |
| 66 岗 | 同一套 chat/run | 50% | run 多为骨架 md，未按易标五段做实 |

### 2.3 两条已经能跑的用户路径（不要改坏）

1. **真装箱**：gateway `:8000` →「解析并生成交付证据」或 `/workbench` → `run_big_team`  
2. **先理解**：`POST /api/turn` 无专家 = 经营岗矩阵；带 `expert_id` = 66 岗 chat/run  

pack-ship 岗在 turn 里**不算柜**，只投影空快照。改进手册把「接通 solver 快照」列为 P0，不是新造第二套装箱。

---

## 3. 目标架构（改进后）

### 3.1 运行时对象

```
Run
  run_id, session_id, user_id?, expert_id?, intent, state
  messages[]          # user / assistant / tool
  steps[]             # 合法转移日志
  tools_used[]
  artifacts[]         # 写盘路径
  hitl                # required / confirmed / pending
  error_code?
```

状态机（合法边，其它一律拒绝并记 trace）：

```
pending → planning → acting → waiting_tool → reflecting → done
                              waiting_tool → acting
                 planning → waiting_hitl → acting
任何非终态 → cancelled | failed
禁止： done → acting
```

同 `session_id` **串行**（写盘保序）；跨 session 可并行。

### 3.2 ToolEngine 流水线（所有写盘/solver 必须走这里）

```
register(name, schema, handler, permission, timeout_s)
    list(query, expert_id)           # 发现，禁止 100 个全量进 prompt
    allow(user, expert, name)        # exclusive + HITL + sandbox
    validate(args, schema)
    execute(call) → {ok, data|error_code, duration_ms}
        超时 / 有界重试 / 同工具连续失败熔断
    normalize → 追加 role=tool 消息
    audit(run_id, name, args_digest, error_code)
```

错误码（固定，便于评测）：

| code | 含义 | 可否重试 |
|------|------|----------|
| `ok` | 成功 | — |
| `permission_denied` | 岗无权 / 未确认 / 沙箱拒 | 否 |
| `invalid_args` | schema 失败 | 否 |
| `timeout` | 单步超时 | 可 1 次 |
| `circuit_open` | 同工具连续失败 | 否，换策略或停 |
| `unspecified` | 工具未接通，字段写字面 UNSPECIFIED | 否（不是让模型补数） |
| `max_steps` | 步数用尽 | 否 |

### 3.3 最小 Agent Loop（生产可与 steps 并存）

```python
def run_agent(session, user_msg, tools, llm, max_steps=8):
    intent = understand(user_msg)          # chat | run | both
    if intent == "chat":
        return explain_only(session, user_msg)   # 禁止 tools.execute 写盘
    messages = session.load() + [{"role": "user", "content": user_msg}]
    for _ in range(max_steps):
        resp = llm.chat(messages, tools=tools.schemas_for(session.expert_id))
        if not resp.tool_calls:
            session.save(messages + [resp])
            return resp.content
        messages.append(resp)
        for call in resp.tool_calls:
            result = tools.execute(call, run=session.run)  # 含 allow/timeout
            messages.append({"role": "tool", "tool_call_id": call.id, "content": str(result)})
    return "达到最大步数，请缩小任务范围"
```

**生产默认仍是 `steps`**（成箱/拼柜/抽招标）。Loop 是平台接口；装箱几何继续禁止从 loop 里「自由发挥」。

### 3.4 记忆四层（按手册，落土木约束）

| 层 | 存什么 | 手段 | 禁写 |
|----|--------|------|------|
| 工作记忆 | 当前 Run messages / steps | 直接进 prompt | 密钥、`.env` |
| 会话记忆 | 摘要 + slot（辖区、项目名、P0） | 窗口满了压缩，打压缩标记 | 假装读过被丢掉的细节 |
| 长期记忆 | 可选：用户偏好辖区 | 显式 API，默认关 | 中标率、业绩、可以开工 |
| 程序记忆 | Skills / `SKILL.md` / 岗 SOP | 召唤该岗才加载 | 65 份人格戏服 |

### 3.5 MCP 与 Skills（不要再混）

| | Skills | MCP |
|--|--------|-----|
| 解决 | 怎么起草（禁语、辖区、确认句） | 能调什么（solver、KB、解析） |
| 现网 | `skills/civil-buddy/SKILL.md` | `civil.bid.*` / `pack-ship__*` / `kb://` |
| 改进 | 按任务渐进披露，不要一份巨无霸 | 真 Host（Claude/Cursor/本机）去 `tools/list`；pack-ship 接通 solver |

---

## 4. 改进原则（每刀都要过）

1. **抽内核，不毁皮肤。** `run_big_team`、招标 pipeline、66 岗名册继续当插件。  
2. **工具算数，模型编排。** 新代码不得让 LLM 写 xyz / N0 / 条款号 / 单价。  
3. **提问不写盘。** `intent=chat` 时 ToolEngine 对写盘类返回 `permission_denied`。  
4. **失败可分类。** 禁止 `except: pass` 后让模型补数；用上一节错误码。  
5. **评测先于叙事。** 每刀必须有驱动**已上线入口**的脚本，而不是「演示过」。  
6. **Python 先做内核接口**（JD 必备）。Go 热路径列为 P2，不阻塞。  
7. **不把总判改成「合格」** 除非默认面真能 chat/run + 真装箱 + 可回放 Run。

---

## 5. 分期路线

### P0 · 内核可讲（约 2–3 刀，优先）

目标：简历能写「ToolEngine + Scheduler + 真装箱接通」，面试能画状态机并指到代码。

| 刀 | 做什么 | 验收（必须跑） |
|----|--------|----------------|
| **P0-1 接通 pack-ship** ✅ | `expert_turn` 先 `health`；有 `packing_summary` / 会话快照则原样抄进 list/plan/export；无则四字段字面 `UNSPECIFIED`。delivery 会 `save_packing_snapshot`。 | `python scripts/test_runtime_p0.py` |
| **P0-2 ToolEngine** ✅ | `packing_assistant/runtime/tool_engine.py`：`register/list/allow/execute`。chat 拒写盘；岗 exclusive；超时/熔断错误码。 | 同上 |
| **P0-3 Scheduler + Run** ✅ | `packing_assistant/runtime/scheduler.py`：合法边、`max_steps`、cancel。`POST /api/turn` 带 `run_id`；`GET /api/runs/{id}`。 | `done→acting` 拒绝；cancel 后 execute `permission_denied` |

P0 不做：长期记忆、Go 重写、PDF OCR、66 岗全部富写盘。

### P1 · 平台可复用（挂上业务插件）

| 刀 | 做什么 | 验收 |
|----|--------|------|
| **P1-1 投标三岗共用 handoff** ✅ | bid-parse 写 `tender.handoff.json`；compliance 读它出三列；tech 只按评分点排目录 | 无评分点不套模板；`submit_blocked` 仍 true |
| **P1-2 Python eval/live** ✅ | `GET /api/eval/live`：understand 分流 + 官方标题针（GST 9%、Fire Code、CTU、GeBIZ≠评分）不绑 `link.exe` | 冷启动可跑；IRAS 针失败不得改口「官方没写 9%」除非打开页确实没有 |
| **P1-3 Memory API** | `session.summary` + slot（辖区/项目/P0）；压缩可见；写入过 `scan_forbidden` | 压缩后提示不得假装读过被丢细节 |
| **P1-4 Trace 回放** | `GET /api/runs/{run_id}` 返回 messages+steps+tools+duration；OTEL span 带同一 `run_id` | 两次 GET 同一 identity，非夹具 |
| **P1-5 施工/危大** | scheme_draft 后可填 docx；judge-card 默认 SG WSH/PTW；确认句硬校验 | 未确认 0 份稿；正文无「可以开工」断言 |

### P2 · 体验与宿主（有余力）

| 刀 | 做什么 | 明确不做 |
|----|--------|----------|
| 可选 MinerU/Docling CLI，失败拒绝 | 默认 GPU OCR |
| MCP 真 Host 配置说明 + `kb://` 分页 | 自研第二个协议 |
| 按 `post-horizon` 富化独有工具栏位 | 65 份人格、IFC 全量抽量 |
| Go 版 Scheduler 热路径（session worker + context） | 用 Go 重写投标解析 |
| 多用户 ACL（user_id 隔离 KB 写入） | 内核 Landlock、Grafana 必选 |

66 岗富化顺序跟 [post-horizon-2026-08-17.md](post-horizon-2026-08-17.md) 总序，**每岗下一刀已经写好，不要在本手册再复制 66 遍**。

---

## 6. 分模块规格

### 6.1 Scheduler

**文件建议：** `packing_assistant/runtime/scheduler.py`

职责：Run 生命周期，不是装箱算法。

- 创建：`create_run(session_id, text, expert_id, intent)`  
- 推进：只允许合法边  
- 停止：`max_steps`、用户 cancel、HITL pending、`circuit_open`  
- 查询：`get_run(run_id)`  

与现网衔接：`POST /api/turn` 内部先 `create_run`，chat 则 `planning→done` 且 `wrote=false`；run 则进入 `acting`。

### 6.2 ToolEngine

**文件建议：** `packing_assistant/runtime/tool_engine.py`

第一批必须注册的工具：

| name | permission | 备注 |
|------|------------|------|
| `pack-ship__list/plan/export/health` | expert=pack-ship | plan/export **投影** solver，禁止二次 packing |
| `tender.parse` | 经营岗或 bid-parse | 产出 matrix，`submit_blocked` |
| `tender.review` | 成稿后 | 不改 `can_fit`、不填业绩 |
| `*.__scan_forbidden` | 本大类 | 写盘后 |
| 各岗 exclusive | 仅该 `expert_id` | 兄弟调用 `permission_denied` |

`execute` 必须调 `sandbox.assert_write` 才能落盘。

### 6.3 Bus（先做最小）

P0 不必上消息中间件。最小总线 = 进程内队列：

```
Event{run_id, type, payload, ts}
types: run_started | tool_call | tool_result | hitl | run_ended | cancelled
```

SSE `/api/runs/{id}/stream` 订阅同一事件。端云协同列为 P2（电视场景再讲，本仓先接口形状）。

### 6.4 Memory

P1 才做独立 API。P0 继续用：

- 工作记忆 = Run.messages  
- 程序记忆 = SKILL.md + 岗 KB  
- 禁止新造「自动记住中标项目」  

### 6.5 pack-ship 接通（P0-1 细节）

当前问题：`expert_turn.py` 写死 `connected=False`。

正确顺序：

1. `pack-ship__health`  
2. 若有会话内 `packing_summary`（刚跑过 delivery）或 sidecar 快照 → `connected=True`，四字段 **等于快照**  
3. 否则四字段 **字面** `UNSPECIFIED`，`xyz` 永远 UNSPECIFIED  
4. 禁止在 turn 里再调一套 3D packer「对照着算一遍」  

用户路径：默认页先「解析并生成交付证据」再召唤 pack-ship，应能抄到刚才的 `can_fit`。

### 6.6 默认面文案

保持：内部讨论 AI 草稿、不可递交、不判定可投标。  
禁止改成：可以投标、可以开工、中标率。

---

## 7. 评测与合格线

### 7.1 每刀回归（不得红）

```
python scripts/test_understand.py
python scripts/test_expert_turn.py
python scripts/test_mcp_surface.py
python scripts/test_tender_ingest.py
python scripts/test_tender_review.py
python scripts/test_sandbox.py
python scripts/test_runtime_p0.py
python scripts/test_agent_loop.py
```

### 7.2 平台新闸（P0 起新增）

| 脚本 | 必须看到 |
|------|----------|
| `test_tool_engine.py` | deny / invalid / timeout / chat 拒写 |
| `test_scheduler.py` | 合法边；cancel；max_steps |
| `test_pack_ship_connect.py` | 快照相等；断线 UNSPECIFIED |

### 7.3 产品总判（不要提前改口）

| 总判 | 条件 |
|------|------|
| 部分合格（现在） | 护栏有，内核未抽，pack-ship turn 未接通 |
| 合格 · 内部起草搭子 | P0 三刀 + 默认面真装箱可抄数 + Python eval/live |
| 不合格 · 签认/递交类 | 永远不要追求 |

---

## 8. 电视/家庭场景怎么映射（面试与设计共用）

不改产品去做电视，但内核接口要能讲迁移：

| 电视约束 | Civil Buddy 已有类比 | 改进时保留 |
|----------|----------------------|------------|
| 设备误操作 | 危大确认句、submit_blocked | HITL 作为 ToolEngine.allow 的一环 |
| 多用户 | KB 岗/大类/公司分层 | P2 加 user_id |
| 可撤销 | 草稿、不代交 | 禁止自动执行 IoT 类工具 |
| 端云 | 本机网关 + 可选隧道 | 重推理上云，意图可在端 |
| 延迟 | steps 默认不依赖 LLM 算几何 | 热路径以后 Go |

---

## 9. 90 天排期（连续实习强度，可压缩）

| 周 | 交付 |
|----|------|
| 1 | P0-1 pack-ship 接通 + 测试 |
| 2–3 | P0-2 ToolEngine，迁 pack-ship 与 turn 写盘 |
| 4 | P0-3 Scheduler 状态机挂 `/api/turn` |
| 5–6 | P1-1 投标三岗 handoff |
| 7 | P1-2 Python eval/live |
| 8–9 | P1-3/4 Memory 摘要 + Run 回放 |
| 10 | P1-5 施工/危大确认与禁语 |
| 11–12 | 按 post-horizon 做 2–3 个高价值岗富写盘（造价 takeoff / 危大卡 / 税务日历栏位） |

每周仍跑 §7.1 全套。

---

## 10. 文档与代码索引（改完要更新）

| 改了什么 | 更新哪 |
|----------|--------|
| 内核模块 | 本手册 + `architecture-as-harness.md` |
| 短刀完成 | `next-steps.md` 打勾 |
| 某岗写盘变富 | `post-horizon-2026-08-17.md` 该 id 的「下一刀」改已做 |
| 评测口径 | `industry-agent-eval-*.md` 只在行为变了以后改总判 |

建议新目录：

```
packing_assistant/runtime/
  scheduler.py
  tool_engine.py
  bus.py
  run.py
```

现有 `harness.py` / `expert_turn.py` / `product_turn.py` 改为调用 runtime，而不是再分叉一套。

---

## 11. 一页速记

```
身份：内部起草搭子，不是签章/递交
抽：Scheduler · ToolEngine · Run/Trace ·（后）Memory
不抽坏：run_big_team 几何、submit_blocked、UNSPECIFIED、chat 不写盘
P0：pack-ship 抄快照 → ToolEngine → 状态机挂 /api/turn
P1：投标 handoff · Python eval · 回放 · 危大卡
永远不做：GeBIZ 代交、编 xyz、中标率、可以开工当能力
验收：脚本打已上线入口，不讲「演示过」
```

---

## 12. 下一刀（手册执行入口）

**P0 已落地。完整 Agent 循环 + 沙箱 + eval/live + P1-1 handoff 已落地。** 下一刀 **P1-4**：Run 回放 messages/steps/tools。行业总判仍是 **部分合格**。过夜规划见 [overnight-eval-iterate-2026-08-19.md](overnight-eval-iterate-2026-08-19.md)。
