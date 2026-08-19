# 长程任务：联网评测 → 优化 → 更新 → 迭代（跑到 2026-08-20 08:30 +08）

> **已废止（空转）。** 心跳 sleep + 定时刀没有把文档 / KB / MCP / Skill 做成产品。  
> 现行规划改走：[product-completion-plan.md](product-completion-plan.md)。  
> 监督进程与 90 分钟 scheduler 已停。本页只作历史，不要再启动 `overnight_civil_supervisor.py`。

> 编写时刻：2026-08-19 22:30 中国标准时间  
> 截止： **2026-08-20 08:30:00+08:00**（约 10 小时）  
> 仓库：`C:\Users\LW\civil-buddy` · 分支 `main`  
> 身份：内部讨论 AI 起草搭子。默认产出永远是草稿。`submit_blocked=true`。

本文件是**可执行规划**，不是愿望清单。心跳脚本、监督进程、Grok 定时刀都按这里的闸运行。

相关：

- 手册：[product-improvement-handbook.md](product-improvement-handbook.md)
- 行业总判仍是 **部分合格**：[industry-agent-eval-2026-08-17.md](industry-agent-eval-2026-08-17.md)
- 66 岗下一刀：[post-horizon-2026-08-17.md](post-horizon-2026-08-17.md)
- 离线闸：`GET /api/eval/live` · `python scripts/test_agent_loop.py`

---

## 0. 一句话

从现在起到明早 8:30，用 **Python 心跳（评测/回滚闸）+ Grok 定时刀（每次只改一处）** 自动循环：联网对照官方标题 → 对照手册缺口 → 落地一刀 → 回归 → 记分。到点停，写出早报。不准把总判改成「合格」，不准把可以投标 / 可以开工做成能力。

```
while now < 08:30:
    离线闸 → 联网抽查官方页 → 对照刀队列 → 至多 1 个产品改动
    回归红 → git reset --hard 本轮起点
    写 cycle-N.json + STATUS.md
    睡到下一拍（默认 40 分钟）或截止
08:30: FINAL_REPORT.md · 停刀 · 停心跳
```

---

## 1. 成功标准（明早 8:30 对人讲）

必须能指到磁盘上的证据，而不是「跑过」。

| 项 | 过线 |
|----|------|
| 心跳还在或已干净停 | `output/overnight-civil/STATUS.md` 最后一行是截止或 `DONE` |
| 离线闸 | 每个 cycle 的 `gates.fast` 为 pass；慢闸（66 岗）至少首尾各一次 |
| 联网评测 | 每个 cycle 有 `live_web.json`；IRAS 抓失败 **不得** 写「官方没写 9%」 |
| KB 口径 | `demo/kb/finance/finance-tax/web-knowledge.md` 仍有页述 **9%** |
| 产品不越界 | 正文无「可以投标」「可以开工」「中标率」当能力；`submit_blocked` 仍 true |
| 装箱数字 | 断线四字段仍字面 `UNSPECIFIED`；有快照则原样抄 |
| 迭代 | 至少尝试手册队列里的下一刀；红则回滚并记 `rolled_back` |
| 总判 | 文档仍写 **部分合格**，除非手册「合格」三条同时成立（默认面真装箱可抄 + 完整循环 + eval/live）**且** 早报明确列出证据 |

「合格 · 内部起草搭子」即使闸全绿，也要早报里**人工**改口，脚本不得改 `industry-agent-eval-*.md` 的总判句。

---

## 2. 明确不做（整晚有效）

| 禁止 | 原因 |
|------|------|
| GeBIZ 代交 / 自动中标 | 门户不是评分办法 |
| 改口「可以投标 / 可以开工」 | 须持证人员 |
| 模型手写 xyz / N0 / 条款号 / GST 税率 | 不可追责 |
| 抓 IRAS 失败就删 KB 里的 9% | 已知渲染页有 9%，壳页面常抽空 |
| 66 份人格戏服、十万字写标 | 手册非目标 |
| 并入 OpenBidKit AGPL | 许可与产品边界 |
| 提交 `.env` / API Key | 安全 |
| 内核 Landlock / Grafana 唯一大盘 | 已否决 |
| 把 packing `autonomy_12h_loop.py` 当本晚主循环 | 那是装箱 phase0 分数环，不是 Civil Buddy 产品刀 |

---

## 3. 双层运行时

### 3.1 层 A · Python 心跳（必跑，不依赖本对话还开着）

| 文件 | 职责 |
|------|------|
| `scripts/overnight_civil_loop.py` | 一轮：闸 + 联网 + 记分 +（可选）一刀 |
| `scripts/overnight_civil_supervisor.py` | 崩溃重启，直到 `AUTONOMY_END_TS` |
| `output/overnight-civil/` | 产物（gitignore，不进 Git） |

环境变量：

| 变量 | 缺省 | 含义 |
|------|------|------|
| `AUTONOMY_END_TS` | `2026-08-20T08:30:00+08:00` | 绝对截止 |
| `OVERNIGHT_SLEEP_SEC` | `2400` | 两轮间隔（秒） |
| `OVERNIGHT_COMMIT` | `1` | 闸绿且有产品 diff 才 commit |
| `OVERNIGHT_PUSH` | `0` | 默认不 push；早报提醒 |
| `OVERNIGHT_ONCE` | `0` | `1` 只跑一轮（烟测） |
| `OVERNIGHT_LIVE_WEB` | `1` | 抓官方页；失败不改 KB |
| `OVERNIGHT_APPLY` | `1` | 是否允许本进程改代码（Grok 刀优先时心跳只评测） |

启动：

```powershell
cd C:\Users\LW\civil-buddy
$env:AUTONOMY_END_TS = "2026-08-20T08:30:00+08:00"
$env:PYTHONUNBUFFERED = "1"
python scripts/overnight_civil_supervisor.py
```

停：结束监督进程，或等到 08:30 自己写 `DONE`。

### 3.2 层 B · Grok 定时刀（优化迭代，跨会话 durable）

间隔 **90 分钟**，`durable=true`，截止后的触发只写早报并停任务。

每刀必须：

1. 读 `output/overnight-civil/STATUS.md` 与 `queue.json`
2. 只做队列**第一项未完成**刀
3. 跑本刀验收脚本 + 快闸
4. 红则 `git reset --hard` 到本刀起点
5. 更新 `queue.json`（`done` / `blocked` / `rolled_back`）
6. 不改行业总判句

若对话已关，durable 任务仍应在时刻触发；心跳层 A 不依赖刀层 B。

---

## 4. 一轮协议（约 40–70 分钟墙钟）

```
T0  读截止；剩余 < 8 分钟 → 写 FINAL 并退出
T1  git rev-parse HEAD → cycle_start
T2  快闸（understand / sandbox / runtime_p0 / agent_loop /
        tender_review / mcp_surface / industry_agent_eval）
T3  每第 3 轮 + 首尾：test_expert_turn + test_tender_ingest
T4  packing_assistant.runtime.eval_live.live_eval()（不抓 IRAS）
T5  联网：IRAS GST · SCDF Fire Code 2023 · IMO CTU · GeBIZ · MOF
    · 超时 25s · 浏览器 UA
    · 抓到 9% → gst_page_has_9=true
    · 抓失败 → gst_page_has_9=null，note=fetch_failed
    · 禁止：fetch_failed ⇒ 「官方没写 9%」
T6  对照 queue.json 下一刀；若 OVERNIGHT_APPLY=1 且无 Grok 占用锁，可落一刀
T7  再跑快闸；失败 → reset --hard cycle_start，记 rolled_back
T8  可选 commit（不含 .env）
T9  写 cycle-NNN.json · STATUS.md · heartbeat 一行
T10  sleep min(SLEEP, remaining-60s)
```

快闸任一项红：本轮不改代码（若已改则回滚）。联网失败**不是**红闸，只记 `live_web.ok=false`。

---

## 5. 联网评测口径（发版闸，不是改税率的借口）

| URL | 过线（正文或标题） | 失败时 |
|-----|-------------------|--------|
| [IRAS Current GST rates](https://www.iras.gov.sg/taxes/goods-services-tax-(gst)/basics-of-gst/current-gst-rates) | 出现 `9%` 或 *The current GST rate in Singapore is 9%* | 保留 KB 9%；报告 `fetch_failed` 或 `js_shell` |
| [SCDF Fire Code 2023](https://www.scdf.gov.sg/fire-safety-services-listing/fire-code-2023) | `Fire Code 2023` | 不编条款号 |
| [IMO CTU Code](https://www.imo.org/en/ourwork/safety/pages/ctu-code.aspx) | `CTU Code` 与 `2014` | 不编章条 |
| [GeBIZ](https://www.gebiz.gov.sg/) | 电子采购门户 | **不是**评分办法 |
| [MOF procurement processes](https://www.mof.gov.sg/policies/government-procurement/procurement-processes/) | sourcing / evaluation / award | 分值只抄 ITT |

对照本仓 KB：四针仍在 `demo/kb/**/web-knowledge.md`。聊天回复「什么是 GST」必须带 **9%**。

---

## 6. 刀队列（本晚顺序，每轮至多 1）

| 序 | 刀 | 验收 | 停条件 |
|----|----|------|--------|
| 1 | **P1-1** bid-parse 落 `tender.handoff.json`；compliance 三列；tech 只按评分点 | `python scripts/test_tender_handoff.py` + expert_turn 不红 | 无评分点不套上个项目目录；`submit_blocked` |
| 2 | **P1-4** `GET /api/runs/{id}` 含 messages/steps/tools/artifacts | 两次 GET 同一 `run_id` | 不把 packing `output/runs` 冒充 Scheduler Run |
| 3 | **P1-3** 会话 slot：辖区 / 项目名 / P0；压缩可见 | 压缩后提示不得假装读过被丢细节 | 不自动记中标项目 |
| 4 | **P1-5** method-hazard：未确认 0 份稿；草稿过禁语 | 确认句硬校验 | 不判定可以开工 |
| 5 | eval/live 加 CORENET X / APPBCA-2026-12 针（只抄 KB 已有句） | `GET /api/eval/live` 新针 found | 不编 GFA 数字 |
| 6 | 默认面 Agent 循环：HITL / max_steps 文案与 UI `run_id` | test_agent_loop | 不改 packing solver |
| 7 | 刷新早报、对照 66 岗 post-horizon **只更新「已做」标记** | 文档与代码一致 | 不新开 65 份人格 |

队列耗尽后心跳只评测，不再为了「显得在干活」改代码。

---

## 7. 回滚与锁

- 每轮开始记下 `HEAD`。
- 产品测试红 → `git reset --hard HEAD_at_cycle_start`（不 `-A` 清 `output/`）。
- `output/overnight-civil/apply.lock`：Grok 刀与 Python APPLY 互斥，TTL 25 分钟。
- 同 session 的 Civil Buddy Scheduler 仍串行；本晚不要对同一 `session_id` 并行写盘。
- 连续 3 轮快闸红且无 diff：停止 APPLY，只评测到截止（防止空转改坏）。

---

## 8. 产物（均在 `output/overnight-civil/`）

| 文件 | 内容 |
|------|------|
| `STATUS.md` | 给人看的活页：截止、HEAD、最近一轮闸、下一刀 |
| `queue.json` | 刀状态 |
| `cycle-001.json` … | 机器可读一轮 |
| `live_web.json` | 最近一次官方页抓取（截断正文，不含 Cookie） |
| `heartbeat.log` | 每轮一行 `CYCLE n=… remaining_h=…` |
| `supervisor.log` | 崩溃/重启 |
| `FINAL_REPORT.md` | 08:30 早报 |
| `loop.pid` / `loop.lock` | 单例 |

早报必须含：轮次、闸绿/红、联网四页结果、落地的刀、回滚次数、剩余缺口、总判仍是部分合格。

---

## 9. 时间盒（22:30 → 08:30）

| 墙钟 | 做什么 |
|------|--------|
| 22:30–23:10 | cycle 0：基线闸 + 联网；P1-1 若未做则做 |
| 23:10–00:40 | cycle 1–2：P1-1 收尾或 P1-4 |
| 00:40–03:00 | cycle 3–4：P1-3 或评测-only（困了也只许小刀） |
| 03:00–06:00 | cycle 5–6：P1-5 / eval 针；慢闸 66 岗 |
| 06:00–08:00 | cycle 7–8：冻结合并，只评测 |
| 08:00–08:30 | 早报、停刀、停心跳 |

不是精确闹钟，是优先级。截止一到，写到一半的刀 **回滚** 而不是带着红测试过夜。

---

## 10. 与现网服务

本晚评测走 **进程内 TestClient / 函数**，不依赖 8000/8765 一直开。若本机网关已开：

- http://127.0.0.1:8000/ → Agent 循环  
- http://127.0.0.1:8000/api/eval/live  
- http://127.0.0.1:8765/ → 66 岗工作台  

心跳不重启这两台，以免打断你正在看的页面。

---

## 11. 早报怎么读（08:30）

1. 打开 `output/overnight-civil/FINAL_REPORT.md`  
2. `git log --since=2026-08-19.22:00` 看落地 commit  
3. `python scripts/test_agent_loop.py` 若仍绿，循环没被改坏  
4. 总判：默认仍 **部分合格**  

需要推 GitHub 时人工 `git push`（`OVERNIGHT_PUSH` 缺省关）。
