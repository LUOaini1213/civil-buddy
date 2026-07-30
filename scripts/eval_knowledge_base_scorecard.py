#!/usr/bin/env python3
"""知识库七维分卡 → 目标各维 ≥9.5、综合 ≥9.5。"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
KB = ROOT / "knowledge_base"
OUT = ROOT / "output" / "kb"

FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def clamp(x: float, lo=0.0, hi=10.0) -> float:
    return max(lo, min(hi, x))


def parse_fm(raw: str) -> dict:
    m = FM_RE.match(raw)
    if not m:
        return {}
    meta = {}
    for line in m.group(1).splitlines():
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        meta[k.strip()] = v.strip().strip("\"'")
    return meta


def main() -> int:
    mds = list(KB.rglob("*.md"))
    n = len(mds)
    with_fm = 0
    full_fm = 0  # updated+harness+status
    for p in mds:
        raw = p.read_text(encoding="utf-8")
        meta = parse_fm(raw)
        if meta:
            with_fm += 1
        if all(k in meta for k in ("updated", "harness", "status")):
            full_fm += 1

    fm_rate = full_fm / n if n else 0.0

    # INDEX coverage
    idx = (KB / "INDEX.yaml").read_text(encoding="utf-8") if (KB / "INDEX.yaml").exists() else ""
    idx_paths = set(re.findall(r"path:\s*(\S+)", idx))
    md_rels = {p.relative_to(KB).as_posix() for p in mds}
    covered = len(md_rels & idx_paths) if idx_paths else 0
    doc_count_idx = len(re.findall(r"^\s*-\s*path:", idx, re.M))
    idx_cov = (covered / n) if n else 0.0
    if doc_count_idx >= n * 0.95:
        idx_cov = max(idx_cov, min(1.0, doc_count_idx / n))

    # trajectories with tool+args+obs
    traj_dir = KB / "03_trajectories"
    traj_files = [
        p
        for p in traj_dir.rglob("*.md")
        if p.name.upper() != "README.MD"
    ]
    complete_traj = 0
    for p in traj_files:
        t = p.read_text(encoding="utf-8")
        if "tool:" in t and "args:" in t and "observation:" in t:
            complete_traj += 1
    traj_score = clamp(10.0 * min(1.0, complete_traj / 8.0) * (0.85 + 0.15 * min(1, complete_traj / 8)))

    # tools catalog coverage (high tools)
    from packing_assistant.tool_registry import TOOL_CATALOG, get_tool

    tool_mds = list((KB / "02_tools").glob("*.md"))
    tool_text = "\n".join(p.read_text(encoding="utf-8") for p in tool_mds)
    hit = 0
    for t in TOOL_CATALOG:
        key = t.id.split(".")[-1]
        if t.id in tool_text or key in tool_text or t.name in tool_text:
            hit += 1
    tool_cov = hit / len(TOOL_CATALOG) if TOOL_CATALOG else 0.0

    # narrative redline
    safety = (KB / "01_rules" / "ctu_loading" / "safety_redlines.md")
    illegal = KB / "05_multi_agent" / "illegal_tools.md"
    narrative_ok = safety.exists() and (
        "坐标" in safety.read_text(encoding="utf-8")
        or "xyz" in safety.read_text(encoding="utf-8").lower()
    )
    narrative_ok = narrative_ok and illegal.exists()

    # README division
    readme = (KB / "README.md").read_text(encoding="utf-8") if (KB / "README.md").exists() else ""
    division_ok = "MySQL" in readme and "knowledge_base" in readme

    # multi-agent protocol files
    ma_need = [
        "roles_definition.md",
        "summary_protocol.md",
        "escalation_rules.md",
        "illegal_tools.md",
        "sequence_happy_path.md",
    ]
    ma_ok = sum(1 for x in ma_need if (KB / "05_multi_agent" / x).exists()) / len(ma_need)

    # competition mirror
    ex = (KB / "06_competition" / "example_tasks.md").read_text(encoding="utf-8")
    comp_ok = "t80" in ex and "T1" in ex and "phase0" in ex.lower()

    # retrieval
    recall = 0.0
    reg_ok = get_tool("knowledge.search") is not None
    try:
        golden = json.loads((ROOT / "test" / "kb" / "rag_golden.json").read_text(encoding="utf-8"))
        from packing_assistant.tools.search_knowledge import search_knowledge

        ok_n = 0
        for it in golden["items"]:
            res = search_knowledge(it["q"], limit=3)
            paths = [h["path"] for h in res.get("hits") or []]
            if any(e in paths for e in it["expect_paths"]):
                ok_n += 1
        recall = ok_n / len(golden["items"]) if golden["items"] else 0.0
    except Exception as e:
        print("retrieval eval error:", e)
        recall = 0.0

    # high rules present
    high_rules = list((KB / "01_rules").rglob("*.md"))
    rules_ok = len(high_rules) >= 7

    # content depth: avg lines for high priority files
    high_lines = []
    for p in mds:
        raw = p.read_text(encoding="utf-8")
        meta = parse_fm(raw)
        if meta.get("priority") == "high":
            high_lines.append(len(raw.splitlines()))
    avg_high = sum(high_lines) / len(high_lines) if high_lines else 0

    # --- dimension scores ---
    # α 架构
    arch = 7.0 + 2.5 * ma_ok + (0.5 if division_ok else 0)
    arch = clamp(arch)

    # α 叙事
    narr = 8.0 + (1.0 if narrative_ok else 0) + (0.5 if reg_ok else 0)
    narr = clamp(narr)

    # β 元数据
    meta_s = 4.0 + 4.0 * fm_rate + 2.0 * min(1.0, idx_cov)
    meta_s = clamp(meta_s)

    # β 内容：规则齐全 + 信息密度 + 工具目录对齐（不鼓励灌水）
    content = 5.0
    if rules_ok:
        content += 1.5
    if avg_high >= 35:
        content += 1.0
    if avg_high >= 50:
        content += 0.5
    content += 2.0 * min(1.0, tool_cov)
    if complete_traj >= 8:
        content += 0.5
    content = clamp(content)

    # β 检索
    retr = 2.0 + (1.0 if reg_ok else 0) + 7.0 * recall
    retr = clamp(retr)

    # γ 比赛
    comp = 7.0 + (1.5 if comp_ok else 0) + (1.0 if (KB / "06_competition" / "scoring_criteria.md").exists() else 0)
    comp = clamp(comp)

    # γ 轨迹
    traj = traj_score

    dims = {
        "架构分层": round(arch, 2),
        "叙事对齐": round(narr, 2),
        "元数据": round(meta_s, 2),
        "内容深度": round(content, 2),
        "检索落地": round(retr, 2),
        "比赛对齐": round(comp, 2),
        "轨迹可用": round(traj, 2),
    }
    # weighted overall (plan weights roughly equal)
    overall = sum(dims.values()) / len(dims)

    lines = [
        "# Knowledge Base Scorecard",
        "",
        f"- docs: {n}",
        f"- frontmatter complete: {full_fm}/{n} ({fm_rate:.1%})",
        f"- INDEX document entries: {doc_count_idx}",
        f"- complete trajectories (tool+args+obs): {complete_traj}",
        f"- TOOL_CATALOG mention coverage: {hit}/{len(TOOL_CATALOG)} ({tool_cov:.1%})",
        f"- Recall@3: {recall:.3f}",
        f"- knowledge.search registered: {reg_ok}",
        f"- avg lines (priority=high): {avg_high:.1f}",
        "",
        "## Dimensions (target ≥9.5 each)",
        "",
        "| 维度 | 分数 |",
        "|------|------|",
    ]
    for k, v in dims.items():
        flag = "OK" if v >= 9.5 else "GAP"
        lines.append(f"| {k} | {v} {flag} |")
    lines += [
        "",
        f"**综合**: {overall:.2f} " + ("PASS ≥9.5" if overall >= 9.5 else "FAIL <9.5"),
        "",
        "## Rubric notes",
        "- 检索: registry + golden Recall@3",
        "- 轨迹: ≥8 条含 tool/args/observation",
        "- 元数据: updated/harness/status + INDEX",
        "- 叙事: safety_redlines + illegal_tools",
        "",
    ]
    report = "\n".join(lines)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "SCORECARD.md").write_text(report, encoding="utf-8")
    print(report)

    # pass if overall >= 9.5 and no dim < 9.0 (strict: all >= 9.5)
    if overall < 9.5 or any(v < 9.5 for v in dims.values()):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
