---
name: pack-ship
description: "装箱拼柜（物机）：成箱/拼柜作业单：数值只走 packing-agent 工具，本岗不编坐标和柜数。交付装箱作业单 + 可选 packing-agent 回传摘要。适用于装箱、拼柜、packing-agent、集装箱。内部草稿。"
metadata:
  category: "plant"
  category_name: "物机"
  title: "成箱/拼柜作业单：数值只走 packing-agent 工具，本岗不编坐标和柜数"
  delivers: "装箱作业单 + 可选 packing-agent 回传摘要"
  risk: "low"
  aliases: "装箱,拼柜,packing-agent,集装箱"
---

# 装箱拼柜

Civil Buddy 的物机专业技能；程序记忆（Skill / SOP），不是用户画像或规范全文。
成箱/拼柜作业单：数值只走 packing-agent 工具，本岗不编坐标和柜数。默认交付：装箱作业单 + 可选 packing-agent 回传摘要。风险：low。

可以只聊天。只有用户本轮要求成稿才调用写入工具；缺少资料可列空栏骨架，不能把待核输入变成事实。

## 成稿资料

按本次任务核对以下资料；缺项逐项标 [A001] / UNSPECIFIED，招标未载内容标「招标未写」。

- 辖区（未提供则UNSPECIFIED；多个对象单独归属）
- 用户物料尺寸、重量、数量原文
- 柜型和约束来源
- packing solver快照及来源
- 连接状态和can_fit结果
- 系固待办与作业单范围

## 专属步骤

1. 检查solver快照可用性；调用 `pack-ship__health`。
2. 列出装箱工具；调用 `pack-ship__list`。
3. 投影装柜证据，不重算坐标；调用 `pack-ship__plan`。
4. 导出同源证据与失败缺项；调用 `pack-ship__export`。

## 输出结构

交付完整 Markdown 草稿及可打开的 Word；正文有表格时可导出 Excel。文首保留内部草稿声明，签认栏由持证人员填写。

1. 用户物料
2. solver状态
3. 装柜证据投影
4. 系固待办
5. 来源标题待核
6. 缺项与失败边界

专业表格至少表达以下字段（缺项保留空栏，不能串用其他对象的值）：

- 装柜证据：字段｜solver原值｜来源｜连接状态｜待核项

## 验收

- can_fit=false保持失败，断线数值全为字面UNSPECIFIED
- plan与export必须同一solver来源，禁止重写xyz或柜数
- 实际生成文件须能打开；用户已给字段进入对应正文或表格，不能仅在附录重复用户原文。

## 能力边界

- 当前工具只投影已有solver快照，不在此处重跑packing引擎或编坐标
- 本岗专属工具不能借给兄弟岗；文书起草工具不等于工程求解器。

## 按需读取

- 需要完整专业细节时读 `demo/kb/plant/pack-ship/outline.md`；其中历史规范标题不是已经核实的现行依据。
- 检索仅限本岗 `demo/kb/plant/pack-ship/` 与大类 `demo/kb/plant/_shared/`。
- 公司规则：`demo/kb/company/hard-rules.md`；法规引用打开对应官方原文再核对版本和条款。

## 共同边界

- 不编条款号、材料强度、岩土参数、综合单价、xyz、柜数、N0。
- 引用写全名+年份+条款；没抽到原文标 unverified / UNSPECIFIED。
- 无来源数字写 [A001] 起待填。
- 禁止断言：可交差、可报审、报审通过、可提交专家论证、请监理审核后开工、可以开工、可以投标。
- 产出是内部讨论 AI 草稿，不是法定签认件。
- 辖区 CN / SG / EU / DUAL 禁止静默混用。以本次明确地区或会话已确认地区为准；未提供则 UNSPECIFIED，不默认国家。DUAL 的依据和接口按明确地区分栏。
- 高风险成稿写盘前，用户须打出：我明白，将由持证人员签认。纯提问不受确认门阻挡。
