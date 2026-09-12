"""IT post drafts from explicitly supplied, sanitized facts; no system operations."""

from __future__ import annotations

import html
import re
import unicodedata
from collections.abc import Sequence

from packing_assistant.jurisdiction import infer_jurisdiction
from packing_assistant.office_job import tables_from_md

_MISSING = "UNSPECIFIED（待填）"
_REDACTED = "[敏感内容已省略]"
_TOOLS = {"it-ops": "it-ops__runbook", "it-data": "it-data__backup", "it-app": "it-app__srs"}
_FIELDS = {
    "system": ("系统名称", "系统名", "平台名称", "系统", "平台"),
    "owner": ("数据负责人", "数据主人", "业务负责人", "负责人"),
    "scope": ("适用范围", "业务范围", "范围"),
    "role": ("使用人岗位", "用户角色", "岗位", "角色"),
    "permission": ("申请权限", "权限范围", "权限", "动作"),
    "application": ("申请事项", "变更事项"),
    "requester": ("申请人",), "approver": ("业务审批人", "审批人"),
    "start": ("拟生效时间", "生效时间", "开始时间"),
    "expiry": ("到期时间", "到期日", "收回时间", "截止时间"),
    "withdrawer": ("收回人",), "ticket": ("变更工单号", "工单号"),
    "window": ("变更窗口", "维护窗口", "窗口"),
    "rollback": ("回退步骤", "回退方案"), "review": ("权限复核周期", "复核周期"),
    "severity": ("故障级别", "故障分级", "严重程度"),
    "impact": ("故障现象", "影响范围", "影响面"),
    "escalation": ("故障升级路径", "升级路径", "升级链"),
    "contact": ("值班联系人", "联系人"), "threshold": ("升级条件", "升级时限"),
    "data": ("数据对象", "备份数据", "数据范围", "数据"),
    "classification": ("数据分级", "系统分级", "重要级别", "分级"),
    "rpo": ("RPO目标", "RPO"), "rto": ("RTO目标", "RTO"),
    "cycle": ("备份周期", "备份频率"), "method": ("备份方式", "备份方法"),
    "media": ("备份介质", "介质"), "backup_window": ("备份窗口",),
    "retention": ("数据保留期限", "保留期限", "保存期限"),
    "location": ("存放位置类型", "存放类型", "备份位置类型"),
    "encryption": ("加密方案", "是否加密"), "drill_cycle": ("演练周期",),
    "drill_object": ("演练对象",), "drill_date": ("演练时间", "演练日期"),
    "isolation": ("隔离环境", "是否隔离"), "business_check": ("业务拉起记录",),
    "integrity": ("完整性检查记录", "完整性检查"), "checker": ("完整性检查人", "检查人"),
    "duration": ("实际恢复时长", "实际耗时"), "evidence": ("演练记录", "演练证据", "证据名称"),
    "failure": ("失败原因",), "handoff": ("移交责任人", "移交要求"),
    "background": ("当前现状", "业务现状", "现状", "背景"),
    "goal": ("建设目标", "业务目标", "目标"),
    "builder": ("建设方", "使用单位"), "site": ("使用现场", "使用场景"),
    "excluded": ("范围外", "排除范围", "不含范围"),
    "process": ("现有流程", "当前流程"), "target_process": ("目标流程", "拟议流程", "流程"),
    "scene": ("业务场景", "场景"), "feature": ("功能需求", "需求", "功能"),
    "object": ("操作对象", "业务对象", "对象"), "rule": ("业务规则", "规则"),
    "exception": ("异常处理", "异常"), "acceptance": ("验收标准", "验收行为", "验收"),
    "concurrency": ("并发目标", "并发"), "offline": ("离线需求", "离线"),
    "source": ("主数据来源", "数据来源"), "peer": ("对端系统", "接口系统"),
    "direction": ("接口方向", "方向"), "retry": ("失败重试", "重试规则"),
    "priority": ("优先级",), "delivery": ("期望交付时间", "期望时间"),
}
_ALIASES = {alias.casefold(): key for key, labels in _FIELDS.items() for alias in labels}
_LABEL = re.compile(
    r"(?<![A-Za-z0-9_])(" + "|".join(sorted(map(re.escape, _ALIASES), key=len, reverse=True))
    + r")\s*[:：=]\s*", re.IGNORECASE
)
_SECRET_NAME = (
    r"(?:api[ _-]?key|access[ _-]?(?:key(?:[ _-]?id)?|token)|client[ _-]?secret|"
    r"private[ _-]?key|secret(?:[ _-]?key)?|authorization|password|passwd|pwd|token|"
    r"connection[ _-]?string|user(?:name|[ _-]?id)?|dsn|endpoint|url|"
    r"密码|口令|密钥|令牌|私钥|连接串|接口地址|真实账号|登录账号|用户名|账号|许可号)"
)
_SECRET_START = re.compile(r"(?<![A-Za-z0-9_])" + _SECRET_NAME + r"[\"']?(?:\s*(?:[:：=]|为|是)\s*|[ \t]+(?=[^ \t|]))", re.I)
_QUOTED_SECRET = re.compile(
    _SECRET_START.pattern + r"(?:\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*')", re.I | re.S
)
_PRIVATE_KEY = re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?(?:-----END [A-Z0-9 ]*PRIVATE KEY-----|\Z)", re.S | re.I)
_URL = re.compile(r"\b[a-z][a-z0-9+.-]*://[^\s<>\"'，；]+", re.I)
_TOKEN = re.compile(
    r"\b(?:Bearer|Basic)\s+[^\s,;，；]+|\bsk-[A-Za-z0-9_-]{8,}|"
    r"\b(?:gh[pousr]_|github_pat_|hf_|xox[baprs]-)[A-Za-z0-9_-]{8,}|"
    r"\bAKIA[A-Z0-9]{16}\b|\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", re.I
)
_ADDRESS = re.compile(
    r"\b(?:\d{1,3}\.){3}\d{1,3}(?:/\d{1,2})?|"
    r"\b[^\s:@，；]+:[^\s@，；]+@[^\s，；]+|"
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}|"
    r"\b(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}(?::\d+)?/[^\s，；]+"
)


def _redact(text: str) -> str:
    """Discard credential values before parsing, including quoted multiline values.

    An unquoted credential assignment discards the rest of its physical line:
    guessing where a password ends could retain part of it as another field.
    Safe fields on subsequent lines remain available.
    """
    value = unicodedata.normalize("NFKC", html.unescape(text or ""))
    value = _PRIVATE_KEY.sub("\n" + _REDACTED + "\n", value)
    value = _QUOTED_SECRET.sub("\n" + _REDACTED + "\n", value)
    value = _URL.sub(_REDACTED, value)
    value = _TOKEN.sub(_REDACTED, value)
    value = _ADDRESS.sub(_REDACTED, value)
    lines = []
    for line in value.splitlines():
        match = _SECRET_START.search(line)
        lines.append(line[:match.start()].rstrip(" \t,;，；\"'") if match else line)
    return "\n".join(lines)


def _value(value: str) -> str:
    return value.strip(" \t\r\n,;，；。") or _MISSING


class _Facts:
    def __init__(self, text: str):
        self.text = _redact(text)
        self.entries: list[tuple[str, str]] = []
        lines = self.text.splitlines()
        index = 0
        while index < len(lines):
            line = lines[index]
            if line.lstrip().startswith("|"):
                end = index + 1
                while end < len(lines) and lines[end].lstrip().startswith("|"):
                    end += 1
                self._table_entries("\n".join(lines[index:end]))
                index = end
                continue
            index += 1
            matches = list(_LABEL.finditer(line))
            for field_index, match in enumerate(matches):
                end = matches[field_index + 1].start() if field_index + 1 < len(matches) else len(line)
                self.entries.append((_ALIASES[match.group(1).casefold()], _value(line[match.end():end])))
            if not matches:
                # Recognize role-led requirement notes without turning arbitrary prose into facts.
                for sentence in re.split(r"[;；]", line):
                    match = re.match(
                        r"\s*(企业管理员|项目经理|施工员|劳务员|安全员|质量员|资料员|商务|财务|工人|监理|业主)"
                        r"(?:可以|需要|负责|应当|应|可|能)?\s*((?:提交|审批|录入|查询|查看|导出|登记|填报|上传|整改|审核).+)", sentence
                    )
                    if match:
                        self.entries.extend((("role", match.group(1)), ("feature", _value(match.group(2)))))

    def _table_entries(self, markdown: str) -> None:
        for _, rows in tables_from_md(markdown):
            headers = [_ALIASES.get(cell.casefold()) for cell in rows[0]]
            if any(headers):
                for row_index, row in enumerate(rows[1:]):
                    if len(row) != len(headers):
                        continue
                    if row_index:
                        self.entries.append(("_record", "reset" if "system" in headers else "inherit"))
                    # Only allowlisted columns are read, never credential columns.
                    for key, value in zip(headers, row):
                        if key:
                            self.entries.append((key, _value(_redact(value))))
            else:
                for row in rows[1:]:
                    key = _ALIASES.get(row[0].casefold()) if row else None
                    if key and len(row) == 2:
                        self.entries.append((key, _value(_redact(row[1]))))

    def get(self, key: str, default: str = _MISSING) -> str:
        return next((value for name, value in self.entries if name == key), default)

    def records(self, split: Sequence[str]) -> list[dict[str, str]]:
        records: list[dict[str, str]] = []
        current: dict[str, str] = {}
        for key, value in self.entries:
            if key == "_record":
                if current:
                    records.append(current)
                current = {"system": current["system"]} if value == "inherit" and "system" in current else {}
                continue
            if key in split and key in current:
                records.append(current)
                inherited = ("system", "role") if key == "feature" else ("system",)
                current = {name: current[name] for name in inherited if key != "system" and name in current}
            current[key] = "；".join(filter(None, (current.get(key), value)))
        if current:
            records.append(current)
        return records or [{}]


def _cell(value: str) -> str:
    return html.escape(value, quote=False).replace("|", "&#124;").replace("\n", " ").replace("\r", " ")


def _table(title: str, headers: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    lines = [f"## {title}", "", "| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    lines.extend("| " + " | ".join(_cell(value) for value in row) + " |" for row in rows)
    return "\n".join(lines) + "\n\n"


def _fields(title: str, rows: Sequence[Sequence[str]]) -> str:
    return _table(title, ("栏位", "用户提供/待填"), rows)


def _header(title: str, facts: _Facts) -> str:
    return (
        f"# {title}（AI 草稿 · 内部讨论）\n\n"
        "> 草稿声明：仅供内部核对，不是批准制度、测评结论或上线批准；本稿未执行权限变更、备份或恢复。\n\n"
        f"- 辖区：{infer_jurisdiction(facts.text)}\n"
        "- 已填事实均来自用户输入，未核验；方案、目标和需求为拟议内容，缺项为 UNSPECIFIED。\n"
        "- 凭据与接口实地址不纳入草稿，不附输入原文；签认和验收结果由责任人填写。\n\n"
    )


def _ops(facts: _Facts) -> str:
    records = facts.records(("system", "role"))
    out = _header("账号与权限运维手册提纲", facts)
    out += _table("系统与权限申请矩阵", ("系统", "适用范围", "岗位角色", "拟申请动作/权限", "业务确认"), [
        (r.get("system", _MISSING), r.get("scope", _MISSING), r.get("role", _MISSING), r.get("permission", _MISSING), "") for r in records
    ])
    out += _table("账号生命周期（拟议流程）", ("触发", "拟处理", "责任角色", "执行记录"), [
        ("入职/外部协作", "申请、业务审批、最小权限开通；外部角色注明到期日", _MISSING, ""),
        ("调岗/临时提权", "复核原权限，记录事由、窗口及收回人", _MISSING, ""),
        ("长期未使用/离职", "按公司确认周期冻结，离职关闭并留痕", _MISSING, ""),
    ])
    out += _fields("权限变更与留痕", [
        ("申请事项", facts.get("application")), ("申请人", facts.get("requester")),
        ("拟审批人", facts.get("approver")), ("拟生效时间", facts.get("start")),
        ("到期/收回时间", facts.get("expiry")), ("收回人", facts.get("withdrawer")),
        ("工单号（用户提供）", facts.get("ticket")), ("审批签认", ""), ("实际生效记录", ""),
    ])
    out += _table("故障分级与升级路径", ("系统", "故障级别/影响", "用户指定升级路径", "联系人", "升级条件/时限"), [
        (r.get("system", _MISSING), "；".join(filter(None, (r.get("severity"), r.get("impact")))) or _MISSING,
         r.get("escalation", _MISSING), r.get("contact", _MISSING), r.get("threshold", _MISSING)) for r in records
    ])
    out += "待业务确认的升级流程：一线记录现象与影响 → 二线运维 → 三线厂商/开发；安全事件按企业应急流程升级。联系人和时限不默认填入。\n\n"
    out += _fields("变更窗口与检查", [
        ("变更窗口", facts.get("window")), ("回退步骤", facts.get("rollback")),
        ("权限复核周期", facts.get("review")), ("特权角色及外部角色到期清单", _MISSING),
        ("最近一次故障时间线", _MISSING), ("核对签认", ""),
    ])
    out += "权限原则（拟议）：一人一号、办公与特权角色分离、禁止共用管理员；仅授予完成任务所需权限。导出、批量删除等敏感动作单独审批。默认口令须更换，管理端采用适当的多因素鉴别，具体措施待确认；本稿不登记凭据。\n"
    return out


def _data(facts: _Facts) -> str:
    records = facts.records(("system",))
    out = _header("数据备份与恢复策略草稿", facts)
    out += _table("系统与数据分级", ("系统", "数据对象", "用户指定分级", "数据负责人"), [
        tuple(r.get(key, _MISSING) for key in ("system", "data", "classification", "owner")) for r in records
    ])
    out += _table("业务恢复目标（拟议，非实测承诺）", ("系统", "RPO 目标", "RTO 目标", "业务确认"), [
        (r.get("system", _MISSING), r.get("rpo", _MISSING), r.get("rto", _MISSING), "") for r in records
    ])
    out += "RPO 是业务可容忍的数据丢失时间；RTO 是业务可容忍的中断时间。目标逐系统由业务确认，不用目标代替实际恢复时长。\n\n"
    out += _table("备份计划（拟议，未执行）", ("系统", "方式", "周期", "介质", "窗口", "保留期限"), [
        tuple(r.get(key, _MISSING) for key in ("system", "method", "cycle", "media", "backup_window", "retention")) for r in records
    ])
    out += _table("存放与保护", ("系统", "位置类型（不含实地址）", "加密方案", "演练周期", "移交责任/要求"), [
        tuple(r.get(key, _MISSING) for key in ("system", "location", "encryption", "drill_cycle", "handoff")) for r in records
    ])
    out += _table("恢复演练记录（用户提供，未核验）", ("系统", "演练对象", "日期", "隔离环境", "业务拉起记录", "实际恢复时长"), [
        tuple(r.get(key, _MISSING) for key in ("system", "drill_object", "drill_date", "isolation", "business_check", "duration")) for r in records
    ])
    out += _table("恢复证据与核对", ("系统", "完整性检查记录", "检查人", "证据名称", "失败原因", "核对签认"), [
        tuple(r.get(key, _MISSING) for key in ("system", "integrity", "checker", "evidence", "failure")) + ("",) for r in records
    ])
    out += (
        "无原始记录时，演练记录、成功恢复证据和实际时长均待填，不能据本策略认定备份或恢复已经完成。\n\n"
        "拟议检查：生产与备份隔离，备份角色最小权限；另行核对副本、介质、异地存放和恢复可用性。"
        "个人网盘、聊天或邮件附件不自动视为正式备份。现场原始资料及项目收尾移交范围由数据负责人确认。"
        "适用制度、标准及条款待核，不在本稿中作保护等级或合规结论。\n"
    )
    return out


def _app(facts: _Facts) -> str:
    records = facts.records(("system", "role", "feature"))
    out = _header("施工企业业务系统需求说明书草稿", facts)
    out += _fields("现状、目标与范围", [
        ("系统", facts.get("system")), ("建设方", facts.get("builder")), ("使用现场", facts.get("site")),
        ("用户描述现状", facts.get("background")), ("拟议目标", facts.get("goal")),
        ("范围", facts.get("scope")), ("范围外", facts.get("excluded")),
    ])
    out += _fields("业务流程", [("现有流程（用户描述）", facts.get("process")), ("拟议目标流程", facts.get("target_process"))])
    out += _table("角色与功能需求（逐项待确认）", ("系统", "角色", "场景", "动作/功能", "对象", "业务规则", "异常处理"), [
        tuple(r.get(key, _MISSING) for key in ("system", "role", "scene", "feature", "object", "rule", "exception")) for r in records
    ])
    out += _table("可观察验收标准（拟议，未验收）", ("角色", "功能", "用户提供的验收标准", "优先级", "验收结果"), [
        tuple(r.get(key, _MISSING) for key in ("role", "feature", "acceptance", "priority")) + ("",) for r in records
    ])
    out += _fields("非功能与数据来源", [
        ("并发目标（待评估）", facts.get("concurrency")), ("保存期限", facts.get("retention")),
        ("离线需求", facts.get("offline")), ("主数据来源", facts.get("source")),
        ("期望交付时间（用户期望，未承诺）", facts.get("delivery")),
    ])
    out += _table("接口边界（仅系统名称）", ("对端系统", "方向", "主数据来源", "失败重试", "接口文档核对"), [
        (facts.get("peer"), facts.get("direction"), facts.get("source"), facts.get("retry"), ""),
    ])
    out += _table("交接检查", ("事项", "接口岗位/责任", "证据", "核对签认"), [
        ("角色最小权限、审计及权限移交", "it-ops / 业务负责人待指定", _MISSING, ""),
        ("恢复目标、备份与恢复演练", "it-data / 数据负责人待指定", _MISSING, ""),
        ("培训、使用说明与验收记录", "项目责任人待指定", _MISSING, ""),
    ])
    out += "未指定模块不默认纳入范围。验收应核对可观察行为与按角色拒绝访问等边界；没有证据时不填通过。需求与时间仅供评估，不形成交付、报价或上线承诺；弱电点位及桥架另交对应设计岗。\n"
    return out


def build_draft(expert_id: str, tool_name: str, text: str) -> str | None:
    """Return sanitized Markdown for the exact post/tool pair, with no I/O."""
    if _TOOLS.get(expert_id) != tool_name:
        return None
    facts = _Facts(text)
    return {"it-ops": _ops, "it-data": _data, "it-app": _app}[expert_id](facts)
