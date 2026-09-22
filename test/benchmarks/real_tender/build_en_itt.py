#!/usr/bin/env python3
"""An English Invitation to Tender, made up, in the shape public works ITTs in Singapore come in: numbered SECTIONS
instead of 第X章, an "Appendix to the Instructions to Tenderers" as the front table (Item | Description | Particulars),
clauses that say "shall be rejected / disqualified / not be considered", an evaluation table of weights in per cent.

    python test/benchmarks/real_tender/build_en_itt.py
    python scripts/eval_real_document.py test/benchmarks/real_tender/en_itt.md --gold test/benchmarks/real_tender/en_itt.gold.json --word

Before this benchmark an English tender was read only through lines that carry a label ("Tender validity: 90 days").
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

CONDITIONS = "\n\n".join(
    f"{n}.{k} The Contractor shall submit the programme within {6 + n + k} days of the Letter of Acceptance. Liquidated damages of "
    f"S${300 * n + 50 * k} per day shall apply for every day of delay, up to {4 + k} per cent of the Contract Sum. The Superintending "
    f"Officer shall respond within {12 + n} days." for n in range(1, 12) for k in range(1, 5))


def tender() -> str:
    return f"""# INVITATION TO TENDER

# Proposed Upgrading of Covered Linkways and Drainage at Seletar North Estate

Tender Reference: TC-SNE-2029-044

TABLE OF CONTENTS

SECTION 1 INVITATION TO TENDER ........................................ 2
SECTION 2 INSTRUCTIONS TO TENDERERS ................................... 5
SECTION 3 EVALUATION CRITERIA ......................................... 14
SECTION 4 CONDITIONS OF CONTRACT ...................................... 18
SECTION 5 FORMS OF TENDER ............................................. 52

SECTION 1 INVITATION TO TENDER

1.1 Seletar North Town Council (the "Employer") invites tenders for the Proposed Upgrading of Covered Linkways and Drainage at Seletar North Estate.

1.2 Tenderers shall be registered with the Building and Construction Authority under workhead CW01 (General Building) with a financial grade of C1 and above.

1.3 The closing date for submission of tenders is 14 August 2029 at 4.00 pm. Tenders received after the closing date and time shall be rejected.

1.4 A site show-round will be held on 24 July 2029 at 10.00 am. Attendance is compulsory; a tenderer who does not attend shall be disqualified.

SECTION 2 INSTRUCTIONS TO TENDERERS

APPENDIX TO THE INSTRUCTIONS TO TENDERERS

| Item | Description | Particulars |
| --- | --- | --- |
| 1 | Employer | Seletar North Town Council, 21 Seletar Link, Singapore |
| 2 | Contract Period | 9 months from the date of commencement |
| 3 | Tender Validity Period | 120 days from the closing date |
| 4 | Tender Deposit | S$35,000 by banker's guarantee or cashier's order |
| 5 | Performance Bond | 5% of the Contract Sum |
| 6 | Defects Liability Period | 12 months |
| 7 | Joint Ventures | Not permitted |
| 8 | Alternative Tenders | Not permitted |
| 9 | Number of copies | One original and two copies |

2.1 The tenderer shall submit the Form of Tender duly signed. An unsigned Form of Tender shall render the tender invalid.

2.2 A tender not accompanied by the Tender Deposit shall be rejected.

2.3 Tenders shall remain valid for the Tender Validity Period. A tender with a shorter validity shall be treated as non-responsive.

2.4 Any tenderer who canvasses any member of the Tender Evaluation Committee shall be disqualified.

2.5 The Project Manager proposed shall have at least 8 years of relevant experience and a degree in civil engineering.

SECTION 3 EVALUATION CRITERIA

The tender will be evaluated using the Price Quality Method.

| Criteria | Weightage |
| --- | --- |
| Price | 60% |
| Track record | 15% |
| Method statement and programme | 15% |
| Safety performance | 10% |

SECTION 4 CONDITIONS OF CONTRACT

{CONDITIONS}

SECTION 5 FORMS OF TENDER

The tender shall comprise the following documents:

(1) Form of Tender;

(2) Schedule of Rates;

(3) Method Statement;

(4) Safety Track Record Declaration.
"""


GOLD = {
    "fields": [
        {"label": "项目名称", "expect": "Proposed Upgrading of Covered Linkways and Drainage at Seletar North Estate"},
        {"label": "招标人", "expect": "Seletar North Town Council"},
        {"label": "招标编号", "expect": "TC-SNE-2029-044"},
        {"label": "投标截止", "expect": "14 August 2029"},
        {"label": "踏勘", "expect": "24 July 2029"},
        {"label": "注册资格/工作类别", "expect": "CW01"},
        {"label": "工期", "expect": "9 months"},
        {"label": "投标有效期", "expect": "120 days"},
        {"label": "投标保证金", "expect": "S$35,000"},
        {"label": "履约担保", "expect": "5% of the Contract Sum"},
        {"label": "缺陷责任期", "expect": "12 months"},
        {"label": "联合体投标", "expect": "Not permitted"},
        {"label": "备选投标方案", "expect": "Not permitted"},
        {"label": "投标文件份数", "expect": "One original and two copies"},
        {"label": "评标办法", "expect": "Price Quality Method"},
        {"label": "项目经理", "expect": "at least 8 years of relevant experience"},
    ],
    "rejections": ["Tenders received after the closing date and time shall be rejected", "a tenderer who does not attend shall be disqualified",
                   "An unsigned Form of Tender shall render the tender invalid", "A tender not accompanied by the Tender Deposit shall be rejected",
                   "A tender with a shorter validity shall be treated as non-responsive",
                   "canvasses any member of the Tender Evaluation Committee shall be disqualified"],
    "scores": [["Price", "60"], ["Track record", "15"], ["Method statement and programme", "15"], ["Safety performance", "10"]],
    "forms": ["Form of Tender", "Schedule of Rates", "Method Statement", "Safety Track Record Declaration"],
}


def main() -> int:
    (HERE / "en_itt.md").write_text(tender(), encoding="utf-8")
    (HERE / "en_itt.gold.json").write_text(json.dumps(GOLD, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"en_itt.md {len(tender())} chars; gold {len(GOLD['fields'])} fields")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
