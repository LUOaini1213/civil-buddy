# GitHub 对照后的改进方向（2026-08-17 联网）

本轮拉取了 MCP / 投标 / 装柜三类公开仓。详细出处见会话 scratch 的 `github-sources.md`。Horizon **B（抽取并表）已做**，不再当缺口。

1. **给 MCP 找一个真宿主** — 服务端已有 tools/resources/prompts，没有客户端去读 `kb://` 或点 `civil.bid.parse`。[Copilot CLI #1518](https://github.com/github/copilot-cli/issues/1518) 说明大宿主也常只接 tools。[knowledge-base-mcp-server](https://github.com/jeanibarz/knowledge-base-mcp-server) 把「按意思检索」和「按文件浏览」拆开。分页/订阅仍按 horizon **D 延期**。
2. **招标文件进矩阵，而不是加长写标** — [OpenBidKit 易标](https://github.com/FB208/OpenBidKit_Yibiao) 有 MinerU/本地解析和废标/查重工作区。主线 C 已接表格/多文件节选进矩阵（2026-08-17）。不是 10 万字生成。
3. **把装柜证据做成可发现的 MCP 工具表** ✅ — `pack-ship__list` / `plan` / `export`。数字只抄本仓 solver；未接通 `UNSPECIFIED`。
4. **成稿后再跑一岗合规审** ✅ — `tender.review.v1` 审禁语和缺项。不填业绩、不改 `can_fit`。
5. **沙箱 + OTEL 大盘** ✅ — 应用层写根/密钥/通用 spawn 策略；`GET /api/otel/dashboard` 读真 span。不是内核 jail，也不是 Grafana 必选项。

**不做：** GeBIZ/自动递交、用托管 200+ 柜型替换 solver、16 类知识库全量 embedding 季更、内核 Landlock/Seatbelt、以 Grafana/Jaeger 为唯一大盘。
