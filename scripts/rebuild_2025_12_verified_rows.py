#!/usr/bin/env python3
"""Rebuild the scan-verified September 2025 PTR transaction tables.

The PTR scan is authoritative for transaction presence, page boundaries, row
order, account headings, and notification dates.  Clean transaction fields are
copied from the matching annual Schedule B rows only after the ordered runs and
their page endpoints were matched against every PTR page image.
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ANNUAL_TEXT = ROOT / "docs/2025-14/text"
PTR_TEXT = ROOT / "docs/2025-12/text"

# Zero-based, half-open positions in the annual filing's September run.
# Page 2 excludes five annual transactions not printed in this PTR: positions
# 3, 4, and 6.  Positions 280 and 281 fall between PTR pages 18 and 19 and are
# likewise not printed in this report.
PAGE_INDEXES = {
    2: [1, 2, 5, *range(7, 23)],
    3: list(range(23, 40)),
    4: list(range(40, 51)),
    5: list(range(51, 68)),
    6: list(range(68, 88)),
    7: list(range(88, 108)),
    8: list(range(108, 128)),
    9: list(range(128, 148)),
    10: list(range(148, 156)),
    11: list(range(156, 170)),
    12: list(range(170, 190)),
    13: list(range(190, 210)),
    14: list(range(210, 230)),
    15: list(range(230, 250)),
    16: list(range(250, 259)),
    17: list(range(259, 277)),
    18: list(range(277, 280)),
    19: list(range(282, 296)),
}

PAGE_GROUPS = {
    2: "Monte and Usha Ahuja 2010 Irrev Trust FBO Grandchildren",
    3: "Monte and Usha Ahuja 2010 Irrev Trust FBO Grandchildren",
    4: "Ahuja Grandchildren's Education Trust",
    5: "2020 Trust FBO Khanna Children",
    6: "2020 Trust FBO Khanna Children",
    7: "2020 Trust FBO Khanna Children",
    8: "2020 Trust FBO Khanna Children",
    9: "2020 Trust FBO Khanna Children",
    10: "2020 Trust FBO Khanna Children",
    11: "Ritu Ahuja Declaration of Trust",
    12: "Ritu Ahuja 1994 Trust",
    13: "Ritu Ahuja 1994 Trust",
    14: "Ritu Ahuja 1994 Trust",
    15: "Ritu Ahuja 1994 Trust",
    16: "Ritu Ahuja 1994 Trust",
    17: "Ritu Ahuja 1995 Trust",
    18: "Ritu Ahuja 1995 Trust",
    19: "M & R Trust Partnership",
}

EXPECTED_ANCHORS = {
    1: "ALPHABET INC  CMN  CLASS C",
    2: "MORGAN STANLEY FINANCE LLC LINKED TO BASKET OF INDICES",
    22: "CHARLES SCHWAB CORPORATION (TH HYBRID PERPETUAL USD",
    23: "CALL/AAPL FLEX EURO  PM 220 EXP 09/05/2025",
    40: "DECKERS OUTDOORS CORP CMN",
    51: "BANK OF MONTREAL LINKED TO S&P 500 INDEX",
    108: "S&P GLOBAL INC CMN",
    109: "AUTOMATIC DATA PROCESSING INC CMN",
    156: "WASHINGTON D C MET AREA TRAN REV 5 % 07/15/29 JJ",
    188: "AUTOMATIC DATA PROCESSING INC CMN",
    210: "CALL/ING FLEX EURO  PM  @ 24 EXP 09/12/2025",
    252: "DATADOG  INC  CMN CLASS A",
    259: "KEYCORP HYBRID PERPETUAL USD",
    279: "NASDAQ INC  CMN",
    282: "WILLOUGHBY EASTLAKE OHIO CITY GO 5% 12/01/46-CA JD SCH DIST",
    295: "PALANTIR TECHNOLOGIES INC CMN",
    315: "BERKSHIRE HATHAWAY INC COM USD0 0033 CLASS B",
    317: "UNITEDHEALTH GROUP INC",
    328: "BERKSHIRE HATHAWAY INC COM USD0 0033 CLASS B",
    330: "UNITEDHEALTH GROUP INC",
    342: "UNITEDHEALTH GROUP INC",
}

# A few annual transcriptions retain slash/spacing OCR where the PTR image
# clearly prints a percent sign.  Preserve the scan's literal security name.
SCAN_NAME_OVERRIDES = {
    52: "OHIO ST GO 5% 03/01/32 MS",
    156: "WASHINGTON D C MET AREA TRAN REV 5% 07/15/29 JJ",
    283: "CINCINNATI OHIO WTR SYS REV REV 5% 12/01/25 JD",
    286: "CLARK CNTY NEV PASSENGER FAC REV 5% 07/01/26 JJ",
}


def month(value: object) -> int | None:
    match = re.match(r"0?(\d+)/", str(value))
    return int(match.group(1)) if match else None


def load_september_rows() -> list[dict]:
    rows: list[dict] = []
    for path in sorted(ANNUAL_TEXT.glob("page-*.json")):
        page_number = int(path.stem.removeprefix("page-"))
        page = json.loads(path.read_text())
        for row in page.get("rows", []):
            if row.get("kind") == "tx" and month(row.get("date")) == 9:
                item = copy.deepcopy(row)
                item["_annual_page"] = page_number
                rows.append(item)
    assert len(rows) == 350, len(rows)
    for index, name in EXPECTED_ANCHORS.items():
        assert rows[index]["asset_name"] == name, (index, rows[index]["asset_name"])
    return rows


def clean_row(source: dict, notification_date: str, annual_index: int) -> dict:
    row = {key: value for key, value in source.items() if key != "_annual_page"}
    if annual_index in SCAN_NAME_OVERRIDES:
        row["asset_name"] = SCAN_NAME_OVERRIDES[annual_index]
    row["notification_date"] = notification_date
    row["partial_sale"] = row.get("tx_type") == "Partial Sale"
    return row


def update_page(page_number: int, rows: list[dict], note: str) -> None:
    path = PTR_TEXT / f"page-{page_number:03}.json"
    page = json.loads(path.read_text())
    page["rows"] = rows
    page["page_confidence"] = "high"
    page["uncertainties"] = [note]
    if page_number == 3:
        page["uncertainties"].append(
            {
                "row": 2,
                "field": "owner",
                "read": "blank",
                "note": (
                    "The American Express owner cell is blank on the filed PTR "
                    "scan and is intentionally preserved as null."
                ),
            }
        )
    page["transcription_note"] = (
        "Scan-verified reconstruction from matching annual Schedule B rows."
    )
    path.write_text(json.dumps(page, indent=2, ensure_ascii=False) + "\n")


def main() -> None:
    annual = load_september_rows()
    total = 0

    for page_number, indexes in PAGE_INDEXES.items():
        rows = [{"kind": "group", "text": PAGE_GROUPS[page_number]}]
        rows.extend(clean_row(annual[index], "10/02/2025", index) for index in indexes)
        annual_pages = sorted({annual[index]["_annual_page"] for index in indexes})
        pages = ", ".join(str(number) for number in annual_pages)
        update_page(
            page_number,
            rows,
            f"All {len(indexes)} printed transactions and the account heading were "
            f"re-verified against PTR scan page {page_number}. Clean fields match the "
            f"same ordered annual Schedule B run (annual pages {pages}); the PTR scan "
            "is authoritative for presence, order, page boundary, group, and "
            "10/02/2025 notification date.",
        )
        total += len(indexes)

    # Page 20 is a separately notified amendment.  The scan interleaves three
    # MURA Holdings subaccounts, and its order differs from the annual schedule.
    page_20_rows = [
        {"kind": "group", "text": "MURA Holdings"},
        {"kind": "group", "text": "Ritu Ahuja 1994 Trust"},
        clean_row(annual[317], "09/04/2025", 317),
        clean_row(annual[315], "09/04/2025", 315),
        {"kind": "group", "text": "MURA Holdings"},
        {
            "kind": "group",
            "text": "Monte and Usha Ahuja 2010 Irrev Trust FBO Grandchildren",
        },
        clean_row(annual[330], "09/04/2025", 330),
        clean_row(annual[328], "09/04/2025", 328),
        {"kind": "group", "text": "MURA Holdings"},
        {"kind": "group", "text": "2020 Trust FBO Khanna Children"},
        clean_row(annual[342], "09/04/2025", 342),
    ]
    update_page(
        20,
        page_20_rows,
        "All five printed transactions and six account headings were re-verified "
        "against PTR scan page 20. Matching annual Schedule B rows supply clean "
        "fields; the PTR amendment scan is authoritative for row order, account "
        "structure, and 09/04/2025 notification date.",
    )
    total += 5

    assert total == 295, total
    assert sum(len(indexes) for indexes in PAGE_INDEXES.values()) == 290
    print("Rebuilt 295 scan-verified transactions across docs/2025-12 pages 002-020")


if __name__ == "__main__":
    main()
