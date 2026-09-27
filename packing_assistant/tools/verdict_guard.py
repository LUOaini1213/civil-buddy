"""不该由 AI、也不该由一份草稿下的结论：可以订舱、符合招标文件的要求、可以开工、报审通过……

数字溯源（tools/number_provenance）管「这个数有没有出处」，管不了「这句话是不是在下结论」。
实测本机小模型在装柜回复里写了「可以订舱」（工具报告写的是不可直接订舱），在招标对照里写了
「符合招标文件的要求」（工具只给候选对照，明确不判合规）。这里是对应的确定性检查：

    stated_verdicts(text) -> 文中**下了**的结论（原文片段、位置）

「下了」是关键，三种情形不算，判定范围都是**同一个分句**：
    否认 / 疑问    不判定可以开工 · 是否可以订舱 · 可以订舱吗？
    条件 / 要求    验收合格后方可进入下道工序 · 补齐之后才谈得上可以投标 · 须满足规范要求
    前一分句的否定不算：「重量不大，体积也不大，可以订舱」照报

数字见 test/benchmarks/verdicts/README.md（scripts/eval_verdicts.py --variant all）。先说最要紧的一条：
开发集上是满分，第一轮留出集上**只有 P 0.667 / R 0.500**——第一版是字面短语表，没见过的说法抓不到一半，
还误报了两句条件句。现在的句式模式和条件判定就是据此改的；改完之后的数以第二轮留出集为准。

结论的种类宁紧勿宽：只收投标、开工、订舱发运、验收、报审论证、对招标/规范/合同的符合性这几类
本产品明令不许下的结论。「可以使用」「可以实施」这类泛用说法不收。要加，先往基准里加正例和反例。
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

from packing_assistant.tools.tender_review import ASSERTIVE

#: 与 runtime/agent_loop.FORBIDDEN 同一组词；放在这里是为了让 tools 层不反过来依赖 runtime。
_FORBIDDEN = ("可以投标", "可以开工", "中标率")
#: 第一版：字面短语。保留它是为了量得出「句式模式带来了什么」。
_LITERAL = (
    "可以订舱", "可直接订舱", "可以发运", "可以发货",
    r"符合招标(?:文件)?的?要求", r"满足招标(?:文件)?的?要求", "已实质性响应", "已实质响应", "没有废标风险", "无废标风险",
    "验收合格", "可以验收",
    r"compliant with the tender", r"ready to submit", r"ready to book", r"may commence work",
)
_PATTERNS = (
    r"可(?:以|直接)?(?:投标|开工|订舱|发运|发货|验收|报审)",
    r"可以投(?=[。，,；;！!\s]|$)",                                   # 「这个标可以投。」；不含「可以投入使用」
    r"(?:符合|满足)(?:招标文件|招标|规范|设计|合同|标准|图纸)(?:的)?(?:全部|各项)?要求",
    r"(?:已经?)?通过(?:了)?(?:专家论证|专家评审|报审|审查|验收)", r"(?:论证|验收|报审)通过",
    r"(?:没有|不存在|无)废标(?:风险|问题|项)", r"已实质性?响应",
    r"验收合格",
    r"compliant with the (?:tender|specification|contract)", r"ready to (?:submit|book|ship)", r"may commence work",
)


def _compile(parts) -> re.Pattern:
    return re.compile("|".join(sorted(parts, key=len, reverse=True)), re.I)


_BASE = tuple(re.escape(p) for p in (*ASSERTIVE, *_FORBIDDEN))
_VERDICT_LITERAL = _compile((*_BASE, *_LITERAL))
_VERDICT = _compile((*_BASE, *_PATTERNS))
_CLAUSE_BREAK = re.compile(r"[，,。；;：:！!？?\n]")
_NEGATION = re.compile(r"不|非|未|无法|禁止|勿|别|没有?(?!废标)|是否|能否|能不能|可否|算不算|\b(?:not|no|never|cannot|whether|if)\b|n't", re.I)
# 同一分句里、结论之前出现这些，说的是条件或要求，不是结论。
_CONDITION_BEFORE = re.compile(r"才|方可|方能|如果|倘若|若|一旦|(?<![接对招期等])待(?!遇)|须|必须|应当|应(?![答对用力])|需(?!要说明)|确保|保证(?!金)|要求|\b(?:must|shall|should|once|after|when|unless)\b", re.I)
# 结论后面紧跟这些，它是别的动作的前提（验收合格后方可……）。
_CONDITION_AFTER = re.compile(r"^(?:之?后|以后|之?前|以前|时|的话|的前提|的条件|者|与否|才)")
_QUESTION_TAIL = re.compile(r"^[^，,。；;！!\n]{0,12}(?:吗|么|呢)?\s*[？?]|^\s*(?:吗|么)")


def stated_verdicts(text: str, *, negation: bool = True, clause_scope: bool = True, questions: bool = True,
                    conditions: bool = True, patterns: bool = True) -> List[Dict[str, Any]]:
    blob = text or ""
    found: List[Dict[str, Any]] = []
    for match in (_VERDICT if patterns else _VERDICT_LITERAL).finditer(blob):
        if clause_scope:
            breaks = [m.end() for m in _CLAUSE_BREAK.finditer(blob, 0, match.start())]
            before = blob[breaks[-1] if breaks else 0: match.start()]
        else:
            before = blob[max(0, match.start() - 8): match.start()]
        after = blob[match.end(): match.end() + 16]
        if negation and _NEGATION.search(before):
            continue
        if conditions and (_CONDITION_BEFORE.search(before) or _CONDITION_AFTER.search(after)):
            continue
        if questions and _QUESTION_TAIL.search(after):
            continue
        found.append({"kind": "verdict", "text": match.group(0), "start": match.start(), "end": match.end()})
    return found


def notice(found: List[Dict[str, Any]], *, english: bool = False) -> str:
    if not found:
        return ""
    names = dict.fromkeys(str(item["text"]) for item in found)
    if english:
        return ("⚠ These verdicts are not this system's to give; they were taken out of the reply, and a qualified "
                "person decides: " + ", ".join(names))
    items = "、".join(names)
    return f"⚠ 以下结论不由本系统下，已从回复里去掉，请由有资格的人判断：{items}"


def strike(text: str, found: List[Dict[str, Any]], *, english: bool = False) -> str:
    """The text with each stated verdict replaced, right to left so positions stay valid."""
    out = text
    for item in sorted(found, key=lambda entry: entry["start"], reverse=True):
        mark = "(verdict removed: not this system's call)" if english else "（此处结论不由本系统判定）"
        out = out[: item["start"]] + mark + out[item["end"]:]
    return out


_SHIPPED = dict(negation=True, clause_scope=True, questions=True, conditions=True, patterns=True)
ABLATIONS: Dict[str, Dict[str, bool]] = {
    "literal phrases, no condition check (v1)": dict(_SHIPPED, patterns=False, conditions=False),
    "+ sentence patterns": dict(_SHIPPED, conditions=False),
    "+ condition check (shipped)": dict(_SHIPPED),
    "ablate: 8-char window, not the clause": dict(_SHIPPED, clause_scope=False),
    "ablate: no negation check": dict(_SHIPPED, negation=False),
    "ablate: no question check": dict(_SHIPPED, questions=False),
}
ABLATIONS["shipped"] = dict(_SHIPPED)
