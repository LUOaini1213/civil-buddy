# Civil Buddy as harness

Every summoned expert is a harness that **understands first**.

- **Chat** — 问、解释、现行口径：DeepSeek + 只读工具（`search_kb` / `web_search` / `web_open`），不成稿。
- **Run** — 写、抽出、编制：本岗 `run_expert_steps`，出稿后再白话说明。
- **Both** — 先跑再聊，例如「解释完再出一份」。
- **Firm pack** — 成套 / 易标 / 一人公司：`run_bid_steps` 一次。

默认是 **chat**。用户没要求成稿就不要落盘。写盘仍是 steps；聊天不当计算器。

| Layer | Where |
|-------|--------|
| Runtime | `understand` → chat / run / both |
| Tools | `packs::execute` whitelist; exclusive refuse; packing-agent computes xyz |
| Memory | `demo/out/<session>/runs/<run_id>/trace.json` |
| Eval | `shadow_eval` · `shadow_eval_expert` · `GET /api/eval/live` |
| Trace | ordered `steps` + `trace.json` |
| HITL | 高风险专家写盘前确认句 |

- `GET /api/architecture`
- `POST /api/firm/bid`
- `POST /api/harness/expert`
- `POST /api/eval/shadow`
- `POST /api/eval/shadow-expert`
- `GET /api/eval/live`
- `GET /api/harness/trace/{session}/{run_id}`

## 文档解析（可选外挂）

`CIVIL_PARSE=auto`（缺省）：文字层够用走内置；扫描件依次试本机 CLI。

| 引擎 | 安装 | 环境变量 |
|------|------|----------|
| MinerU | `pip install "mineru[all]"` | `CIVIL_MINERU_BIN` |
| Docling | `pip install docling` | `CIVIL_DOCLING_BIN` |
| Marker | `pip install marker-pdf` | `CIVIL_MARKER_BIN` |

`CIVIL_PARSE=builtin` 关闭外挂。`GET /api/health` 的 `parse` 显示是否探测到 CLI。不把易标 AGPL 代码并进本仓。
