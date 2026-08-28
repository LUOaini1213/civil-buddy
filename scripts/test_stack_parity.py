#!/usr/bin/env python3
"""三栈 parity 守卫：Python 运行时 / Rust 工作台 / SKILL.md 镜像 不得手工漂移。

项目原则 "tools compute numbers; the model only routes" 依赖三套并行实现保持同义。
本脚本断言三组单源关系（脚本式断言风格，退出码：全过=0，任何漂移=1 并打印明细）：

1) 意图词表：packing_assistant/understand.py vs workbench/src/agent.rs understand()
   中文词表（_PACKISH/_PACK_ACTION_ZH/_PHRASE_WRITE/_WRITE_NOUNS/_ASK/_TENDER）集合相等；
   英文 pack 判定两侧机制不同（Python 正则 \\bpack\\b，Rust 切词 eq_ignore_ascii_case），
   以成对锚点注释 `# parity:pack-action-en` / `// parity:pack-action-en` 相互引用；
   另校验 agent.rs match_skill_implicit 的 pack-ship 词表 ⊇ runtime/expert_skills.py _STRONG。

2) SKILL.md 镜像：.agents/skills 与 .codex/skills 由 scripts/build_codex_expert_skills.py
   从 catalog_seed / yibiao-map / demo/kb 单源生成，两侧逐文件一致、目录集合一致，
   且 .agents（canonical）与生成器现输出一致（防两侧同时手改）。

3) 名册单源：demo/catalog_seed.py（66 岗）与 workbench/seed.json 的 id+name 一致。
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

UNDERSTAND_PY = ROOT / "packing_assistant" / "understand.py"
AGENT_RS = ROOT / "workbench" / "src" / "agent.rs"
EXPERT_SKILLS_PY = ROOT / "packing_assistant" / "runtime" / "expert_skills.py"
AGENTS_SKILLS = ROOT / ".agents" / "skills"
CODEX_SKILLS = ROOT / ".codex" / "skills"
SEED_JSON = ROOT / "workbench" / "seed.json"


def drift(msg: str) -> None:
    DRIFTS.append(msg)


def diff_detail(py: set, rs: set) -> str:
    only_py, only_rs = sorted(py - rs), sorted(rs - py)
    parts = []
    if only_py:
        parts.append("仅 Python 有: " + "、".join(only_py))
    if only_rs:
        parts.append("仅 Rust 有: " + "、".join(only_rs))
    return "；".join(parts)


# ---------- Python 侧（ast 解析，不触发包导入副作用） ----------

def python_vocab(path: Path) -> dict[str, tuple[str, ...]]:
    """提取模块级 tuple 常量（元素全为 str 字面量）。"""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out: dict[str, tuple[str, ...]] = {}
    for node in tree.body:
        if not (isinstance(node, ast.Assign) and isinstance(node.value, ast.Tuple)):
            continue
        names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        try:
            vals = tuple(ast.literal_eval(node.value))
        except ValueError:
            continue
        if all(isinstance(v, str) for v in vals):
            for n in names:
                out[n] = vals
    return out


def python_pack_en_regex(path: Path) -> str | None:
    """提取 _PACK_ACTION_EN = re.compile(r"...") 的模式串。"""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(t, ast.Name) and t.id == "_PACK_ACTION_EN" for t in node.targets):
            continue
        if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute):
            arg = node.value.args[0] if node.value.args else None
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                return arg.value
    return None


def python_strong_pack_ship(path: Path) -> set[str]:
    """expert_skills._STRONG 中路由到 pack-ship 的短语。"""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if not (isinstance(node, ast.Assign) and isinstance(node.value, ast.Tuple)):
            continue
        if not any(isinstance(t, ast.Name) and t.id == "_STRONG" for t in node.targets):
            continue
        out = set()
        for el in node.value.elts:
            if isinstance(el, ast.Tuple) and len(el.elts) == 2:
                phrase, eid = ast.literal_eval(el)
                if eid == "pack-ship":
                    out.add(phrase)
        return out
    raise AssertionError("_STRONG not found in " + str(path))


# ---------- Rust 侧（锚点定位 + 括号配对提取字符串字面量） ----------

def rust_segment_strings(src: str, anchor: str) -> list[str]:
    """anchor 后第一个元素为字符串字面量的平衡 [...] 段内的 "..." 字面量。

    跳过类型注解段（如 `const PACK_SHIP: &[&str] = &[...]` 的 &[&str]）。
    """
    i = src.find(anchor)
    if i < 0:
        raise AssertionError(f"agent.rs anchor not found: {anchor!r}")
    for j in (m.start() for m in re.finditer(r"\[", src[i:])):
        j += i
        rest = src[j + 1 :].lstrip()
        if not rest.startswith('"'):
            continue  # 非字符串数组（类型注解等），跳过
        depth = 0
        for k in range(j, len(src)):
            if src[k] == "[":
                depth += 1
            elif src[k] == "]":
                depth -= 1
                if depth == 0:
                    seg = src[j : k + 1]
                    return [m.group(1) for m in re.finditer(r'"((?:[^"\\]|\\.)*)"', seg)]
        raise AssertionError(f"unbalanced brackets after anchor: {anchor!r}")
    raise AssertionError(f"no string array after anchor: {anchor!r}")


def check_vocab_parity() -> None:
    py = python_vocab(UNDERSTAND_PY)
    rs_src = AGENT_RS.read_text(encoding="utf-8")

    # 成对锚点：英文 pack 判定两侧机制不同，靠注释锚点互相指认（缺任一即漂移）。
    py_src = UNDERSTAND_PY.read_text(encoding="utf-8")
    if py_src.count(PY_ANCHOR) != 1:
        drift(f"understand.py 缺少锚点注释 {PY_ANCHOR!r}（须恰 1 处，与 agent.rs 成对）")
    if rs_src.count(RS_ANCHOR) != 1:
        drift(f"agent.rs 缺少锚点注释 {RS_ANCHOR!r}（须恰 1 处，与 understand.py 成对）")

    pairs = [
        # (Python 常量名, Rust 锚点, 说明)
        ("_PACKISH", "fn is_packish", "packish 触发词"),
        ("_PACK_ACTION_ZH", "let pack_action", "pack 中文动作词"),
        ("_PHRASE_WRITE", "let phrase_write", "写-短语词表"),
        ("_WRITE_NOUNS", "let write = phrase_write", "写-名词词表"),
        ("_ASK", "let ask = has_any", "提问词表"),
        ("_TENDER", "let tender = has_any", "招标词表"),
    ]
    for const, anchor, label in pairs:
        py_set = set(py.get(const, ()))
        if not py_set:
            drift(f"understand.py 未解析到 {const}")
            continue
        try:
            rs_set = set(rust_segment_strings(rs_src, anchor))
        except AssertionError as e:
            drift(f"agent.rs 无法提取 {label}（锚点 {anchor!r}）：{e}")
            continue
        if py_set != rs_set:
            drift(f"意图词表漂移[{label} / {const}]：{diff_detail(py_set, rs_set)}")

    # 英文 pack：Python 侧必须是词边界正则；Rust 侧是切词判等（文本不可直接比对，靠锚点+此处 sanity）。
    pat = python_pack_en_regex(UNDERSTAND_PY)
    if pat != r"\bpack\b":
        drift(f"understand.py _PACK_ACTION_EN 预期正则 \\bpack\\b，实为 {pat!r}")
    if 'eq_ignore_ascii_case("pack")' not in rs_src:
        drift('agent.rs 英文 pack 判定缺少 eq_ignore_ascii_case("pack")（切词实现被改动？）')

    # match_skill_implicit 的 pack-ship 子集须覆盖 expert_skills._STRONG 的 pack-ship 短语
    #（"pack" 由切词规则覆盖，不在 Rust 数组内）。
    strong = python_strong_pack_ship(EXPERT_SKILLS_PY)
    try:
        rs_pack_ship = set(rust_segment_strings(rs_src, "const PACK_SHIP"))
    except AssertionError as e:
        drift(f"agent.rs 无法提取 PACK_SHIP：{e}")
        return
    missing = {p for p in strong if p != "pack" and p not in rs_pack_ship and p != "pack-ship"}
    if missing:
        drift(
            "match_skill_implicit 词表缺 expert_skills._STRONG 的 pack-ship 触发词: "
            + "、".join(sorted(missing))
        )


# ---------- SKILL.md 镜像 ----------

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


# ---------- 名册单源 ----------

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
    check_vocab_parity()
    check_skill_mirrors()
    check_roster()
    if DRIFTS:
        print("PARITY FAIL（三栈漂移 %d 处）:" % len(DRIFTS))
        for d in DRIFTS:
            print("  -", d)
        print("修法：词表漂移→对齐 understand.py/agent.rs；镜像漂移→python scripts/build_codex_expert_skills.py")
        return 1
    print(
        "PASS stack parity: vocab(understand.py==agent.rs) + mirrors(.agents==.codex==generator) "
        "+ roster(catalog_seed==seed.json, 66 岗)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
