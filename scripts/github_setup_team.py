#!/usr/bin/env python3
"""
在 GitHub 仓库创建 labels + 分活 Issues。

前置：
  1) 安装 GitHub CLI: https://cli.github.com/
  2) gh auth login
  3) 当前目录为仓库根，remote 指向 packing-agent

用法：
  python scripts/github_setup_team.py
  python scripts/github_setup_team.py --dry-run
  python scripts/github_setup_team.py --repo LUOaini1213/packing-agent
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple


LABELS: List[Tuple[str, str, str]] = [
    ("phase1", "1D76DB", "阶段1 装箱/结构/材料"),
    ("phase2", "0E8A16", "阶段2 装载/风险/三视图"),
    ("orchestrator", "5319E7", "主控与联调"),
    ("priority-p0", "B60205", "本周必须"),
    ("priority-p1", "FBCA04", "重要"),
    ("priority-p2", "C5DEF5", "可延后"),
    ("bug", "D73A4A", "缺陷"),
    ("docs", "0075CA", "文档"),
]

ISSUES: List[Dict[str, Any]] = [
    # phase1
    {
        "title": "P1-01 [P0] 校准箱型库与现场铁架参数",
        "labels": ["phase1", "priority-p0"],
        "body": """## 角色
阶段1

## 路径
`knowledge/packing_knowledge_base.json`

## 任务
对照现场 1.1/2/4/6 米铁架、铁笼：外廓、自重、最大载荷、别名。

## 验收
- 与装货单箱型名称/尺寸误差可接受
- `python scripts/run_excel_tests.py --only syn_` 通过
""",
    },
    {
        "title": "P1-02 [P0] 尺寸覆盖 dims_override 补齐高频件",
        "labels": ["phase1", "priority-p0"],
        "body": """## 角色
阶段1

## 路径
`knowledge/dims_override.json`、`tools/dims_override.py`

## 任务
为远东高频件配置 length/width/height 覆盖，减少估算尺寸。

## 验收
关键件 `dims_estimated=false` 或来源为 override。
""",
    },
    {
        "title": "P1-03 [P0] 结构结论业务口径文档",
        "labels": ["phase1", "docs", "priority-p0"],
        "body": """## 角色
阶段1 + 结构同事

## 任务
写清：通过 / 需加强 / 不通过 的判定与现场动作；对齐 `structure_calc`。

## 验收
5～10 个真实箱结论无争议；文档进 `docs/`。
""",
    },
    {
        "title": "P1-04 [P0] boxes[] 契约冻结检查",
        "labels": ["phase1", "phase2", "priority-p0"],
        "body": """## 角色
阶段1 + 阶段2

## 路径
`docs/api-spec.md`、`adapters.py`

## 验收
阶段2 仅凭 `boxes[]` 可装柜；字段变更必须 PR 说明并 @ 对方。
""",
    },
    {
        "title": "P1-05 [P1] 确认页六区 UI / 展示",
        "labels": ["phase1", "priority-p1"],
        "body": """## 参考
`docs/team-a-user-output-template.md`

## 验收
材料表、箱明细、结构、建议柜型、确认/修改/取消齐全。
""",
    },
    {
        "title": "P1-06 [P1] PDF 装箱单解析边界",
        "labels": ["phase1", "priority-p1"],
        "body": """## 路径
`tools/packing_list_parser.py`、`test/*.pdf`

## 验收
`python scripts/run_test_shipments.py` 材料行完整、少漏少重。
""",
    },
    {
        "title": "P1-07 [P1] Excel 业务集维护",
        "labels": ["phase1", "priority-p1"],
        "body": """## 路径
`scripts/build_steel_test_set.py`、`test/excel/`

## 验收
`python scripts/run_excel_tests.py` 全绿。
""",
    },
    {
        "title": "P1-08 [P2] 结构计算书导出",
        "labels": ["phase1", "priority-p2"],
        "body": """## 任务
将 `calc_report_md` 导出 Word/PDF。

## 验收
单箱可导出给现场。
""",
    },
    # phase2
    {
        "title": "P2-01 [P0] 装载策略调参（并排/二层/COG）",
        "labels": ["phase2", "priority-p0"],
        "body": """## 路径
`tools/bin3d.py`、`agents/planner.py`

## 验收
真实箱单尽量 1 柜装下；COG 规则符合业务。
""",
    },
    {
        "title": "P2-02 [P0] 三视图 Vue 打磨",
        "labels": ["phase2", "priority-p0"],
        "body": """## 路径
`frontend/index.html`、`agents/visualizer.py`

## 验收
缩放、分柜、图例清晰；可演示。
""",
    },
    {
        "title": "P2-03 [P0] 与阶段1 boxes 联调",
        "labels": ["phase2", "phase1", "priority-p0"],
        "body": """## 验收
阶段1 导出 boxes JSON → 阶段2 只喂 boxes 跑通装柜与三视图。
""",
    },
    {
        "title": "P2-04 [P1] skjolber 服务联调（有 JDK 时）",
        "labels": ["phase2", "priority-p1"],
        "body": """## 路径
`skjolber-service/`、`SKJOLBER_URL`

## 验收
health + pack；与 python-laff-3d 对照记录。
""",
    },
    {
        "title": "P2-05 [P1] 评估/风险阈值对齐业务",
        "labels": ["phase2", "priority-p1"],
        "body": """## 路径
`evaluator.py`、`risk_compliance.py`、`knowledge/`

## 验收
空隙/偏心/重量阈值有业务确认记录。
""",
    },
    {
        "title": "P2-06 [P1] 装柜报表导出",
        "labels": ["phase2", "priority-p1"],
        "body": """## 验收
layout + 利用率 + 绑扎建议表可导出。
""",
    },
    {
        "title": "P2-07 [P2] replan 闭环验证",
        "labels": ["phase2", "priority-p2"],
        "body": """## 路径
evaluator → planner 回路

## 验收
装不下时自动加柜/改策略可演示。
""",
    },
    # orchestrator
    {
        "title": "O-01 [P0] 端到端演示脚本固定",
        "labels": ["orchestrator", "priority-p0"],
        "body": """## 路径
`gateway/`、`main.py`、`scripts/run_test_shipments.py`

## 验收
一条命令完成 PDF→报告；答辩可用。
""",
    },
    {
        "title": "O-02 [P1] 主控选柜 UI 展示",
        "labels": ["orchestrator", "priority-p1"],
        "body": """## 验收
开头推荐柜型 + 结尾是否建议换柜 在前端可见。
""",
    },
    {
        "title": "O-03 [P0] 保护 main + PR 规范",
        "labels": ["docs", "priority-p0", "orchestrator"],
        "body": """## 任务
Settings → Branch protection：main 必须 PR。
向队友宣贯：分支命名、禁止提交 Key。

## 验收
队友均走 PR 合入。
""",
    },
]


def run(cmd: List[str]) -> Tuple[int, str, str]:
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode, p.stdout.strip(), p.stderr.strip()


def ensure_gh() -> None:
    code, out, err = run(["gh", "auth", "status"])
    if code != 0:
        print("请先安装并登录 GitHub CLI：")
        print("  winget install --id GitHub.cli -e")
        print("  gh auth login")
        print(err or out)
        sys.exit(1)


def existing_issue_titles(repo: str) -> set:
    code, out, err = run(
        ["gh", "issue", "list", "--repo", repo, "--limit", "200", "--json", "title"]
    )
    if code != 0:
        print("列出 issue 失败:", err or out)
        return set()
    try:
        data = json.loads(out or "[]")
        return {x.get("title") or "" for x in data}
    except json.JSONDecodeError:
        return set()


def create_labels(repo: str, dry: bool) -> None:
    for name, color, desc in LABELS:
        if dry:
            print(f"[dry-run] label {name}")
            continue
        code, out, err = run(
            [
                "gh",
                "label",
                "create",
                name,
                "--repo",
                repo,
                "--color",
                color,
                "--description",
                desc,
                "--force",
            ]
        )
        # --force may not exist on old gh; fallback create/edit
        if code != 0:
            run(
                [
                    "gh",
                    "label",
                    "create",
                    name,
                    "--repo",
                    repo,
                    "--color",
                    color,
                    "--description",
                    desc,
                ]
            )
        print(f"label ok: {name}")


def create_issues(repo: str, dry: bool) -> None:
    have = existing_issue_titles(repo) if not dry else set()
    for issue in ISSUES:
        title = issue["title"]
        if title in have:
            print(f"skip exists: {title}")
            continue
        if dry:
            print(f"[dry-run] issue {title}")
            continue
        cmd = [
            "gh",
            "issue",
            "create",
            "--repo",
            repo,
            "--title",
            title,
            "--body",
            issue["body"],
        ]
        for lb in issue.get("labels") or []:
            cmd.extend(["--label", lb])
        code, out, err = run(cmd)
        if code != 0:
            # labels may not exist yet
            print("create failed, retry without missing labels:", err or out)
            cmd2 = [
                "gh",
                "issue",
                "create",
                "--repo",
                repo,
                "--title",
                title,
                "--body",
                issue["body"],
            ]
            code, out, err = run(cmd2)
        print("created:" if code == 0 else "FAIL:", title, out or err)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default="LUOaini1213/packing-agent")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not args.dry_run:
        ensure_gh()
    else:
        print("dry-run mode (no gh required for listing plans)")

    print("== labels ==")
    create_labels(args.repo, args.dry_run)
    print("== issues ==")
    create_issues(args.repo, args.dry_run)
    print("DONE")
    print(f"打开: https://github.com/{args.repo}/issues")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
