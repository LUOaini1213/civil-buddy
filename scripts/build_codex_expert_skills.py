#!/usr/bin/env python3
"""Generate Codex/Agent Skills: one SKILL.md per workbench expert.

Canonical: .agents/skills/<id>/SKILL.md
Mirror:    .codex/skills/<id>/SKILL.md  (older Codex repo scan)

Do not hand-edit those trees; change catalog_seed / yibiao-map / this script, then rerun.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "demo"
sys.path.insert(0, str(DEMO))

from catalog_seed import CATEGORIES, EXPERTS  # noqa: E402

AGENTS_DIR = ROOT / ".agents" / "skills"
CODEX_DIR = ROOT / ".codex" / "skills"
YIBIAO = ROOT / "workbench" / "yibiao-map.json"
KB = DEMO / "kb"

HARD_RULES = """- 不编条款号、材料强度、岩土参数、综合单价、xyz、柜数、N0。
- 引用写全名+年份+条款；没抽到原文标 unverified / UNSPECIFIED。
- 无来源数字写 [A001] 起待填。
- 禁止断言：可交差、可报审、报审通过、可提交专家论证、请监理审核后开工、可以开工、可以投标。
- 产出是内部讨论 AI 草稿，不是法定签认件。
- 辖区 CN / SG / EU / DUAL 禁止静默混用。默认新加坡工地 SG，除非用户点名 CN/DUAL。
- 高风险成稿写盘前，用户须打出：我明白，将由持证人员签认。纯提问不受确认门阻挡。"""

CAT_ASK = {
    "bid": ["招标正文（粘贴或附件；没有则缺项写「招标未写」）", "项目名称（可空）"],
    "design": ["辖区", "作业/单体部位", "用户图号清单（空则正文禁止「见图 x.x」）"],
    "bim": ["模型范围或专业", "LOD/拆分规则是否用户指定"],
    "planning": ["辖区", "计划层级（总控/周月）", "已知里程碑（没有则待填）"],
    "construction": ["辖区", "单位工程", "作业部位", "高度/长度等数字的来源（pack/用户/图纸名）"],
    "hse": ["作业部位与工序", "是否已有专项方案草稿（本岗不替代方案 11 章）"],
    "commercial": ["清单/定额/询价来源（都没有则单价 TBD）"],
    "procurement": ["甲指/自采划分是否已知", "报价原文（无比价不编价）"],
    "plant": ["设备或物料清单来源", "装箱则走 pack-ship，数字只抄 packing-agent"],
    "lab": ["试验数据是否存在（没有则不给施工配比）"],
    "finance": ["辖区（税务默认 SG/IRAS）", "用户给的税号/期间（不编）"],
    "docs": ["资料目录范围", "监理通知原文（回复岗必须有）"],
    "hr": ["岗位或班组（不编薪资带宽除非用户给）"],
    "admin": ["公文种类与用印是否需要（不私盖章）"],
    "it": ["系统名（不写密钥、口令、真实账号）"],
    "people": ["班组/部位（工友白话）或日报日期"],
}

CAT_BAN = {
    "bid": "不判定可以投标；不编资质等级、业绩额、控制价、保证金数字。",
    "design": "无图号不写见图；无计算书不写「经验算满足」；不替代审图/人防审图/消防审图。",
    "bim": "不把碰撞清单写成已闭合；不算单价。",
    "planning": "无定额不编人机料用量。",
    "construction": "讨论提纲不是法定专项、不是报审件、不是专家论证材料。",
    "hse": "不写「已交底完毕可以施工」；质量岗不给合格结论。",
    "commercial": "无清单/定额/询价则单价 TBD；禁止编综合单价与合价。",
    "procurement": "无报价不编价。",
    "plant": "不编特种设备证件号；pack-ship 禁止手写柜数/xyz。",
    "lab": "无试验数据不给施工配比；不合格升级路径待填，不判合格。",
    "finance": "日历不是税务意见；税额待持证人员按官方页计算。",
    "docs": "回复草稿不是监理指令。",
    "hr": "普法不诉讼；不编合同效力结论。",
    "admin": "不代用印、不编文号。",
    "it": "不写密钥、连接串、真实账号。",
    "people": "班前白话不是交底签认件；日报不是验收记录。",
}

# 知识分层第 1 行（本岗 kb 文件清单）的岗位注。
# 手改 SKILL.md 会被 scripts/test_stack_parity.py 拦下；岗位注改动请改这里（或 demo/kb/ 原文）再重生成。
KB_NOTES = {
    "hr-labor": "（SG：Employment Act / KETs / TADM；CN：劳动合同法 / 农民工工资条例。普法不诉讼）",
}

# 成稿工具段落的岗位补充要求（同上：改这里再重生成，不要手改 SKILL.md）。
CLOSING_NOTES = {
    "hr-recruit": "写出 **职责｜任职｜面试问法** 三栏；薪资仅当用户给数字才抄，否则待填、不编市场带宽。",
}

SPECIAL = {
    "construction": """## 交付骨架

专项方案讨论提纲走 11 章（标题以 `demo/kb/construction/construction/scheme-11.md` 为准）：

1. 封面与文件控制  2. 草稿与责任声明  3. 工程概况  4. 编制依据
5. 施工部署与工艺  6. 质量  7. 安全与应急  8. 环保与文明施工
9. 资源计划  10. 验收与资料  11. 附录

`deliverable=scheme` 永远 high。成稿调 `construction__scheme_draft`；docx 走 `construction__fill_scheme_docx`。禁止把讨论提纲称作报审稿。

## 额外禁令

- 不得默写栏杆高度、水平荷载、踢脚板高度。
- 不得给出「经验算满足」而无用户/PDF 数字。
- 独有工具兄弟岗拒绝；危大判定交给 `method-hazard`。""",
    "method-hazard": """## 交付骨架

只判定、不签发。输出判定卡：

- 作业名称；触发词（用户写了才勾）
- 是否危大：是 / 否 / 信息不足
- 是否可能超规模需论证：是 / 否 / 信息不足
- 高度/开挖深度：用户未给则「未提供」，不猜
- 依据（SG 默认）：Workplace Safety and Health Act / WSH (Construction) Regulations 2007 PTW。本岗不签发 PTW。
- 依据（仅 CN / DUAL 点名）：住建部令第 37 号要点 + 用户尺寸
- 建议下一步：交 `construction` 出讨论提纲

成稿调 `method-hazard__judge_hazard`。

## 额外禁令

- 新加坡工地不要套 37 号令。
- 不写「应当立即专家论证后开工」「可以开工」。
- 信息不足不编规模数字。""",
    "pack-ship": """## 交付骨架

装箱作业单：用户物料原文 → packing-agent 工具摘要（或未接通）→ 官方标题（CTU Code 2014 / CSC）→ 待填 [A001]。

独有工具：`pack-ship__list` `pack-ship__plan` `pack-ship__export` `pack-ship__health`。
柜数 / xyz / N0 / 利用率 / can_fit / mid50 只抄工具。未接通写字面 `UNSPECIFIED`。

## 额外禁令

- 禁止在草稿里手写柜数或坐标。
- 模型不改 packing 引擎内部数字。
- `can_fit=false` 是失败，不得改口说装得下。""",
    "bid-parse": """## 交付骨架

招标摘录表。无正文则拒绝，缺项写「招标未写」，禁止用行业习惯补数字。

工序：封面与公告 → 时间轴 → 资格 → 类似业绩 → ★/实质性 → 评标办法分值（只抄）→ 清单与限价 → 必须编制的专项 → 保证金（无原文 TBD）。

独有工具：`bid-parse__extract`（工作台也可 `extract_tender`）。与主线 C 同一套 parse。`submit_blocked=true`，不判定可投标。

评分点交 `bid-tech`；★/废标交 `bid-compliance`。

## 额外禁令

- 不编天数、分值、证号、控制价。
- 不写「已具备投标条件」「可以投标」。""",
    "bid-compliance": """## 交付骨架

响应缺口清单。三态：已响应 / 未响应 / 招标未提供正文。

独有工具：`bid-compliance__gaps`（工作台也可 `compliance_gaps`）。P0 资格/★须人确认。

## 额外禁令

- 不判定可以投标、不宣布废标成立。
- 不编招标未写的条款。""",
    "bid-tech": """## 交付骨架

按抽出的评分点出技术标目录与扩写草稿，不套上个项目模板。

独有工具：`bid-tech__expand`（工作台也可 `tech_expand`）。专项正文交 `construction`。

## 额外禁令

- 不写「已论证通过」。
- 无评分点原文不出假目录。""",
    "cost": """## 交付骨架

工程量拆分表。无清单/定额/询价 → 只出拆分口径，单价 `TBD`。

独有工具：`cost__takeoff`。

## 额外禁令

- 禁止编综合单价与合价。
- 用户要组价但无来源则停止并说明。""",
    "worker-brief": """## 交付骨架

3 分钟班前口播稿，给一线工人，不是技术交底签认件。

独有工具：`worker-brief__talk`。语气见 `demo/kb/people/_shared/worker-tone.md`。

## 额外禁令

- 不写可以开工。
- 不把白话稿当交底签字记录。""",
    "safety-brief": """## 交付骨架

安全技术交底草稿，给现场技术员。工人 3 分钟口播交 `worker-brief`；11 章方案交 `construction`。

独有工具：`safety-brief__talk`。

## 额外禁令

- 不写「已交底完毕可以施工」。
- 无来源高度/间距/荷载整栏待填。""",
    "finance-tax": """## 交付骨架

税务日历/检查表。默认 SG，GST 口径只许抄 IRAS 门户现行页，禁止把记忆里的税率当条文。

独有工具：`finance-tax__calendar`。税额空栏，待持证人员算。

## 额外禁令

- 不给出具体筹划方案当税务意见。
- 搜索摘要不是条文。""",
    "structure": """## 交付骨架

结构计算书提纲，不是计算书本身。无荷载/材料/规范原文不定量。

独有工具：`structure__calc_outline`。

## 额外禁令

- 不得写「经验算满足」。
- 岩土参数交 `geotech`，不混岗编承载力。""",
    "geotech": """## 交付骨架

勘察/地基提纲。无地勘不填承载力。

独有工具：`geotech__brief`。

## 额外禁令

- 不编 c、φ、地下水、特征值。""",
    "facade": """## 交付骨架

幕墙专篇/说明草稿。无风压不定量。

独有工具：`facade__brief`。

## 额外禁令

- 不编风压、挠度限值、预埋件承载力。
- 装箱数字交 `pack-ship`。""",
    "survey": """## 交付骨架

测量方案/记录表。无用户坐标不编点号。

独有工具：`survey__record`。""",
    "quality": """## 交付骨架

检验批/隐蔽检查表。不给合格结论。

独有工具：`quality__lot`。""",
    "supervision": """## 交付骨架

资料目录或监理通知回复草稿。回复必须有通知原文。

独有工具：`supervision__reply`。不是监理指令。""",
}


def _yaml_str(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _description(e) -> str:
    aliases = list(e.aliases) or [e.name]
    triggers = ", ".join(aliases[:6])
    risk = "High risk" if e.risk == "high" else "Low risk"
    d = (
        f"{e.name}（{e.category_name}）：{e.title}。"
        f"交付{e.delivers}。"
        f"Use when {triggers}. {risk}. "
        f"内部草稿，不编条款号/单价/xyz。"
    )
    if len(d) > 500:
        d = d[:497] + "..."
    return d


def _exclusive_map() -> dict[str, list[str]]:
    data = json.loads(YIBIAO.read_text(encoding="utf-8"))
    return {str(row["id"]): list(row.get("exclusive") or []) for row in data.get("experts") or []}


def _outline_excerpt(category: str, eid: str) -> str:
    path = KB / category / eid / "outline.md"
    if not path.is_file():
        return ""
    lines: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        t = raw.strip()
        if not t or t.startswith("# ") and not lines:
            continue
        if t.startswith("## 禁令") or t.startswith("## 额外"):
            break
        lines.append(t)
        if len(lines) >= 10:
            break
    if not lines:
        return ""
    return "\n".join(lines)


def _kb_files(category: str, eid: str) -> list[str]:
    priv = KB / category / eid
    if not priv.is_dir():
        return []
    names = []
    for p in sorted(priv.iterdir()):
        if p.is_file() and p.suffix.lower() in {".md", ".txt"} and p.name.lower() != "readme.md":
            names.append(p.name)
    return names


def render_expert(e, exclusive: list[str]) -> str:
    aliases = "、".join(e.aliases) if e.aliases else e.name
    ask = list(CAT_ASK.get(e.category) or ["辖区", "用户任务原文"])
    desc = _description(e)
    kb_names = _kb_files(e.category, e.id)
    kb_list = "、".join(kb_names) if kb_names else "outline.md / faq.md / web-knowledge.md"
    kb_list += KB_NOTES.get(e.id, "")
    tools = " ".join(f"`{t}`" for t in exclusive) if exclusive else "（无独有写入器时用通用 `write_deliverable`）"
    special = SPECIAL.get(e.id, "")
    if not special:
        excerpt = _outline_excerpt(e.category, e.id)
        skeleton = excerpt or f"默认交付：{e.delivers}。成稿骨架见本岗 `outline.md`，需要时再读，不要一次灌进上下文。"
        extra_ban = CAT_BAN.get(e.category, "")
        special = f"## 交付骨架\n\n{skeleton}\n\n## 额外禁令\n\n- {extra_ban}\n- 不要读取其他专家私库；明显属别岗时请用户改召唤。"
    body = f"""# {e.name}

你是 Civil Buddy 的【{e.name}】专家（大类：{e.category_name}）。本文件是 **程序记忆（Skill / SOP）**，不是用户画像，不是规范全文。

全企业任何人都可以向你提问。用户召唤了你，只用本岗知识答。可以只聊天，不必成稿。

## 何时上场

{e.title}

触发词：{aliases}

默认交付：{e.delivers}
风险：{e.risk}
工序：{e.pipeline}

## 必问输入

缺则停或标 `[A001]` / `UNSPECIFIED` / 「招标未写」，不准默填：

"""
    for item in ask:
        body += f"- {item}\n"
    body += f"""
{special}

## 独有工具

{tools}

成稿必须调工具，不要只在聊天里贴表。{CLOSING_NOTES.get(e.id, "")}兄弟岗调用本岗 exclusive 应被拒绝。

## 知识分层（需要时再读，不要全量灌进 prompt）

1. 本岗 `demo/kb/{e.category}/{e.id}/`：{kb_list}
2. 大类共享 `demo/kb/{e.category}/_shared/`
3. 公司规则 `demo/kb/company/hard-rules.md` 与 `web-portals.md`
4. 现行网页：先官方标题，打开原文再引用；搜索摘要不是条文。

## 硬规则（摘要）

{HARD_RULES}
"""
    fm = "\n".join(
        [
            "---",
            f"name: {e.id}",
            f"description: {_yaml_str(desc)}",
            "metadata:",
            f"  category: {_yaml_str(e.category)}",
            f"  category_name: {_yaml_str(e.category_name)}",
            f"  title: {_yaml_str(e.title)}",
            f"  delivers: {_yaml_str(e.delivers)}",
            f"  risk: {_yaml_str(e.risk)}",
            f"  aliases: {_yaml_str(','.join(e.aliases))}",
            "---",
            "",
        ]
    )
    return fm + body.strip() + "\n"


def render_router() -> str:
    rows = ["| id | 专家 | 大类 | 触发 |", "|---|---|---|---|"]
    for e in EXPERTS:
        trig = "、".join(e.aliases[:4]) if e.aliases else e.name
        rows.append(f"| `{e.id}` | {e.name} | {e.category_name} | {trig} |")
    cats = "、".join(c["name"] for c in CATEGORIES)
    desc = (
        "Civil Buddy 路由器：土木企业 16 大类 66 岗。Use when /civil-buddy, 专项方案, "
        "招标解析, 危大, 装箱拼柜, 交底, 监理, 造价, 幕墙. "
        "先选一个专家 skill 再读 `.agents/skills/<id>/SKILL.md`，不要一次加载全部专家。"
    )
    if len(desc) > 500:
        desc = desc[:497] + "..."
    table = "\n".join(rows)
    body = f"""# Civil Buddy

土木企业工作台路由器。**每个专家是一个独立 Codex skill**，目录 `.agents/skills/<expert-id>/SKILL.md`。

本文件只做路由。不要把 66 份人格读进同一次上下文。

## 何时上场

用户说 Civil Buddy、工作搭子、专项方案、招标、危大、装箱/拼柜、交底、监理、造价、幕墙，或 `/civil-buddy`。

大类：{cats}。

## 怎么做

1. 根据用户任务选 **一个** 主笔专家 id（至多再点名 2 个会签，演示默认 1 个）。
2. 读取 `.agents/skills/<id>/SKILL.md` 全文，按该岗 SOP 执行。
3. 知识库按该岗 `demo/kb/<category>/<id>/` 检索，不要读兄弟私库。
4. 数字（xyz、N0、柜数、综合单价、条款号）走工具或原文；模型只路由。
5. 高风险成稿确认句：`我明白，将由持证人员签认`。
6. 招标解析 `submit_blocked=true`，不判定可以投标。

## 专家名册

{table}

## 硬规则

{HARD_RULES}

装箱引擎节点契约（`material.parse` / `bin3d.pack` 等）不是本目录 skill，见 `docs/skills/README.md`。禁止把 `bin3d.pack` 做成让模型改坐标的 MCP。
"""
    return (
        "---\n"
        f"name: civil-buddy\n"
        f"description: {_yaml_str(desc)}\n"
        "---\n\n"
        + body
    )


def _write_tree(root: Path, files: dict[str, str]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    want = set(files)
    if root.is_dir():
        for child in list(root.iterdir()):
            if child.is_dir() and child.name not in want and child.name != "README.md":
                skill = child / "SKILL.md"
                if skill.is_file():
                    skill.unlink()
                try:
                    child.rmdir()
                except OSError:
                    pass
    for name, text in files.items():
        d = root / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "SKILL.md").write_text(text, encoding="utf-8", newline="\n")


def main() -> int:
    assert len(EXPERTS) == 66, len(EXPERTS)
    exclusive_map = _exclusive_map()
    files = {e.id: render_expert(e, exclusive_map.get(e.id) or []) for e in EXPERTS}
    files["civil-buddy"] = render_router()
    _write_tree(AGENTS_DIR, files)
    _write_tree(CODEX_DIR, files)
    readme = """# Expert skills (Codex / Agent Skills)

Each workbench expert is a skill:

- `.agents/skills/<id>/SKILL.md` — current Codex scan path
- `.codex/skills/<id>/SKILL.md` — same files, older repo-scoped path

Regenerate:

```
python scripts/build_codex_expert_skills.py
```

Do not put 66 personalities into `skills/civil-buddy/SKILL.md`. That file is the Grok `/civil-buddy` SOP router.
"""
    (ROOT / ".agents" / "README.md").write_text(readme, encoding="utf-8", newline="\n")
    (ROOT / ".codex" / "README.md").write_text(readme, encoding="utf-8", newline="\n")
    print(f"PASS wrote {len(EXPERTS)} expert skills + router → {AGENTS_DIR} and {CODEX_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
