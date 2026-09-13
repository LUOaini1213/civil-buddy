#!/usr/bin/env python3
"""PDF 装箱单：接得上、认不出时要说人话、并且不许再依赖 AGPL 库。

三件事：
1. 文本抽取走 pypdf（BSD，requirements.txt 已声明），不是 fitz/PyMuPDF
   （AGPL，且从未进过依赖清单——按 requirements 干净安装的机器上会 ImportError，
   本仓又是 MIT）。
2. .pdf 能进解析入口，不再是 "unsupported table type"。
3. 行版式认不出来时，返回的是可执行的说明，不是安静的空结果——空结果会
   一路变成"这份单子没有货"。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

FIXTURE = ROOT / "test" / "fixtures" / "packing_list_generic_en.pdf"


def main():
    assert FIXTURE.exists(), f"缺少夹具: {FIXTURE}"

    # 1) 不许回到 fitz/PyMuPDF
    src = (ROOT / "packing_assistant" / "tools" / "packing_list_parser.py").read_text(
        encoding="utf-8"
    )
    imports = [ln.strip() for ln in src.splitlines()
               if ln.strip().startswith(("import ", "from ")) or ln.strip().startswith("    import ")]
    bad = [ln for ln in imports if "fitz" in ln or "pymupdf" in ln.lower()]
    assert not bad, f"不应 import fitz/PyMuPDF（AGPL，且不在 requirements）: {bad}"
    assert "from pypdf import" in src, "应使用 requirements 里声明的 pypdf"

    # 2) pypdf 真的能把文本抽出来
    from packing_assistant.tools.packing_list_parser import extract_pdf_text

    text = extract_pdf_text(FIXTURE)
    assert "PACKING LIST" in text, text[:200]
    assert len(text.splitlines()) >= 5, text[:200]

    # 3) .pdf 进得了解析入口（不再抛 unsupported table type）
    from packing_assistant.tools.table_mapper import load_table, parse_table_file

    rows = load_table(FIXTURE)
    assert isinstance(rows, list), rows

    # 4) 认不出版式时，错误要可执行
    parsed = parse_table_file(FIXTURE)
    assert parsed["ok"] is False, "这份通用英文版式目前解析不出行，不应报成功"
    assert parsed["errors"], parsed
    reason = parsed["errors"][0]
    assert "xlsx" in reason or "csv" in reason, f"错误应给出下一步做什么: {reason}"

    # 5) 这个错误要一路传到工具面，而不是变成一个空方案
    from packing_assistant.tools.pack_ship_solve import run_plan

    plan = run_plan(file_path=str(FIXTURE))
    assert plan["ok"] is False and plan["error"] == "no_materials", plan
    assert plan["detail"] and ("xlsx" in plan["detail"][0] or "csv" in plan["detail"][0]), plan

    print(
        f"PASS packing_list_pdf pypdf=yes fitz=no lines={len(text.splitlines())} "
        f"unknown_layout=actionable_error"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
