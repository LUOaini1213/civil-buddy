from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class Expert:
    id: str
    name: str
    category: str
    category_name: str
    title: str
    delivers: str
    risk: str
    aliases: tuple[str, ...] = field(default_factory=tuple)
    pipeline: str = "理解任务 → 检索本库与大类库 → 提纲 → 独立成稿 → 自检"
    builtin: bool = True
    enabled: bool = True

    @staticmethod
    def default_pipeline() -> str:
        return "理解任务 → 检索本库与大类库 → 提纲 → 独立成稿 → 自检"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["aliases"] = list(self.aliases)
        return d


CATEGORIES = [
    {"id": "bid", "name": "经营投标", "blurb": "招标解析、响应检查", "builtin": True},
    {"id": "design", "name": "勘察设计", "blurb": "按审图专业拆：建筑结构机电 + 土木专项", "builtin": True},
    {"id": "bim", "name": "BIM", "blurb": "模型协调、碰撞、算量口径、交付", "builtin": True},
    {"id": "planning", "name": "计划", "blurb": "总控、周月计划、资源负荷", "builtin": True},
    {"id": "construction", "name": "施工生产", "blurb": "专项方案、危大、测量、调度", "builtin": True},
    {"id": "hse", "name": "安质环", "blurb": "安全、质量、环保、应急", "builtin": True},
    {"id": "commercial", "name": "商务造价", "blurb": "拆分、签证、分包、索赔、验工", "builtin": True},
    {"id": "procurement", "name": "采购", "blurb": "计划、比价、供应商", "builtin": True},
    {"id": "plant", "name": "物机", "blurb": "设备租赁维保、仓管、现场材料", "builtin": True},
    {"id": "lab", "name": "试验室", "blurb": "配合比、见证取样、台账", "builtin": True},
    {"id": "finance", "name": "财务", "blurb": "核算、资金、税务口径", "builtin": True},
    {"id": "docs", "name": "资料监理", "blurb": "目录闭合、回复草稿", "builtin": True},
    {"id": "hr", "name": "人力", "blurb": "招聘、劳动合同、培训", "builtin": True},
    {"id": "admin", "name": "行政", "blurb": "公文印章、会务后勤", "builtin": True},
    {"id": "it", "name": "IT", "blurb": "权限运维、数据备份、系统需求", "builtin": True},
    {"id": "people", "name": "项目与工人", "blurb": "班前白话、为工友谋幸福", "builtin": True},
]


def E(eid, name, cat, cname, title, delivers, risk, *aliases):
    return Expert(eid, name, cat, cname, title, delivers, risk, aliases)


EXPERTS: list[Expert] = [
    # 经营
    E("bid-parse", "招标解析", "bid", "经营投标", "抽出评分点、工期、资质和必须编制的专项", "评分点表 + 专项触发清单", "low", "招标", "解析招标"),
    E("bid-compliance", "废标检查", "bid", "经营投标", "对照招标响应项列出未响应/易废标点", "响应缺口清单", "low", "废标", "响应检查"),
    E("bid-tech", "技术标", "bid", "经营投标", "按评分点出技术标目录与扩写草稿", "技术标目录/草稿", "low", "技术标", "标书"),
    # 设计：房建审图专业
    E("architecture", "建筑", "design", "勘察设计", "平面功能、防火分区、无障碍、图则口径", "建筑专业说明草稿", "low", "建筑专业", "方案设计"),
    E("structure", "结构", "design", "勘察设计", "结构体系、荷载组合提纲、构件复核清单", "结构计算书提纲", "high", "结构专业", "计算书"),
    E("geotech", "岩土勘察", "design", "勘察设计", "勘察纲要、地基方案比选口径，无地勘不填承载力", "勘察/地基提纲", "high", "岩土", "勘察", "地基"),
    E("plumbing", "给排水", "design", "勘察设计", "给水、排水、消防水量原则，无标高不编管径", "给排水说明草稿", "low", "给水", "排水", "水专业"),
    E("hvac", "暖通", "design", "勘察设计", "冷热源与通风排烟原则，无负荷不选型", "暖通说明草稿", "low", "暖通空调", "通风"),
    E("electrical", "电气", "design", "勘察设计", "供配电、照明、防雷接地原则，无负荷不选变压器", "电气说明草稿", "low", "电气专业", "强电"),
    E("fire-protect", "消防", "design", "勘察设计", "消防系统与疏散原则，不替代消防审图", "消防专篇提纲", "high", "消防设计", "消电"),
    E("steel", "钢结构", "design", "勘察设计", "钢结构体系、连接与防腐涂装提纲", "钢结构说明草稿", "high", "钢构"),
    E("landscape", "园林景观", "design", "勘察设计", "软硬景分区、苗木与铺装原则", "景观说明草稿", "low", "景观", "园林"),
    E("interior", "室内装修", "design", "勘察设计", "饰面、隔墙、吊顶、精装界面与防水节点原则", "室内装修说明/界面表", "low", "精装", "室内", "装修"),
    E("facade", "幕墙", "design", "勘察设计", "幕墙体系、预埋、抗风、气密水密防火提纲，无风压不定量", "幕墙专篇/说明草稿", "high", "外墙", "幕墙工程", "玻璃幕墙"),
    E("intel-weak", "智能化弱电", "design", "勘察设计", "弱电系统清单与桥架原则，不编品牌除非用户指定", "弱电说明草稿", "low", "弱电", "智能化", "综合布线"),
    E("civil-defense", "人防", "design", "勘察设计", "防护单元、口部、防化通风、人防给排水原则，不替代人防审图", "人防专篇提纲", "high", "人防工程", "人防设计"),
    E("hydraulic", "水利", "design", "勘察设计", "堤防、护岸、水闸、泵站提纲，无水文地质不定量", "水利设计提纲", "high", "水利工程", "堤防", "水闸"),
    E("port", "港航", "design", "勘察设计", "码头、航道、防波堤提纲，无水位与地质不定量", "港航设计提纲", "high", "码头", "港口", "航道", "港航"),
    # 设计：土木/市政专项
    E("municipal", "市政道路", "design", "勘察设计", "横断、管线综合、路面结构原则", "市政道路原则稿", "low", "道路", "市政"),
    E("bridge", "桥梁", "design", "勘察设计", "桥型比选、上下部结构提纲，无跨径不定量", "桥梁设计提纲", "high", "桥涵"),
    E("tunnel", "隧道", "design", "勘察设计", "开挖支护、防水与监控量测提纲", "隧道设计提纲", "high", "暗挖", "隧道工程"),
    E("traffic", "交通工程", "design", "勘察设计", "交通组织、标志标线、仿真实验口径", "交通报告骨架", "low", "交通", "导改", "仿真"),
    E("design-coord", "设计统筹", "design", "勘察设计", "图纸会审、专业碰撞、设计变更口径", "会审纪要草稿", "low", "图纸会审", "设计变更", "提资"),
    # BIM
    E("bim-coord", "模型协调", "bim", "BIM", "碰撞检查口径、专业提资接口、问题清单", "碰撞/协调纪要", "low", "碰撞", "BIM协调"),
    E("bim-qto", "模型算量", "bim", "BIM", "从模型出量的口径与过滤规则，不编单价", "算量口径说明", "low", "算量", "QTO"),
    E("bim-deliver", "模型交付", "bim", "BIM", "LOD/交付物清单、命名与拆分规则", "BIM交付清单", "low", "LOD", "BIM交付"),
    # 计划
    E("plan-master", "总控计划", "planning", "计划", "一级网络、关键线路、里程碑", "总进度计划草稿", "low", "总计划", "网络图"),
    E("plan-lookahead", "周月计划", "planning", "计划", "四周滚动、停工条件、交叉作业", "周/月计划草稿", "low", "周计划", "月计划"),
    E("plan-resource", "资源负荷", "planning", "计划", "人机料峰值与错峰口径，无定额不编用量", "资源负荷表头", "low", "资源计划"),
    # 施工
    E("construction", "施工方案", "construction", "施工生产", "专项施工方案讨论提纲，独立走完 11 章", "专项方案-AI草稿", "high", "施工", "专项方案", "方案"),
    E("method-hazard", "危大识别", "construction", "施工生产", "判断是否危大、要否论证，只判定不签发", "危大判定书", "high", "危大", "超危", "论证"),
    E("survey", "测量", "construction", "施工生产", "控制网、放样、复测记录口径，不编坐标除非用户给", "测量方案/记录表", "high", "放样", "复测", "控制点"),
    E("dispatch", "生产调度", "construction", "施工生产", "日报、指令下达、节点跟踪", "调度日报草稿", "low", "调度", "生产调度"),
    # 安质环
    E("safety-brief", "安全交底", "hse", "安质环", "技术交底草稿，给现场技术员", "安全交底草稿", "high", "交底", "安全交底"),
    E("quality", "质量", "hse", "安质环", "检验批、隐蔽验收、通病防治，不给合格结论", "质量检查表", "high", "质检", "质量员", "隐蔽"),
    E("env", "环保文明", "hse", "安质环", "扬尘、弃土、污水、夜间施工口径", "环保文明清单", "low", "环保", "文明施工"),
    E("emergency", "应急", "hse", "安质环", "预案目录、演练记录，联系人待填", "应急预案提纲", "high", "应急预案", "演练"),
    # 造价商务
    E("cost", "造价", "commercial", "商务造价", "工程量拆分与组价口径，无清单则单价 TBD", "工程量拆分表", "low", "造价", "组价", "清单"),
    E("variation", "变更签证", "commercial", "商务造价", "事实、依据、工程量栏，金额待填", "签证单草稿", "low", "签证", "设计变更"),
    E("claim", "索赔调概", "commercial", "商务造价", "索赔意向、证据清单、时限", "索赔意向草稿", "low", "索赔", "调概"),
    E("subcontract", "分包结算", "commercial", "商务造价", "分包验工、扣款、结算口径", "分包结算表头", "low", "分包", "劳务结算"),
    E("interim", "验工计价", "commercial", "商务造价", "对上验工表单口径，无业主确认不编金额", "验工计价草稿", "low", "验工", "计量"),
    # 采购
    E("proc-plan", "采购计划", "procurement", "采购", "甲指/自采划分、提前期、到货节点", "采购计划表", "low", "采购计划"),
    E("proc-compare", "比价询价", "procurement", "采购", "询价口径与比价表，无报价不编价", "比价表草稿", "low", "询价", "比价"),
    E("proc-vendor", "供应商", "procurement", "采购", "准入、考察、短名单口径", "供应商评价表", "low", "供方", "供应商"),
    # 物机
    E("equip", "设备管理", "plant", "物机", "进场验收、租赁、维保、特种设备证件", "设备台账/维保计划", "high", "机械", "设备", "特种设备"),
    E("warehouse", "仓管", "plant", "物机", "入库验收、限额领料、盘点", "收发存台账口径", "low", "仓库", "领料"),
    E("pack-ship", "装箱拼柜", "plant", "物机", "成箱/拼柜作业单：数值只走 packing-agent 工具，本岗不编坐标和柜数", "装箱作业单 + 可选 packing-agent 回传摘要", "low", "装箱", "拼柜", "packing-agent", "集装箱"),
    E("material-site", "现场材料", "plant", "物机", "耗用核算、节超分析口径，无盘点不编盈亏", "材料核算表头", "low", "材料员", "料具"),
    # 试验室
    E("lab-mix", "配合比", "lab", "试验室", "砼/砂浆配合比选定口径，无试验数据不给施工配比", "配比报告提纲", "high", "施工配合比", "配比"),
    E("lab-sample", "见证取样", "lab", "试验室", "原材料取样、送检、不合格报告升级", "取样送检清单", "high", "取样", "送检", "见证"),
    E("lab-record", "试验台账", "lab", "试验室", "记录、报告编号、仪器检定台账", "试验台账骨架", "low", "试验资料"),
    # 财务
    E("finance-book", "核算", "finance", "财务", "科目口径、报销审核清单，不编账套分录细节", "核算检查表", "low", "会计", "报销"),
    E("finance-fund", "资金", "finance", "财务", "资金计划、收支平衡口径", "资金计划草稿", "low", "资金计划", "现金流"),
    E("finance-tax", "税务", "finance", "财务", "税种清单与申报节点，不给出具体筹划方案当税务意见", "税务日历/检查表", "low", "税务", "发票"),
    # 资料
    E("supervision", "资料监理", "docs", "资料监理", "验收资料目录与监理通知回复草稿", "资料目录 / 回复草稿", "low", "资料", "监理", "验收"),
    # 人力
    E("hr-recruit", "招聘", "hr", "人力", "岗位说明书、面试提纲，不编薪资带宽除非用户给", "招聘简报", "low", "招聘", "面试"),
    E("hr-labor", "劳动关系", "hr", "人力", "劳动合同/劳务协议检查清单，普法不诉讼", "合同检查表", "low", "劳动合同", "劳务"),
    E("hr-train", "培训", "hr", "人力", "三级安全教育与技能培训计划骨架", "培训计划草稿", "low", "培训", "三级教育"),
    # 行政
    E("admin-doc", "公文印章", "admin", "行政", "请示、纪要、用印审批口径", "公文草稿", "low", "公文", "印章", "用印"),
    E("admin-office", "会务后勤", "admin", "行政", "会议、接待、差旅、办公物资", "会务/后勤清单", "low", "行政", "后勤", "会议"),
    # IT
    E("it-ops", "运维权限", "it", "IT", "账号、权限、故障升级路径", "运维手册提纲", "low", "运维", "权限", "账号"),
    E("it-data", "数据备份", "it", "IT", "备份策略、恢复演练口径", "备份策略草稿", "low", "备份", "数据安全"),
    E("it-app", "系统需求", "it", "IT", "业务系统需求说明书骨架", "需求说明书草稿", "low", "信息化", "需求"),
    # 工人
    E("worker-brief", "工友白话", "people", "项目与工人", "3 分钟班前口播稿，给一线工人", "班前白话稿", "low", "工人", "白话", "班前"),
    E("pm-daily", "项目日报", "people", "项目与工人", "形象进度、人机料、安全质量记事", "项目日报草稿", "low", "日报", "工程日志"),
]
