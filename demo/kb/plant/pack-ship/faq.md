# 常见问答

- 问：能不能直接报几柜？答：不能手编。设 `PACKING_AGENT_URL` 调 packing-agent，或标 UNSPECIFIED。
- 问：CTU Code 是不是强制法？答：官方标题是 IMO/ILO/UNECE Code of Practice for Packing of Cargo Transport Units (CTU Code, 2014)，作业守则，条款未抽出则 UNSPECIFIED。


问：装箱拼柜默认交付什么？是不是签认件？
答：默认交付「装箱作业单 + 可选 packing-agent 回传摘要」。内部讨论 AI 草稿，不是法定签认件。独有工具 `pack-ship__plan`（数值只走 packing-agent）。可以只聊天，不必成稿。

问：装箱拼柜缺尺寸、单价或条款时怎么写？
答：无来源数字写 [A001] 或 UNSPECIFIED。不编条款号、综合单价、xyz、柜数。用户没给的栏整栏待填。

问：SG 和 CN 口径能混着用吗？
答：默认新加坡工地 SG。CN 标题只在用户点名 CN 或 DUAL 时用。DUAL 必须分栏点名两套门户。权威句见 company/web-portals.md。
