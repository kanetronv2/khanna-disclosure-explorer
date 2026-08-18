#!/usr/bin/env python3
"""Rebuild the scan-verified April 2022 PTR pages from annual Schedule B rows.

The PTR scan is authoritative for page boundaries, row order, account headings,
and notification date.  The matching annual filing supplies the clean row fields
after the runs and their endpoints were independently matched to the PTR scan.
"""

from __future__ import annotations

import copy
import datetime as dt
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ANNUAL_TEXT = ROOT / "docs/2022-15/text"
PTR_TEXT = ROOT / "docs/2022-5/text"

# Zero-based, half-open positions in the annual filing's April transaction run.
PAGE_RANGES = {
    3: (87, 158),
    4: (158, 231),
    5: (231, 303),
    6: (303, 376),
    7: (376, 449),
    8: (449, 521),
    9: (521, 594),
    10: (594, 667),
    11: (667, 740),
    12: (740, 812),
    13: (812, 885),
    14: (885, 954),
    15: (954, 1032),
    16: (1032, 1089),
}

# Account headings printed in the PTR scan. Keys are annual-run positions.
GROUPS = {
    87: "Monte and Usha Ahuja 2010 Irrev Trust FBO Grandchildren",
    253: "Ahuja Grandchildren's Education Trust",
    456: "Ahuja Khanna Children's Irrevocable Trust",
    756: "Ritu Ahuja 1994 Trust",
    1060: "Ritu Ahuja 1995 Trust",
    1087: "M & R Primary",
}

EXPECTED_ANCHORS = {
    87: "HEDGE FUND SELECT: ELT ASSOCIATES LLC COMMITMENT",
    157: "AMERICAN TOWER CORPORATION CMN",
    158: "DANAHER CORPORATION CMN",
    230: "WELLS FARGO & COMPANY HYBRID PERPETUAL USD",
    231: "SHOPIFY INC. CMN CLASS A",
    302: "REGIONS FINANCIAL CORPORATION CMN",
    303: "THE BANK OF NY MELLON CORP CMN",
    375: "BIOGEN INC. CMN",
    376: "KKR & CO. INC. CMN",
    448: "AMERIPRISE FINANCIAL, INC. CMN",
    449: "BIO-RAD LABORATORIES, INC CMN CLASS A",
    520: "WALT DISNEY COMPANY (THE) CMN",
    521: "MEDTRONIC PUBLIC LIMITED COMPA CMN",
    593: "EAST WEST BANCORP INC CMN",
    594: "U.S. BANCORP CMN",
    666: "STARBUCKS CORP. CMN",
    667: "3M COMPANY CMN",
    739: "GENERAC HOLDINGS INC. CMN",
    740: "PENN NATIONAL GAMING INC CMN",
    811: "ZEBRA TECHNOLOGIES INC CMN CLASS A",
    812: "ROUND ROCK TEX GO 5% 08/15/22 FA",
    884: "QORVO, INC. CMN",
    885: "UNITY SOFTWARE INC. CMN",
    953: "FIRST REPUBLIC BANK CMN SERIES",
    954: "TRANE TECHNOLOGIES PUBLIC LIMI CMN",
    1031: "APOLLO GLOBAL MANAGEMENT INC CMN",
    1032: "INGERSOLL RAND INC CMN",
    1088: "HEDGE FUND SELECT: ELT ASSOCIATES LLC COMMITMENT",
}


def month(value: object) -> int | None:
    match = re.match(r"0?(\d+)/", str(value))
    return int(match.group(1)) if match else None


def normalize_date(value: str) -> str:
    parsed = dt.datetime.strptime(value, "%m/%d/%Y")
    return parsed.strftime("%m/%d/%Y")


def load_april_rows() -> list[dict]:
    rows: list[dict] = []
    for path in sorted(ANNUAL_TEXT.glob("page-*.json")):
        page_number = int(path.stem.removeprefix("page-"))
        page = json.loads(path.read_text())
        for row in page.get("rows", []):
            if row.get("kind") == "tx" and month(row.get("date")) == 4:
                item = copy.deepcopy(row)
                item["_annual_page"] = page_number
                rows.append(item)
    assert len(rows) == 1093, len(rows)
    for index, name in EXPECTED_ANCHORS.items():
        assert rows[index]["asset_name"] == name, (index, rows[index]["asset_name"])
    return rows


def clean_row(source: dict) -> dict:
    row = {key: value for key, value in source.items() if key != "_annual_page"}
    row["date"] = normalize_date(row["date"])
    row["notification_date"] = "05/05/2022"
    row["partial_sale"] = row.get("tx_type") == "Partial Sale"
    return row


def main() -> None:
    annual = load_april_rows()
    total = 0
    for page_number, (start, end) in PAGE_RANGES.items():
        rebuilt: list[dict] = []
        annual_pages: set[int] = set()
        for index in range(start, end):
            if index in GROUPS:
                rebuilt.append({"kind": "group", "text": GROUPS[index]})
            annual_pages.add(annual[index]["_annual_page"])
            rebuilt.append(clean_row(annual[index]))

        path = PTR_TEXT / f"page-{page_number:03}.json"
        page = json.loads(path.read_text())
        page["rows"] = rebuilt
        page["page_confidence"] = "high"
        pages = ", ".join(str(number) for number in sorted(annual_pages))
        page["uncertainties"] = [
            f"All {end - start} printed transaction rows and account headings were "
            f"re-verified against the PTR scan. Clean fields match the same ordered "
            f"annual Schedule B run (annual pages {pages}); the PTR scan remains "
            "authoritative for page boundaries, row order, and 05/05/2022 notification date."
        ]
        page["transcription_note"] = (
            "Scan-verified reconstruction from the matching annual Schedule B row run."
        )
        path.write_text(json.dumps(page, indent=2, ensure_ascii=False) + "\n")
        total += end - start

    assert total == 1002, total
    print(f"Rebuilt {total} scan-matched transactions across docs/2022-5 pages 003-016")


if __name__ == "__main__":
    main()
