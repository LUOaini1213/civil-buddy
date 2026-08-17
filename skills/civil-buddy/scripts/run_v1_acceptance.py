"""Mechanical V1 check: fictional TEMP pack → draft + docx + scan/validate."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from paths import SKILL_ROOT, TEMPLATE_DEFAULT, validate_py

SAMPLE = SKILL_ROOT / "examples" / "sample-cn-project.md"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main() -> int:
    temp = Path(os.environ.get("TEMP") or os.environ.get("TMP") or ".")
    root = temp / "civil-buddy-v1-验收" / "job"
    if "layout" in str(root).replace("/", "\\").lower():
        sys.stderr.write("refusing to use a path that looks like D:\\layout\n")
        return 2
    if root.exists():
        shutil.rmtree(root)
    pack_dir = root / ".civil-buddy"
    out_dir = pack_dir / "out" / "2026-08-13T15-04-05"
    out_dir.mkdir(parents=True)
    shutil.copy2(SAMPLE, pack_dir / "project.md")
    _write(
        pack_dir / "codes.md",
        "建筑施工高处作业安全技术规范 | UNAVAILABLE | UNAVAILABLE\n"
        "建筑施工安全检查标准 | UNAVAILABLE | UNAVAILABLE\n",
    )
    _write(
        out_dir / "draft.md",
        """# 专项施工方案讨论提纲（AI 草稿）

## 3 工程概况
工程名称：虚构滨河路人行道维修。范围见 project pack：虚构省虚构市滨河路 K0+120～K0+180（非真实路段）。
单位工程：edge-protect 人行道临边与检查井洞口防护。无正式施工图。临边高度见 [A001]。

## 5 施工部署与工艺
作业部位待用户指定。部署原则只写讨论提纲：先封闭临边，再处理检查井洞口。具体步距、杆件规格见 [A001] [A002]。

## 6 质量
质量检查表骨架待填。不编允许偏差。

## 7 安全与应急
临边与洞口防护的栏杆高度、水平荷载、踢脚板高度均无用户或 PDF 来源，整节待填 [A001]。禁止将本段理解为验算结论。应急联络人以现场持证人员签认为准。

## 8 环保与文明施工
扬尘与废弃物去向未提供，列待填。

## 9 资源计划
人工 | 材料 | 机具
TBD | TBD | TBD

## 10 验收与资料
只列资料目录骨架，不给合格结论：方案讨论记录、交底草稿、检查表。

## 11 附录
用户图号清单为空，不引用图号。无计算摘录。
""",
    )
    _write(
        out_dir / "assumptions.md",
        """> A001
> 内容: 临边高度未由用户或图纸给出
> 原因: project pack 与用户消息均无高度
> Owner: user
> 影响: 栏杆选型与验算整节保持待填

> A002
> 内容: 检查井洞口平面尺寸未提供
> 原因: 无正式施工图
> Owner: user
> 影响: 洞口盖板与护栏布置待填
""",
    )
    _write(
        out_dir / "citations.md",
        """## 已核实

## 未核实
全名 | 年份 | 条款 | 状态
建筑施工高处作业安全技术规范 | UNAVAILABLE | UNSPECIFIED | unverified
建筑施工安全检查标准 | UNAVAILABLE | UNSPECIFIED | unverified
""",
    )

    if not TEMPLATE_DEFAULT.is_file():
        subprocess.check_call([sys.executable, str(SKILL_ROOT / "scripts" / "build_scheme_template.py")])

    fill = [
        sys.executable,
        str(SKILL_ROOT / "scripts" / "fill_scheme_template.py"),
        "--template",
        str(TEMPLATE_DEFAULT),
        "--draft",
        str(out_dir / "draft.md"),
        "--assumptions",
        str(out_dir / "assumptions.md"),
        "--citations",
        str(out_dir / "citations.md"),
        "--jurisdiction",
        "CN",
        "--stamp",
        "2026-08-13T15-04-05",
        "--project-name",
        "虚构滨河路人行道维修",
        "--short-name",
        "滨河维修",
        "--out",
        str(out_dir / "专项施工方案-AI草稿.docx"),
    ]
    print("fill", *fill)
    subprocess.check_call(fill)
    subprocess.check_call([sys.executable, str(validate_py()), str(out_dir / "专项施工方案-AI草稿.docx")])
    subprocess.check_call(
        [
            sys.executable,
            str(SKILL_ROOT / "scripts" / "scan_forbidden_inventions.py"),
            "--draft",
            str(out_dir / "draft.md"),
            "--docx",
            str(out_dir / "专项施工方案-AI草稿.docx"),
            "--citations",
            str(out_dir / "citations.md"),
            "--jurisdiction",
            "CN",
        ]
    )
    subprocess.check_call(
        [
            sys.executable,
            str(SKILL_ROOT / "scripts" / "assert_outdir_only.py"),
            "--root",
            str(root),
            "--out-dir",
            str(out_dir),
        ]
    )
    print("V1 acceptance OK", out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
