# 专业工作台架构研究（历史摘录）

本记录保留本地主目录 Excel 副本中尚未进入功能分支的“专业工作台架构”工作表。其记录日期写为 2026-09-22，晚于本次审查日 2026-09-21，保留原文待核。表中的端口、产品现状、功能范围和第三方研究均是当时笔记，不能替代当前功能说明或验收。

当前已接入能力见 [工程工作台](engineering-workbench.md)、[施工排程](planning-workbench.md) 和 [物流工作台](logistics-workbench.md)。本摘录不覆盖开源清单的最新排程记录。

| 层 | 常见专业工作台怎么做 | 本仓 Civil Buddy 现状 | 要不要跟 |
| --- | --- | --- | --- |
| 前台 / 后台 | 员工作业前台与 Admin 配置后台拆开（Adobe/飞书/钉钉/Salesforce Setup） | 本机 8765 作业台 + 无独立企业 Admin（Key 在 demo/.env，无租户计费） | 比赛/单机不必做 Admin Console；多用户再拆 |
| 管理型 vs 任务型 | 高管看 KPI 合计；一线走缩短待办与动作 | 任务型：点岗→问/写一份；无项目部 KPI 大盘 | 保持任务型；不要做成集团驾驶舱 |
| 角色裁剪 | 同一模块按角色显隐；首屏 5–9 块 | 66 岗左侧点名 = 岗位裁剪；不是组织 RBAC | 岗 skill 已够；不要上钉钉式多门户 |
| 标准模块 | 帮助、核心数据、快捷入口、待办、通知 | 空态卡+示例任务+/pack /bid /safety；HITL 审批卡=待办 | 已有快捷与审批；统一待办中心非主链 |
| 页面组合 | 微前端 Module Federation 或 portlet 拼页 | 单体 frontend/demo static + 网关 :8000 装箱 3D | 不要上微前端；两入口已够 |
| 权限 | RBAC 角色范围；SSO SAML/OIDC | 本机单用户 + 高风险确认句；MCP 按 pack/expert 裁工具 | SSO 非目标；exclusive 工具鉴权已有 |
| 施工垂直 | 云-管-边-端；劳务/进度/安全/质量/机械/物资 | 起草搭子，不接安全帽/无人机物联网 | 不做智慧工地 IoT 平台 |
| 招投标垂直 | 交易/公共服务/行政监督三分离；CA 加密 | 主线 C：解析→矩阵→handoff；submit_blocked；不代交 GeBIZ | 对；不要做法定交易平台 |
| 制造垂直 | ISA-95 L3 MES 接 ERP 与 PLC | 无 | 不做 MES |
| 客服垂直 | Salesforce Console 多标签客户上下文 | 会话 session_id 当标段档案 | 可借鉴多标签，不要做成 CRM |
| 和 Codex 对照 | Host 冻 harness；UI 是客户端 | TUI/exec/app/MCP/serve 同一循环 | 保持；不换皮复制 Codex |
| 资料 | 人人都是产品经理/Ant Design 工作台研究/飞书钉钉Adobe 文档/电子招标投标办法/T-CAIEC 征求意见稿 | 本表 2026-09-22 深研摘录 | 征求意见稿条款用「宜」，非强制 |
