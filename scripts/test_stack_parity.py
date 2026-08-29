#!/usr/bin/env python3
"""三栈 parity 守卫：Python 运行时 / Rust 工作台 / SKILL.md 镜像 不得手工漂移。

项目原则 "tools compute numbers; the model only routes" 依赖三套并行实现保持同义。
意图词表已单源化：唯一真源 = contract/intents.v1.json（见 contract/README.md），
两侧代码只是消费者。本脚本断言四组关系（脚本式断言风格，退出码：全过=0，任何漂移=1）：

1) 契约与双栈接线：contract/intents.v1.json schema 完整；
   packing_assistant/understand.py 与 packing_assistant/runtime/expert_skills.py 的词表常量
   必须是契约加载调用（contract_list/contract_strong/contract_pack_action_en_pattern），
   且不得再内联词表字面量（残留判定：模块级 ≥2 个契约词组的字符串元组/列表）；
   workbench/src/agent.rs 必须 include_str! 契约文件，且无内联词表数组
   （残留判定：≥2 个契约词组的字符串数组字面量）、无旧 PACK_SHIP 子集；
   英文 pack 判定两侧机制不同（Python 正则 \\bpack\\b，Rust 切词 eq_ignore_ascii_case），
   以成对锚点注释 `# parity:pack-action-en` / `// parity:pack-action-en` 相互引用。

2) 行为金句：test/eval/intents_golden.json（≥15 条中英混合）冻结了 (text → intent, skill)
   基线；Python 侧在此实跑 understand()+match_skill() 断言；并断言每个金句的选岗都能由
   strong_match 全表首命中复现（Rust match_skill_implicit 是 strong-only，两侧金句才能同源）。
   Rust 侧行为由 workbench/tests/intents_golden.rs 用同一份金句实跑（cargo test）。

3) SKILL.md 镜像：.agents/skills 与 .codex/skills 由 scripts/build_codex_expert_skills.py
   从 catalog_seed / yibiao-map / demo/kb 单源生成，两侧逐文件一致、目录集合一致，
   且 .agents（canonical）与生成器现输出一致（防两侧同时手改）。

4) 名册单源：demo/catalog_seed.py（66 岗）与 workbench/seed.json 的 id+name 一致。
"""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DRIFTS: list[str] = []

PY_ANCHOR = "# parity:pack-action-en"
RS_ANCHOR = "// parity:pack-action-en"
CONTRACT_JSON = ROOT / "contract" / "intents.v1.json"
GOLDEN_JSON = ROOT / "test" / "eval" / "intents_golden.json"
INCLUDE_STR_LITERAL = 'include_str!("../../contract/intents.v1.json")'

UNDERSTAND_PY = ROOT / "packing_assistant" / "understand.py"
EXPERT_SKILLS_PY = ROOT / "packing_assistant" / "runtime" / "expert_skills.py"
AGENT_RS = ROOT / "workbench" / "src" / "agent.rs"
AGENTS_SKILLS = ROOT / ".agents" / "skills"
CODEX_SKILLS = ROOT / ".codex" / "skills"
SEED_JSON = ROOT / "workbench" / "seed.json"

LIST_KEYS = ("pack_action_zh", "packish", "phrase_write", "write_nouns", "ask", "tender")
PY_CONST_TO_KEY = [
    ("_PACKISH", "packish"),
    ("_PACK_ACTION_ZH", "pack_action_zh"),
    ("_PHRASE_WRITE", "phrase_write"),
    ("_WRITE_NOUNS", "write_nouns"),
    ("_ASK", "ask"),
    ("_TENDER", "tender"),
]


def drift(msg: str) -> None:
    DRIFTS.append(msg)


def load_contract() -> dict | None:
    if not CONTRACT_JSON.is_file():
        drift(f"契约文件缺失: {CONTRACT_JSON}（唯一真源必须存在）")
        return None
    try:
        data = json.loads(CONTRACT_JSON.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        drift(f"契约文件不可读或非法 JSON: {e}")
        return None
    if not isinstance(data, dict):
        drift("契约顶层必须是 JSON 对象")
        return None
    return data


# ---------- 1) 契约 schema 与双栈接线 ----------

def check_contract_schema(data: dict) -> None:
    if data.get("version") != "1":
        drift(f"契约 version 预期 '1'，实为 {data.get('version')!r}")
    for key in LIST_KEYS:
        vals = data.get(key)
        if (
            not isinstance(vals, list)
            or not vals
            or not all(isinstance(v, str) and v for v in vals)
        ):
            drift(f"契约 {key} 必须是非空字符串数组，实为 {vals!r}")
    strong = data.get("strong_match")
    if not isinstance(strong, list) or not strong:
        drift(f"契约 strong_match 必须是非空 [phrase, expert_id] 数组，实为 {strong!r}")
        return
    for i, item in enumerate(strong):
        if (
            not isinstance(item, list)
            or len(item) != 2
            or not all(isinstance(x, str) and x for x in item)
        ):
            drift(f"契约 strong_match[{i}] 必须是 [phrase, expert_id]，实为 {item!r}")
    pack_en = data.get("pack_action_en")
    if not isinstance(pack_en, dict):
        drift("契约 pack_action_en 必须是对象")
        return
    if pack_en.get("python") != r"\bpack\b":
        drift(f"契约 pack_action_en.python 预期 \\bpack\\b，实为 {pack_en.get('python')!r}")
    if pack_en.get("rust") != "word_equals_pack":
        drift(f"契约 pack_action_en.rust 预期 word_equals_pack，实为 {pack_en.get('rust')!r}")


def contract_vocab(data: dict) -> set[str]:
    """全部契约词组（含 strong 短语），用于残留内联检查。"""
    vocab: set[str] = set()
    for key in LIST_KEYS:
        vals = data.get(key)
        if isinstance(vals, list):
            vocab.update(v for v in vals if isinstance(v, str))
    strong = data.get("strong_match")
    if isinstance(strong, list):
        for item in strong:
            if isinstance(item, list) and len(item) == 2 and isinstance(item[0], str):
                vocab.add(item[0])
    return vocab


def python_string_tuples(tree: ast.Module) -> list[tuple[str, ...]]:
    """模块级赋值中元素全为 str 字面量的 tuple/list（潜在内联词表形状）。"""
    out: list[tuple[str, ...]] = []
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            value = node.value
            if isinstance(value, (ast.Tuple, ast.List)):
                try:
                    vals = tuple(ast.literal_eval(value))
                except ValueError:
                    continue
                if len(vals) >= 2 and all(isinstance(v, str) for v in vals):
                    out.append(vals)
    return out


def check_python_wiring(data: dict) -> None:
    for path, strong_const in ((UNDERSTAND_PY, None), (EXPERT_SKILLS_PY, "_STRONG")):
        src = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(src)
        except SyntaxError as e:
            drift(f"{path.name} 无法解析: {e}")
            continue

        def call_name(value: ast.AST) -> str:
            if isinstance(value, ast.Call) and isinstance(value.func, ast.Name):
                return value.func.id
            return ""

        for const, key in PY_CONST_TO_KEY:
            found = False
            for node in tree.body:
                if not (isinstance(node, ast.Assign) and any(
                    isinstance(t, ast.Name) and t.id == const for t in node.targets
                )):
                    continue
                found = True
                if call_name(node.value) != "contract_list":
                    drift(
                        f"{path.name} {const} 必须从契约加载（= contract_list({key!r})），"
                        "不得内联词表"
                    )
                    break
                arg = node.value.args[0] if node.value.args else None
                if not (isinstance(arg, ast.Constant) and arg.value == key):
                    drift(f"{path.name} {const} 契约键预期 {key!r}，实为 {ast.dump(arg)}")
                break
            if not found and path == UNDERSTAND_PY:
                drift(f"{path.name} 缺少契约接线常量 {const} = contract_list(...)")

        if strong_const:
            hit = any(
                isinstance(node, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == strong_const for t in node.targets)
                and call_name(node.value) == "contract_strong"
                for node in tree.body
            )
            if not hit:
                drift(f"{path.name} {strong_const} 必须从契约加载（= contract_strong()）")

        # 残留内联：模块级 ≥2 个契约词组的字符串元组/列表
        vocab = contract_vocab(data)
        for vals in python_string_tuples(tree):
            overl = [v for v in vals if v in vocab]
            if len(overl) >= 2:
                drift(f"{path.name} 残留内联词表字面量 {vals[:4]}…（唯一真源是 contract/）")

    if UNDERSTAND_PY.exists():
        py_src = UNDERSTAND_PY.read_text(encoding="utf-8")
        if py_src.count(PY_ANCHOR) != 1:
            drift(f"understand.py 锚点注释 {PY_ANCHOR!r} 须恰 1 处（与 agent.rs 成对）")
        # _PACK_ACTION_EN 必须编译自契约模式（contract_pack_action_en_pattern()）
        try:
            tree = ast.parse(py_src)
        except SyntaxError:
            return
        en_ok = False
        for node in tree.body:
            if not (isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "_PACK_ACTION_EN" for t in node.targets
            )):
                continue
            v = node.value
            en_ok = (
                isinstance(v, ast.Call)
                and isinstance(v.func, ast.Attribute)
                and v.func.attr == "compile"
                and v.args
                and call_name(v.args[0]) == "contract_pack_action_en_pattern"
            )
        if not en_ok:
            drift(
                "understand.py _PACK_ACTION_EN 必须 = re.compile(contract_pack_action_en_pattern(), "
                "re.IGNORECASE)（英文 pack 模式来自契约 pack_action_en.python）"
            )


def rust_string_arrays(src: str) -> list[list[str]]:
    """源码中所有平衡 [...] 且首元素为字符串字面量的段（潜在内联词表数组）。"""
    out: list[list[str]] = []
    for m in re.finditer(r"\[", src):
        j = m.start()
        rest = src[j + 1 :].lstrip()
        if not rest.startswith('"'):
            continue  # 类型注解等非字符串数组
        depth = 0
        for k in range(j, len(src)):
            if src[k] == "[":
                depth += 1
            elif src[k] == "]":
                depth -= 1
                if depth == 0:
                    seg = src[j : k + 1]
                    out.append(
                        [m2.group(1) for m2 in re.finditer(r'"((?:[^"\\]|\\.)*)"', seg)]
                    )
                    break
        else:
            continue
    return out


def check_rust_wiring(data: dict) -> None:
    if not AGENT_RS.is_file():
        drift(f"agent.rs 缺失: {AGENT_RS}")
        return
    src = AGENT_RS.read_text(encoding="utf-8")
    if INCLUDE_STR_LITERAL not in src:
        drift(f"agent.rs 未从契约加载词表（缺 {INCLUDE_STR_LITERAL}）")
    if src.count(RS_ANCHOR) != 1:
        drift(f"agent.rs 锚点注释 {RS_ANCHOR!r} 须恰 1 处（与 understand.py 成对）")
    if 'eq_ignore_ascii_case("pack")' not in src:
        drift('agent.rs 英文 pack 判定缺少 eq_ignore_ascii_case("pack")（切词实现被改动？）')
    if "const PACK_SHIP" in src:
        drift("agent.rs 残留旧 PACK_SHIP 子集（已升级为契约 strong_match 全表）")
    vocab = contract_vocab(data)
    for arr in rust_string_arrays(src):
        overl = [v for v in arr if v in vocab]
        if len(overl) >= 2:
            drift(f"agent.rs 残留内联词表数组 {overl[:4]}…（唯一真源是 contract/）")


# ---------- 2) 行为金句（Python 侧实跑） ----------

def strong_first_hit(strong: list, text: str) -> str | None:
    blob = (text or "").strip().lower()
    for item in strong:
        phrase, eid = item
        if phrase.lower() in blob:
            return eid
    return None


def check_golden(data: dict) -> None:
    if not GOLDEN_JSON.is_file():
        drift(f"金句文件缺失: {GOLDEN_JSON}")
        return
    try:
        golden = json.loads(GOLDEN_JSON.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        drift(f"金句文件不可读或非法 JSON: {e}")
        return
    cases = golden.get("cases")
    if not isinstance(cases, list) or len(cases) < 15:
        drift(f"金句 cases 须 ≥15 条，实为 {len(cases) if isinstance(cases, list) else '非数组'}")
        return
    strong = data.get("strong_match") or []
    sys.path.insert(0, str(ROOT))
    from packing_assistant.understand import understand  # noqa: E402
    from packing_assistant.runtime.expert_skills import match_skill  # noqa: E402

    for case in cases:
        text = case.get("text")
        want_i = case.get("intent")
        want_s = case.get("skill")
        if not isinstance(text, str) or not text:
            drift(f"金句 case 缺 text: {case!r}")
            continue
        got_i = understand(text)
        got_s = match_skill(text)
        if got_i != want_i:
            drift(f"金句 intent 漂移: {text!r} want={want_i!r} got={got_i!r}")
        if got_s != want_s:
            drift(f"金句 skill 漂移: {text!r} want={want_s!r} got={got_s!r}")
        # strong-only 兼容：Rust match_skill_implicit 只读 strong_match 全表，
        # 金句的选岗必须能由首命中复现（否则两侧金句无法同源）。
        if got_s != strong_first_hit(strong, text):
            drift(
                f"金句 {text!r} 的选岗 {got_s!r} 无法由 strong_match 首命中复现"
                f"（strong 首命中={strong_first_hit(strong, text)!r}）——"
                "Rust match_skill_implicit 将与 Python 金句不同源"
            )


# ---------- 3) SKILL.md 镜像 ----------

def read_tree(root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for p in sorted(root.rglob("*")):
        if p.is_file():
            out[p.relative_to(root).as_posix()] = p.read_text(encoding="utf-8")
    return out


def generator_output() -> dict[str, str]:
    sys.path.insert(0, str(ROOT / "scripts"))
    sys.path.insert(0, str(ROOT / "demo"))
    import build_codex_expert_skills as gen  # noqa: E402

    exclusive_map = gen._exclusive_map()
    files = {e.id: gen.render_expert(e, exclusive_map.get(e.id) or []) for e in gen.EXPERTS}
    files["civil-buddy"] = gen.render_router()
    return files


def check_skill_mirrors() -> None:
    if not AGENTS_SKILLS.is_dir() or not CODEX_SKILLS.is_dir():
        drift(f"镜像目录缺失：{AGENTS_SKILLS} / {CODEX_SKILLS}")
        return
    agents, codex = read_tree(AGENTS_SKILLS), read_tree(CODEX_SKILLS)
    only_a, only_c = sorted(set(agents) - set(codex)), sorted(set(codex) - set(agents))
    if only_a:
        drift(f".codex/skills 缺目录: {only_a}")
    if only_c:
        drift(f".agents/skills 缺目录: {only_c}")
    for rel in sorted(set(agents) & set(codex)):
        if agents[rel] != codex[rel]:
            drift(f"SKILL.md 镜像不一致: {rel}（.agents 与 .codex 内容不同）")

    # canonical 侧还须等于生成器现输出（防两侧被同时手改）。
    try:
        expected = generator_output()
    except Exception as e:  # noqa: BLE001
        drift(f"无法执行生成器比对（build_codex_expert_skills）：{e}")
        return
    for rel, want in sorted(expected.items()):
        got = agents.get(rel + "/SKILL.md")
        if got is None:
            drift(f".agents/skills 缺生成器产物: {rel}/SKILL.md")
        elif got != want:
            drift(
                f".agents/skills/{rel}/SKILL.md 与生成器输出不一致（疑似手改；"
                "请改 catalog_seed / KB_NOTES / demo/kb 后重跑 scripts/build_codex_expert_skills.py）"
            )
    extra = sorted(set(agents) - {r + "/SKILL.md" for r in expected})
    if extra:
        drift(f".agents/skills 存在生成器之外的文件: {extra}")


# ---------- 4) 名册单源 ----------

def check_roster() -> None:
    sys.path.insert(0, str(ROOT / "demo"))
    from catalog_seed import EXPERTS  # noqa: E402

    seed = json.loads(SEED_JSON.read_text(encoding="utf-8"))
    catalog = {e.id: e.name for e in EXPERTS}
    roster = {x["id"]: x.get("name") for x in seed.get("experts", [])}
    if len(catalog) != 66:
        drift(f"catalog_seed.EXPERTS 应 66 岗，实为 {len(catalog)}")
    if len(roster) != 66:
        drift(f"seed.json.experts 应 66 岗，实为 {len(roster)}")
    only_c, only_s = sorted(set(catalog) - set(roster)), sorted(set(roster) - set(catalog))
    if only_c:
        drift(f"seed.json 缺岗: {only_c}")
    if only_s:
        drift(f"seed.json 多岗: {only_s}")
    name_diff = {k: (catalog[k], roster[k]) for k in set(catalog) & set(roster) if catalog[k] != roster[k]}
    if name_diff:
        drift(f"catalog_seed vs seed.json 岗名不一致: {name_diff}")


def main() -> int:
    data = load_contract()
    golden_n = 0
    if data is not None:
        check_contract_schema(data)
        check_python_wiring(data)
        check_rust_wiring(data)
        check_golden(data)
        try:
            golden_n = len(json.loads(GOLDEN_JSON.read_text(encoding="utf-8")).get("cases") or [])
        except Exception:  # noqa: BLE001
            golden_n = 0
    check_skill_mirrors()
    check_roster()
    if DRIFTS:
        print("PARITY FAIL（三栈漂移 %d 处）:" % len(DRIFTS))
        for d in DRIFTS:
            print("  -", d)
        print(
            "修法：词表/接线漂移→改 contract/intents.v1.json 或对齐加载调用；"
            "金句漂移→确认新行为后同步 test/eval/intents_golden.json；"
            "镜像漂移→python scripts/build_codex_expert_skills.py"
        )
        return 1
    print(
        "PASS stack parity: contract(intents.v1.json schema + 双栈接线 understand.py/"
        f"expert_skills.py/agent.rs 无内联残留) + golden({golden_n} 金句 Python 实跑) "
        "+ mirrors(.agents==.codex==generator) + roster(catalog_seed==seed.json, 66 岗)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
