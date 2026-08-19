# 长程：知识库 + MCP

> 2026-08-17 起。只管协议原语、库时效、招标抽取并表。  
> **66 岗独有工具名册不归本文**：仍由 [`yibiao-mcp-map.md`](yibiao-mcp-map.md) + `workbench/yibiao-map.json` 维护。  
> MCP 对照 [2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28/server/resources)：Tools（模型选）· Resources（宿主读）· Prompts（人点工作流）。

## 洞（仍成立的部分）

- 2026-08-17 **之前** `civil-mcp` 只宣告 `tools`。现已在源码里补 resources / prompts；本机若无 MSVC `link.exe`，**不能把 `civil-mcp` 二进制当作已验收入口**。
- 岗上 `web-knowledge` 主体仍是 2026-08-14 门户摘录；投标 / 装箱岗补了 08-17 接线，其余大类未季更。
- 工作台招标抽取与装箱 `tender.handoff.v1` 必须走**同一变换**（天数 / ★ / 评分点只抄原文）。

## 阶段

| 阶段 | 做什么 | 验收 | 状态 |
|------|--------|------|------|
| **A** | MCP 三原语；bid / pack-ship 库接线；检索吃文件名 | 可运行面宣告 tools+resources+prompts；`kb://` 不见兄弟私库；读兄弟 URI 拒绝；bid/pack-ship prompt 不教「可投标 / 编 xyz / 编条款号」 | **部分完成**（见下） |
| **B** | 工作台 bid-parse 抽取与 `tender.handoff.v1` 同一变换 | 同输入 → 同 `duration_days`、同 ★ 原文、同评分点原文 | **已做**（`workbench_bid_extract` = `parse_tender_text`；Rust `bid-parse__extract` 调 `run_tender_extract.py`，无 Python 时才回退 `extract.rs`） |
| **C** | 16 大类 `web-knowledge.md` 按季度再联网，只改入口与页更日期 | 禁止新编条款号；每次最多 1 个大类 | **延期**（维护纪律，不是今晚） |
| **D** | resource 订阅 / 分页；prompts 按 CN/SG 分模板 | 有真实 MCP 宿主订阅后再做 | **延期**（可选） |

### 阶段 A 已落地 vs 未证明

| 面 | 状态 |
|----|------|
| Python 工作台 `demo/mcp_surface.py` + `GET /api/mcp/*` | 可运行、有测试 |
| Rust `workbench/src/mcp.rs`（`handle_rpc`） | 源码已接 `resources/*` `prompts/*`；`tests/mcp_protocol.rs` 在无 `link.exe` 时**编不过**，不能当作 launch |
| bid-parse / bid-compliance / pack-ship `web-knowledge` 08-17 接线 | 已写进口 |
| 文件名加权检索 | 已做 |

## 依赖

- B 不依赖 C/D。C 不依赖 D。
- 用 `civil-mcp` 跑 A 的 Rust 验收需要链接器；今晚验收以 Python MCP 面为准。
- 双实现（Rust mcp.rs ↔ Python mcp_surface）靠相同 URI / prompt 名；改名必须两边一起改。

本轮 GitHub 对照（2026-08-17）：见 [`github-directions-2026-08-17.md`](github-directions-2026-08-17.md)。不重开阶段 B。

## 明确不做

GeBIZ 递交、扫描 PDF 当全文库、规范正文进仓、沙箱 / 通用 spawn / OTEL、重写 66 岗名册、装箱评分离线循环。
