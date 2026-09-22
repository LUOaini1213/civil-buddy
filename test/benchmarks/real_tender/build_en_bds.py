#!/usr/bin/env python3
"""Held-out H: an English bidding document in the multilateral-bank shape - written after the English rules were frozen
on en_itt, in other words and another layout: "Section II. Bid Data Sheet" as a TWO-column table (ITB Reference | Data)
whose cells are sentences ("The bid validity period shall be 90 days."), Bidders / Bid Security / Purchaser, criteria
scored in points, "will be rejected as non-responsive" / "shall result in disqualification".

    python test/benchmarks/real_tender/build_en_bds.py
    python scripts/eval_real_document.py test/benchmarks/real_tender/en_bds.md --gold test/benchmarks/real_tender/en_bds.gold.json --word

Run once; the first-run number goes into README.md.
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

GCC = "\n\n".join(
    f"GCC {n}.{k} The Contractor shall notify the Project Manager within {5 + n + k} days of any event likely to delay the Works. "
    f"Delay damages of {0.05 * k:.2f} per cent of the Contract Price per day shall apply, up to a maximum of {5 + k} per cent. "
    f"The Employer shall pay certified amounts within {28 + n} days." for n in range(1, 12) for k in range(1, 5))


def tender() -> str:
    return f"""# BIDDING DOCUMENT

# Rehabilitation of the Kanda River Flood Embankment, Lot KR-2

Invitation for Bids No.: MOW/KRB/2030/NCB-07

Table of Contents

Section I. Instructions to Bidders ........................................ 3
Section II. Bid Data Sheet ................................................ 21
Section III. Evaluation and Qualification Criteria ........................ 27
Section IV. Bidding Forms ................................................. 35
Section V. General Conditions of Contract ................................. 60

Section I. Instructions to Bidders

1.1 The Employer indicated in the Bid Data Sheet issues this Bidding Document for the procurement of the Works specified in it.

18.1 Bids shall remain valid for the period specified in the BDS. A bid valid for a shorter period shall be rejected by the Employer as non-responsive.

19.1 The Bidder shall furnish as part of its bid a bid security in the amount specified in the BDS. Any bid not accompanied by a substantially responsive bid security shall be rejected by the Employer as non-responsive.

22.1 Bids must be received by the Employer no later than the date and time specified in the BDS. Any bid received after the deadline will be declared late, rejected, and returned unopened.

26.2 Any attempt by a Bidder to influence the Employer in the evaluation of the bids shall result in the disqualification of its bid.

Section II. Bid Data Sheet

| ITB Reference | Data |
| --- | --- |
| ITB 1.1 | The Employer is: Ministry of Works, Kanda River Basin Office |
| ITB 1.1 | The name of the bidding process is: Rehabilitation of the Kanda River Flood Embankment, Lot KR-2 |
| ITB 4.1 | Joint ventures are permitted, with no more than three members. |
| ITB 13.1 | Alternative bids shall not be considered. |
| ITB 18.1 | The bid validity period shall be 90 days. |
| ITB 19.1 | A bid security shall be required in the amount of USD 85,000. |
| ITB 20.1 | In addition to the original of the bid, the number of copies is: three. |
| ITB 22.1 | The deadline for bid submission is: 9 October 2030, 10:00 a.m. local time |
| ITB 25.1 | The bid opening shall take place at: Ministry of Works, Conference Room 2, Kanda |
| ITB 41.1 | The performance security shall be 10 per cent of the Contract Price. |

Section III. Evaluation and Qualification Criteria

The Employer will award the contract to the lowest evaluated bid. The technical proposal is scored as follows.

| Criterion | Maximum points |
| --- | --- |
| Construction methodology | 40 points |
| Key personnel | 25 points |
| Environmental and social management | 20 points |
| Work programme | 15 points |

3.1 The Bidder shall have completed at least two flood-protection contracts of a value of USD 4 million each within the last seven years. A Bidder that does not meet this requirement shall be disqualified.

Section IV. Bidding Forms

The bid shall comprise the following documents:

(a) Letter of Bid;

(b) Bid Security;

(c) Priced Bill of Quantities;

(d) Technical Proposal.

Section V. General Conditions of Contract

{GCC}
"""


GOLD = {
    "fields": [
        {"label": "项目名称", "expect": "Rehabilitation of the Kanda River Flood Embankment, Lot KR-2"},
        {"label": "招标人", "expect": "Ministry of Works, Kanda River Basin Office"},
        {"label": "招标编号", "expect": "MOW/KRB/2030/NCB-07"},
        {"label": "投标截止", "expect": "9 October 2030"},
        {"label": "投标有效期", "expect": "90 days"},
        {"label": "投标保证金", "expect": "USD 85,000"},
        {"label": "履约担保", "expect": "10 per cent of the Contract Price"},
        {"label": "联合体投标", "expect": "permitted"},
        {"label": "备选投标方案", "expect": "shall not be considered"},
        {"label": "投标文件份数", "expect": "three"},
        {"label": "开标地点", "expect": "Ministry of Works, Conference Room 2, Kanda"},
        {"label": "类似业绩", "expect": "at least two flood-protection contracts"},
    ],
    "rejections": ["shall be rejected by the Employer as non-responsive", "Any bid not accompanied by a substantially responsive bid security shall be rejected",
                   "will be declared late, rejected, and returned unopened", "shall result in the disqualification of its bid",
                   "A Bidder that does not meet this requirement shall be disqualified"],
    "scores": [["Construction methodology", "40"], ["Key personnel", "25"], ["Environmental and social management", "20"], ["Work programme", "15"]],
    "forms": ["Letter of Bid", "Bid Security", "Priced Bill of Quantities", "Technical Proposal"],
}


def main() -> int:
    (HERE / "en_bds.md").write_text(tender(), encoding="utf-8")
    (HERE / "en_bds.gold.json").write_text(json.dumps(GOLD, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"en_bds.md {len(tender())} chars; gold {len(GOLD['fields'])} fields")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
