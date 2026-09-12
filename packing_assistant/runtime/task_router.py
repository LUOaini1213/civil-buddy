"""Workbench task routing, separate from the shared Python/Rust legacy matcher.

Pure routing data only: no execution, model calls, approval, or inferred inputs.
The caller validates enabled/custom selections against its live catalog.
"""
from __future__ import annotations

import re

from packing_assistant.expert_roster import list_experts
from packing_assistant.understand import understand

_TASK_PHRASES = {
    "pm-daily": ("整理日报", "项目日报", "写日报", "做日报", "生成日报", "日报模板", "工程日志"),
    "dispatch": ("调度日报", "生产调度", "调度指令"),
    "it-data": ("备份策略", "备份计划", "备份方案", "恢复演练", "数据备份"),
    "steel": ("钢构说明", "钢结构说明", "钢结构", "钢构"),
    "bid-parse": ("招标解析", "解析招标", "抽取评分点", "提取评分点", "评分点表"),
    "bid-compliance": ("投标响应", "响应检查", "检查响应", "响应缺口", "废标检查", "废标风险"),
    "bid-tech": ("技术标", "技术响应草稿"),
    "construction": ("施工方案", "专项方案", "专项施工方案"),
    "admin-office": ("会务清单", "会议安排", "整理会务", "接待清单"),
    "method-hazard": ("危大识别", "危大判定", "是否危大", "危大工程"),
}
_AMBIGUOUS_REASONS = {
    "design-coord": "处理图纸会审、专业接口与设计变更技术事项",
    "variation": "整理变更签证的事实、依据与工程量栏",
}
_PREFIX = r"(?:(?:请帮我|帮我|麻烦|请|这次|本次|暂时|现在|进一步|继续|接着|先|再|仅仅|只需|只要|仅|只)\s*)*"
_NEGATED = re.compile(r"^" + _PREFIX + r"(?:不要|不用|无需|暂不|不需要|不想|不做|不写|不生成|别|禁止|我不(?:想|需要|打算|要求))")
_QUESTION = re.compile(r"什么|如何|怎么|为什么|能做什么|需要哪些|有哪些|是否|能否|能不能|区别|含义")
_READ_REQUEST = re.compile(r"^" + _PREFIX + r"(?:解释|说明一下|介绍|聊聊|讨论|说说|讲解|科普|概述|咨询)")
_ACTION = re.compile(r"(?:帮我|请|需要|想要|先|再|只)?\s*(?:整理|编制|生成|制作|起草|准备|审查|核对|检查|评审|制定|写|做)")
_FOLLOWUP_ACTION = re.compile(r"(?:然后|并且|之后|随后|接着|同时|再|并|后)\s*(?:请帮我|帮我|请|给我|为我)?\s*(?:整理|编制|生成|制作|起草|准备|审查|核对|检查|评审|制定|写|做)")
_QUOTED = re.compile(r'```[\s\S]*?```|`[^`\n]*`|“[^”]*”|‘[^’]*’|「[^」]*」|『[^』]*』|"[^"\n]*"|(?<!\w)\'[^\'\n]*\'')
_REFERENCE_END = re.compile(r"的(?:流程|注意事项|注意点|步骤|原因|含义|区别|意义|作用|风险|要求|方法|思路)[？?。！!\s]*$")
_SEQUENCE = re.compile(r"先.+(?:再|然后)|之后|随后|接着", re.S)
_TENDER = ("bid-parse", "bid-tech", "bid-compliance")


def _positive_text(message: str) -> str:
    return "，".join(part.strip() for part in re.split(r"[，,。；;\n]", message)
                    if part.strip() and not _NEGATED.match(part.strip()))


def _intent(text: str) -> str:
    # Quoted operations describe source material, not actions authorized by this
    # turn. Keep the original text separately for selecting the relevant post.
    text = _positive_text(_QUOTED.sub("〔引用〕", text))
    base = understand(text)
    read_request = bool(_QUESTION.search(text) or _READ_REQUEST.search(text))
    if read_request:
        followup_action = False
        for match in _FOLLOWUP_ACTION.finditer(text):
            clause_start = text.rfind("，", 0, match.start()) + 1
            clause_end = text.find("，", match.end())
            clause_end = len(text) if clause_end < 0 else clause_end
            # "为什么先检查再生成" asks about a sequence. A separate
            # "然后生成" clause, or "解释后生成", still requests a deliverable.
            if not _QUESTION.search(text[clause_start:match.start()]) and not _REFERENCE_END.search(text[match.end():clause_end]):
                followup_action = True
                break
        return "both" if followup_action else "chat"
    if _ACTION.search(text):
        return "both" if base == "both" else "run"
    return base


def _label(eid: str, roster: dict) -> str:
    expert = roster.get(eid)
    return expert.name if expert else eid


def _candidate(eid: str, roster: dict) -> dict:
    expert = roster[eid]
    return {"expert_ids": [eid], "label": expert.name,
            "reason": _AMBIGUOUS_REASONS.get(eid, expert.title)}


def _steps(ids: list[str], workflow: str, text: str, roster: dict) -> list[dict]:
    if workflow == "tender-review":
        return [
            {"id": "parse", "expert_id": "bid-parse", "label": "解析招标原文", "depends_on": []},
            {"id": "tech", "expert_id": "bid-tech", "label": "整理技术响应", "depends_on": ["parse"]},
            {"id": "compliance", "expert_id": "bid-compliance", "label": "检查响应缺口", "depends_on": ["parse"]},
            {"id": "aggregate", "expert_id": "", "label": "汇总证据与未解决事项", "depends_on": ["tech", "compliance"]},
        ]
    sequential = bool(_SEQUENCE.search(text))
    return [{"id": f"task-{i + 1}", "expert_id": eid, "label": _label(eid, roster),
             "depends_on": [f"task-{i}"] if sequential and i else []} for i, eid in enumerate(ids)]


def _mention_labels(roster: dict) -> dict[str, set[str]]:
    labels: dict[str, set[str]] = {}
    for expert in roster.values():
        for label in (expert.id, expert.name, *expert.aliases):
            if label:
                labels.setdefault(label.casefold(), set()).add(expert.id)
    return labels


def _without_leading_mentions(text: str, roster: dict) -> str:
    """Known addressing prefixes do not change the intent of the following words."""
    labels = sorted(_mention_labels(roster), key=len, reverse=True)
    while marker := re.match(r"(?:[@$]|召唤)\s*", text):
        tail = text[marker.end():]
        label = next((label for label in labels if tail.casefold().startswith(label)
                      and not (re.fullmatch(r"[a-z0-9-]+", label)
                               and re.match(r"[a-z0-9_-]", tail[len(label):], re.I))), None)
        if label is None:
            break
        text = tail[len(label):].lstrip(" \t\r\n,，:：;；")
    return text


def _explicit(text: str, roster: dict) -> tuple[list[str], list[dict]]:
    """Longest exact label after @/$/召唤; shared aliases remain ambiguous."""
    labels = _mention_labels(roster)
    ordered = sorted(labels, key=len, reverse=True)
    ids: list[str] = []
    candidates: list[dict] = []
    for marker in re.finditer(r"[@$]|召唤", text):
        tail = text[marker.end():].lstrip().casefold()
        for label in ordered:
            if not tail.startswith(label):
                continue
            if re.fullmatch(r"[a-z0-9-]+", label) and re.match(r"[a-z0-9_-]", tail[len(label):]):
                continue
            matches = labels[label]
            if len(matches) > 1:
                candidates.extend(_candidate(eid, roster) for eid in sorted(matches))
            else:
                eid = next(iter(matches))
                if eid not in ids:
                    ids.append(eid)
            break
    return ids, candidates


def route_task(message: str, expert_ids: list[str] | None = None) -> dict:
    """Return selection, ambiguity and dependency data without doing any work."""
    if not isinstance(message, str):
        raise ValueError("任务内容必须是文字")
    roster = {expert.id: expert for expert in list_experts()}
    text = _positive_text(message.strip())
    result = {"expert_ids": [], "workflow": "", "candidates": [], "reason": "尚未匹配明确岗位，可浏览岗位目录选择。",
              "ambiguous": False, "intent": _intent(_without_leading_mentions(message.strip(), roster)), "steps": []}
    explicit = False
    if expert_ids:
        if any(not isinstance(eid, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", eid) for eid in expert_ids):
            raise ValueError("岗位选择格式无效")
        ids = list(dict.fromkeys(expert_ids))
        explicit = True
        result["reason"] = "按你已选择的岗位执行。"
    else:
        ids, candidates = _explicit(text, roster)
        if candidates:
            result.update(ambiguous=True, candidates=candidates, reason="这个岗位称呼有多个含义，请选择本次要处理的事项。")
            return result
        explicit = bool(ids)
        if explicit:
            result["reason"] = "按任务中明确点名的岗位执行。"
    if not explicit:
        comprehensive = (bool(re.search(r"招标|投标|技术标", text))
                         and bool(re.search(r"综合|全面|整体|成套|完整|全套|三岗", text))
                         and bool(re.search(r"检查|审查|响应|评审|审阅", text)))
        if comprehensive:
            ids = list(_TENDER)
            result["workflow"] = "tender-review"
            result["reason"] = "综合投标响应检查需要先解析原文，再分别整理技术响应和检查缺口，最后汇总。"
        else:
            hits: dict[str, tuple[int, int]] = {}
            matched_labels: dict[str, set[str]] = {}
            for expert in roster.values():
                phrases = set(_TASK_PHRASES.get(expert.id, ())) | {p for p in (expert.name, *expert.aliases) if len(p) >= 4}
                for phrase in phrases:
                    if phrase in text:
                        hits[expert.id] = max(hits.get(expert.id, (0, 0)), (len(phrase), -text.index(phrase)))
                        matched_labels.setdefault(phrase, set()).add(expert.id)
            # A shared label alone cannot justify selecting two different duties.
            ambiguous = {eid for label, owners in matched_labels.items() if len(owners) > 1
                         for eid in owners if hits.get(eid, (0,))[0] <= len(label)}
            if len(ambiguous) > 1:
                result.update(ambiguous=True, candidates=[_candidate(eid, roster) for eid in sorted(ambiguous)],
                              reason="任务同时对应不同职责，请明确要技术会审还是变更签证等具体交付。")
                return result
            # A specific compound name wins over its contained general label.
            for label, owners in matched_labels.items():
                for other, other_owners in matched_labels.items():
                    if label != other and label in other and len(owners) == 1:
                        eid = next(iter(owners))
                        if eid not in other_owners and hits.get(eid, (0,))[0] <= len(label):
                            hits.pop(eid, None)
            ids = sorted(hits, key=lambda eid: (-hits[eid][1], -hits[eid][0]))
            if ids:
                result["reason"] = "根据任务中的具体交付和专业词选用：" + "、".join(_label(eid, roster) for eid in ids) + "。"
    if len(ids) > 8:
        result.update(ambiguous=True, candidates=[_candidate(eid, roster) for eid in ids if eid in roster],
                      reason="涉及岗位较多，请先选择本轮的主要交付。")
        return result
    if set(ids) == set(_TENDER) and result["intent"] != "chat":
        result["workflow"] = "tender-review"
        ids = list(_TENDER)
    # Educational questions can route to a post, but never launch a workflow.
    if result["intent"] == "chat":
        result["workflow"] = ""
    result["expert_ids"] = ids
    result["steps"] = _steps(ids, result["workflow"], text, roster)
    return result
