# GitHub 对照后的改进方向（2026-08-17 联网）

本轮拉取了 MCP / 投标 / 装柜三类公开仓。详细出处见会话 scratch 的 `github-sources.md`。Horizon **B（抽取并表）已做**，不再当缺口。

1. **给 MCP 找一个真宿主** — 服务端已有 tools/resources/prompts，没有客户端去读 `kb://` 或点 `civil.bid.parse`。[Copilot CLI #1518](https://github.com/github/copilot-cli/issues/1518) 说明大宿主也常只接 tools。[knowledge-base-mcp-server](https://github.com/jeanibarz/knowledge-base-mcp-server) 把「按意思检索」和「按文件浏览」拆开。分页/订阅仍按 horizon **D 延期**。
2. **招标文件进矩阵，而不是加长写标** — [OpenBidKit 易标](https://github.com/FB208/OpenBidKit_Yibiao) 有 MinerU/本地解析和废标/查重工作区。我们主线 C 仍主要是粘贴与 `.txt/.md`。下一步应是「整节招标进响应矩阵」，不是 10 万字生成。
3. **把装柜证据做成可发现的 MCP 工具表** — [loadingmcp-mcp](https://github.com/lxxmng/loadingmcp-mcp) 用 `plan_load` / `export_plan` 回传利用率、重心、系固清单，并标明非认证。我们数字仍只走本仓 solver；缺的是 MCP 上的 list / plan / export 形状。
4. **成稿后再跑一岗合规审** — [autonomous-rfp-agent](https://github.com/aniket-work/autonomous-rfp-agent) 的 ComplianceOfficer 审禁语和缺项。我们已有写盘 `scan_forbidden`；缺的是矩阵上的二次审查步，不是用 RAG 填业绩。

**不做：** GeBIZ/自动递交、用托管 200+ 柜型替换 solver、16 类知识库全量 embedding 季更、沙箱/通用 spawn/OTEL。
