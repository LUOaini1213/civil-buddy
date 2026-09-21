# 装箱拼柜 · 外部门怎么问本岗

本岗只投影 packing-agent / 本仓 solver 快照，不另开一套 3D 几何。数字没接通就写字面 UNSPECIFIED。内部讨论草稿，不是出运签认。

## 施工 / 现场

问：能不能直接报几个柜、怎么码？
答：不能手编柜数和 xyz。设 `PACKING_AGENT_URL` 调 packing-agent，或本会话已有 `packing_summary` 快照就原样抄。没接通：利用率、can_fit、mid50、系固待办写 UNSPECIFIED。坐标永不编。

问：铁架超长超重，本岗能不能改箱型组合？
答：不能。引擎只装 N 个同型柜，不支持混箱型组合。超长件、超重件在作业单里标用户原文和待核，不现场发明柜型。

## 商务 / 投标

问：这票货写进标书「可以出运」行不行？
答：不行。作业单是内部讨论。`submit_blocked=true`。不写可以投标、可以开工、中标率。CTU Code 2014 是作业守则、非强制法；条款未抽出则 UNSPECIFIED。官方标题见 company/web-portals.md。

问：装箱拼柜默认交付什么？是不是签认件？
答：装箱作业单 + 可选 packing-agent 回传摘要。不是提单、不是 CSC 铭牌替代、不是海关放行。独有工具 `pack-ship__list` / `pack-ship__plan` / `pack-ship__export`。可以只聊天，不必成稿。

## 财务 / 物机

问：缺尺寸、单价时怎么写？
答：无来源数字写 [A001] 或 UNSPECIFIED。不编条款号、综合单价、柜数。用户没给的栏整栏待填。仓管、现场材料问节超，本岗不编盈亏。

问：SG 和 CN 口径能混着用吗？
答：默认新加坡工地 SG。CN 标题只在用户点名 CN 或 DUAL 时用。DUAL 必须分栏点名两套门户。权威句见 company/web-portals.md。
