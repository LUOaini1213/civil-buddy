#!/usr/bin/env python3
"""Generate Codex/Agent Skills: one SKILL.md per workbench expert.

Canonical: .agents/skills/<id>/SKILL.md
Mirror:    .codex/skills/<id>/SKILL.md  (older Codex repo scan)

Do not hand-edit generated files. Change workbench/seed.json or this renderer.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "demo"
sys.path.insert(0, str(DEMO))

sys.path.insert(0, str(ROOT))
from catalog_seed import CATEGORIES, EXPERTS  # noqa: E402
from packing_assistant.expert_capabilities import load_seed, tier_map  # noqa: E402

AGENTS_DIR = ROOT / ".agents" / "skills"
CODEX_DIR = ROOT / ".codex" / "skills"
YIBIAO = ROOT / "workbench" / "yibiao-map.json"
KB = DEMO / "kb"

HARD_RULES = """- 不编条款号、材料强度、岩土参数、综合单价、xyz、柜数、N0。
- 引用写全名+年份+条款；没抽到原文标 unverified / UNSPECIFIED。
- 无来源数字写 [A001] 起待填。
- 禁止断言：可交差、可报审、报审通过、可提交专家论证、请监理审核后开工、可以开工、可以投标。
- 产出是内部讨论 AI 草稿，不是法定签认件。
- 辖区 CN / SG / EU / DUAL 禁止静默混用。以本次明确地区或会话已确认地区为准；未提供则 UNSPECIFIED，不默认国家。DUAL 的依据和接口按明确地区分栏。
- 高风险成稿写盘前，用户须打出：我明白，将由持证人员签认。纯提问不受确认门阻挡。"""

def _yaml_str(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)


def _exclusive_map() -> dict[str, list[str]]:
    return {e["id"]: e["exclusive"] for e in load_seed()["experts"]}


def _description(e) -> str:
    triggers = "、".join(e.aliases[:6]) or e.name
    return f"{e.name}（{e.category_name}）：{e.title}。交付{e.delivers}。适用于{triggers}。内部草稿。"


def render_expert(e, exclusive: list[str]) -> str:
    row = next(x for x in load_seed()["experts"] if x["id"] == e.id)
    if exclusive != row["exclusive"]:
        raise ValueError(f"{e.id} 工具映射与权威目录不一致")
    cap = row["capability"]
    fm = ["---", f"name: {e.id}", f"description: {_yaml_str(_description(e))}", "metadata:"]
    for key in ("category", "category_name", "title", "delivers", "risk"):
        fm.append(f"  {key}: {_yaml_str(getattr(e, key))}")
    fm.extend([f"  aliases: {_yaml_str(','.join(e.aliases))}", "---", ""])
    lines = [f"# {e.name}", "",
        f"Civil Buddy 的{e.category_name}专业技能；程序记忆（Skill / SOP），不是用户画像或规范全文。",
        f"{e.title}。默认交付：{e.delivers}。风险：{e.risk}。", "",
        "可以只聊天。只有用户本轮要求成稿才调用写入工具；缺少资料可列空栏骨架，不能把待核输入变成事实。",
        "", "## 成稿资料", "",
        "按本次任务核对以下资料；缺项逐项标 [A001] / UNSPECIFIED，招标未载内容标「招标未写」。", ""]
    lines.extend("- " + item for item in cap["inputs"])
    lines.extend(["", "## 专属步骤", ""])
    for number, step in enumerate(cap["steps"], 1):
        tools = "；调用 " + "、".join(f"`{name}`" for name in step["tools"]) if step["tools"] else ""
        lines.append(f"{number}. {step['action']}{tools}。")
    if cap.get("runtime_note"):
        lines.extend(["", cap["runtime_note"]])
    lines.extend(["", "## 输出结构", "",
        "交付完整 Markdown 草稿及可打开的 Word；正文有表格时可导出 Excel。文首保留内部草稿声明，签认栏由持证人员填写。", ""])
    lines.extend(f"{i}. {section}" for i, section in enumerate(cap["output_sections"], 1))
    lines.extend(["", "专业表格至少表达以下字段（缺项保留空栏，不能串用其他对象的值）：", ""])
    for table in cap["output_tables"]:
        lines.append(f"- {table['name']}：" + "｜".join(table["columns"]))
    lines.extend(["", "## 验收", ""])
    lines.extend("- " + item for item in cap["acceptance"])
    lines.append("- 实际生成文件须能打开；用户已给字段进入对应正文或表格，不能仅在附录重复用户原文。")
    lines.extend(["", "## 能力边界", ""])
    lines.extend("- " + item for item in cap["limitations"])
    lines.append("- 本岗专属工具不能借给兄弟岗；文书起草工具不等于工程求解器。")
    lines.extend(["", "## 按需读取", ""])
    for reference in cap["reference_paths"]:
        lines.append(f"- 需要完整专业细节时读 `{reference}`；其中历史规范标题不是已经核实的现行依据。")
    lines.extend([
        f"- 检索仅限本岗 `demo/kb/{e.category}/{e.id}/` 与大类 `demo/kb/{e.category}/_shared/`。",
        "- 公司规则：`demo/kb/company/hard-rules.md`；法规引用打开对应官方原文再核对版本和条款。",
        "", "## 共同边界", "", HARD_RULES, ""])
    return "\n".join(fm + lines)


def render_router() -> str:
    lines = ["---", "name: civil-buddy",
        "description: " + _yaml_str("Civil Buddy 土木企业岗位路由器，16 大类 66 岗。用于选择施工、设计、投标、物机等专业技能；先看岗位目录，选中后才加载对应 SOP。"),
        "---", "", "# Civil Buddy", "",
        "Host 是 Civil Buddy；每个岗位是一份专业技能。目录只负责选择，不能把 66 份 SOP 一次灌入模型。", "",
        "1. 根据用户目的选择主笔岗位；跨专业任务按用户范围分工。",
        "2. 只读取所选 `.agents/skills/<id>/SKILL.md`，其资料、步骤、输出结构和验收条件来自 `workbench/seed.json`。",
        "3. 独有工具仅由所属岗位使用；未连接求解器的数值保持 UNSPECIFIED。",
        "4. 聊天不写业务产物；当前强类型确认与写入权限由运行时逐次检查，历史确认不生效。", "",
        "## 专业目录", "", "| id | 岗位 | 大类 | 适用任务 |", "|---|---|---|---|"]
    for e in EXPERTS:
        lines.append(f"| `{e.id}` | {e.name} | {e.category_name} | {e.title} |")
    lines.extend(["", "## 共同边界", "", HARD_RULES, ""])
    return "\n".join(lines)


def expected_files() -> dict[str, str]:
    mapping = _exclusive_map()
    files = {e.id: render_expert(e, mapping[e.id]) for e in EXPERTS}
    files["civil-buddy"] = render_router()
    return files


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Compare generated skills and tool map without writing")
    args = parser.parse_args()
    files = expected_files()
    generated = {root / name / "SKILL.md": text for root in (AGENTS_DIR, CODEX_DIR) for name, text in files.items()}
    generated[YIBIAO] = json.dumps(tier_map(), ensure_ascii=False, indent=2) + "\n"
    if args.check:
        changed = [str(p.relative_to(ROOT)) for p, text in generated.items()
                   if not p.is_file() or p.read_text(encoding="utf-8") != text]
        if changed:
            print("FAIL generated files differ: " + ", ".join(changed))
            return 1
        print(f"PASS {len(EXPERTS)} professional contracts, both skill mirrors and generated tier-map agree")
        return 0
    # Only replace our known generated artifacts. Preserve custom skills/files.
    for path, text in generated.items():
        if path.is_file() and path.read_text(encoding="utf-8") == text:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
    print(f"PASS wrote {len(EXPERTS)} expert skills + router in both mirrors and the tier-map")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
