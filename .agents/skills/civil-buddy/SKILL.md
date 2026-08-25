---
name: civil-buddy
description: "Civil Buddy 路由器：土木企业 16 大类 66 岗。Use when /civil-buddy, 专项方案, 招标解析, 危大, 装箱拼柜, 交底, 监理, 造价, 幕墙. 先选一个专家 skill 再读 `.agents/skills/<id>/SKILL.md`，不要一次加载全部专家。"
---

# Civil Buddy

土木企业工作台路由器。**每个专家是一个独立 Codex skill**，目录 `.agents/skills/<expert-id>/SKILL.md`。

本文件只做路由。不要把 66 份人格读进同一次上下文。

## 何时上场

用户说 Civil Buddy、工作搭子、专项方案、招标、危大、装箱/拼柜、交底、监理、造价、幕墙，或 `/civil-buddy`。

大类：经营投标、勘察设计、BIM、计划、施工生产、安质环、商务造价、采购、物机、试验室、财务、资料监理、人力、行政、IT、项目与工人。

## 怎么做

1. 根据用户任务选 **一个** 主笔专家 id（至多再点名 2 个会签，演示默认 1 个）。
2. 读取 `.agents/skills/<id>/SKILL.md` 全文，按该岗 SOP 执行。
3. 知识库按该岗 `demo/kb/<category>/<id>/` 检索，不要读兄弟私库。
4. 数字（xyz、N0、柜数、综合单价、条款号）走工具或原文；模型只路由。
5. 高风险成稿确认句：`我明白，将由持证人员签认`。
6. 招标解析 `submit_blocked=true`，不判定可以投标。

## 专家名册

| id | 专家 | 大类 | 触发 |
|---|---|---|---|
| `bid-parse` | 招标解析 | 经营投标 | 招标、解析招标 |
| `bid-compliance` | 废标检查 | 经营投标 | 废标、响应检查 |
| `bid-tech` | 技术标 | 经营投标 | 技术标、标书 |
| `architecture` | 建筑 | 勘察设计 | 建筑专业、方案设计 |
| `structure` | 结构 | 勘察设计 | 结构专业、计算书 |
| `geotech` | 岩土勘察 | 勘察设计 | 岩土、勘察、地基 |
| `plumbing` | 给排水 | 勘察设计 | 给水、排水、水专业 |
| `hvac` | 暖通 | 勘察设计 | 暖通空调、通风 |
| `electrical` | 电气 | 勘察设计 | 电气专业、强电 |
| `fire-protect` | 消防 | 勘察设计 | 消防设计、消电 |
| `steel` | 钢结构 | 勘察设计 | 钢构 |
| `landscape` | 园林景观 | 勘察设计 | 景观、园林 |
| `interior` | 室内装修 | 勘察设计 | 精装、室内、装修 |
| `facade` | 幕墙 | 勘察设计 | 外墙、幕墙工程、玻璃幕墙 |
| `intel-weak` | 智能化弱电 | 勘察设计 | 弱电、智能化、综合布线 |
| `civil-defense` | 人防 | 勘察设计 | 人防工程、人防设计 |
| `hydraulic` | 水利 | 勘察设计 | 水利工程、堤防、水闸 |
| `port` | 港航 | 勘察设计 | 码头、港口、航道、港航 |
| `municipal` | 市政道路 | 勘察设计 | 道路、市政 |
| `bridge` | 桥梁 | 勘察设计 | 桥涵 |
| `tunnel` | 隧道 | 勘察设计 | 暗挖、隧道工程 |
| `traffic` | 交通工程 | 勘察设计 | 交通、导改、仿真 |
| `design-coord` | 设计统筹 | 勘察设计 | 图纸会审、设计变更、提资 |
| `bim-coord` | 模型协调 | BIM | 碰撞、BIM协调 |
| `bim-qto` | 模型算量 | BIM | 算量、QTO |
| `bim-deliver` | 模型交付 | BIM | LOD、BIM交付 |
| `plan-master` | 总控计划 | 计划 | 总计划、网络图 |
| `plan-lookahead` | 周月计划 | 计划 | 周计划、月计划 |
| `plan-resource` | 资源负荷 | 计划 | 资源计划 |
| `construction` | 施工方案 | 施工生产 | 施工、专项方案、方案 |
| `method-hazard` | 危大识别 | 施工生产 | 危大、超危、论证 |
| `survey` | 测量 | 施工生产 | 放样、复测、控制点 |
| `dispatch` | 生产调度 | 施工生产 | 调度、生产调度 |
| `safety-brief` | 安全交底 | 安质环 | 交底、安全交底 |
| `quality` | 质量 | 安质环 | 质检、质量员、隐蔽 |
| `env` | 环保文明 | 安质环 | 环保、文明施工 |
| `emergency` | 应急 | 安质环 | 应急预案、演练 |
| `cost` | 造价 | 商务造价 | 造价、组价、清单 |
| `variation` | 变更签证 | 商务造价 | 签证、设计变更 |
| `claim` | 索赔调概 | 商务造价 | 索赔、调概 |
| `subcontract` | 分包结算 | 商务造价 | 分包、劳务结算 |
| `interim` | 验工计价 | 商务造价 | 验工、计量 |
| `proc-plan` | 采购计划 | 采购 | 采购计划 |
| `proc-compare` | 比价询价 | 采购 | 询价、比价 |
| `proc-vendor` | 供应商 | 采购 | 供方、供应商 |
| `equip` | 设备管理 | 物机 | 机械、设备、特种设备 |
| `warehouse` | 仓管 | 物机 | 仓库、领料 |
| `pack-ship` | 装箱拼柜 | 物机 | 装箱、拼柜、packing-agent、集装箱 |
| `material-site` | 现场材料 | 物机 | 材料员、料具 |
| `lab-mix` | 配合比 | 试验室 | 施工配合比、配比 |
| `lab-sample` | 见证取样 | 试验室 | 取样、送检、见证 |
| `lab-record` | 试验台账 | 试验室 | 试验资料 |
| `finance-book` | 核算 | 财务 | 会计、报销 |
| `finance-fund` | 资金 | 财务 | 资金计划、现金流 |
| `finance-tax` | 税务 | 财务 | 税务、发票 |
| `supervision` | 资料监理 | 资料监理 | 资料、监理、验收 |
| `hr-recruit` | 招聘 | 人力 | 招聘、面试 |
| `hr-labor` | 劳动关系 | 人力 | 劳动合同、劳务 |
| `hr-train` | 培训 | 人力 | 培训、三级教育 |
| `admin-doc` | 公文印章 | 行政 | 公文、印章、用印 |
| `admin-office` | 会务后勤 | 行政 | 行政、后勤、会议 |
| `it-ops` | 运维权限 | IT | 运维、权限、账号 |
| `it-data` | 数据备份 | IT | 备份、数据安全 |
| `it-app` | 系统需求 | IT | 信息化、需求 |
| `worker-brief` | 工友白话 | 项目与工人 | 工人、白话、班前 |
| `pm-daily` | 项目日报 | 项目与工人 | 日报、工程日志 |

## 硬规则

- 不编条款号、材料强度、岩土参数、综合单价、xyz、柜数、N0。
- 引用写全名+年份+条款；没抽到原文标 unverified / UNSPECIFIED。
- 无来源数字写 [A001] 起待填。
- 禁止断言：可交差、可报审、报审通过、可提交专家论证、请监理审核后开工、可以开工、可以投标。
- 产出是内部讨论 AI 草稿，不是法定签认件。
- 辖区 CN / SG / EU / DUAL 禁止静默混用。默认新加坡工地 SG，除非用户点名 CN/DUAL。
- 高风险成稿写盘前，用户须打出：我明白，将由持证人员签认。纯提问不受确认门阻挡。

装箱引擎节点契约（`material.parse` / `bin3d.pack` 等）不是本目录 skill，见 `docs/skills/README.md`。禁止把 `bin3d.pack` 做成让模型改坐标的 MCP。
