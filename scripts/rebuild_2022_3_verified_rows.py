#!/usr/bin/env python3
"""Rebuild the scan-verified February 2022 PTR transaction tables.

The PTR scan is authoritative for transaction presence, page boundaries, row
order, account headings, dates, notification dates, checkbox columns, and
amounts. Clean fields come from the matching annual Schedule B run only after
its ordered endpoints were matched against each PTR page image.
"""

from __future__ import annotations

import copy
import datetime as dt
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ANNUAL_TEXT = ROOT / "docs/2022-15/text"
PTR_TEXT = ROOT / "docs/2022-3/text"

# Zero-based, half-open positions in the annual filing's February run.
PAGE_RANGES = {
    4: (128, 198),
    5: (198, 268),
    7: (336, 406),
    8: (406, 470),
    9: (470, 546),
    10: (546, 616),
}

EXPECTED_ANCHORS = {
    60: "GS FINANCE CORP. LINKED TO S&P 500 INDEX",
    108: "MICROSOFT CORPORATION CMN",
    109: "ALPHABET INC. CMN CLASS C",
    114: "GS FINANCE CORP. LINKED TO S&P 500 INDEX",
    127: "T-MOBILE US, INC. CMN",
    128: "TARGET CORPORATION CMN",
    197: "CATERPILLAR INC (DELAWARE) CMN",
    198: "MEDTRONIC PUBLIC LIMITED COMPA CMN",
    267: "FASTENAL COMPANY CMN",
    268: "MASCO CORPORATION CMN",
    305: "CANADIAN PACIFIC RAILWAY LTD CMN",
    306: "BLIND BROOK-RYE N Y UN FREE GO 5% 03/01/27 MS",
    307: "ALPHABET INC. CMN CLASS A",
    335: "REPUBLIC SERVICES INC CMN",
    336: "BECTON, DICKINSON AND COMPANY CMN",
    405: "PAYLOCITY HOLDING CORPORATION CMN",
    406: "KEYSIGHT TECHNOLOGIES, INC. CMN",
    469: "THERMO FISHER SCIENTIFIC INC CMN",
    470: "MEDTRONIC PUBLIC LIMITED COMPA CMN",
    545: "GENERAL MOTORS COMPANY CMN",
    546: "KKR & CO. INC. CMN",
    615: "QUANTA SERVICES INC CMN",
    616: "MASIMO CORPORATION CMN",
    622: "VERISIGN, INC. CMN",
    623: "TULSA OKLA MET UTIL AUTH UTIL REV 1% 07/01/22 JJ",
    670: "PROCTER & GAMBLE COMPANY (THE) CMN",
    674: "GS FINANCE CORP. LINKED TO S&P 500 INDEX",
    675: "GS FINANCE CORP. LINKED TO EURO STOXX 50 PR",
    676: "GS FINANCE CORP. LINKED TO S&P 500 INDEX",
}


def month(value: object) -> int | None:
    match = re.match(r"0?(\d+)/", str(value))
    return int(match.group(1)) if match else None


def normalized_date(value: str) -> str:
    return dt.datetime.strptime(value, "%m/%d/%Y").strftime("%m/%d/%Y")


def load_february_rows() -> list[dict]:
    rows: list[dict] = []
    for path in sorted(ANNUAL_TEXT.glob("page-*.json")):
        page_number = int(path.stem.removeprefix("page-"))
        page = json.loads(path.read_text())
        for row in page.get("rows", []):
            if row.get("kind") == "tx" and month(row.get("date")) == 2:
                item = copy.deepcopy(row)
                item["_annual_page"] = page_number
                rows.append(item)
    assert len(rows) == 686, len(rows)
    for index, name in EXPECTED_ANCHORS.items():
        assert rows[index]["asset_name"] == name, (index, rows[index]["asset_name"])
    return rows


def clean_row(source: dict, notification_date: str = "03/03/2022") -> dict:
    row = {key: value for key, value in source.items() if key != "_annual_page"}
    row["date"] = normalized_date(row["date"])
    row["notification_date"] = notification_date
    row["partial_sale"] = row.get("tx_type") == "Partial Sale"
    return row


def source_pages(annual: list[dict], indexes: range | list[int]) -> str:
    pages = sorted({annual[index]["_annual_page"] for index in indexes})
    return ", ".join(str(page) for page in pages)


def update_page(page_number: int, rows: list[dict], note: str) -> None:
    path = PTR_TEXT / f"page-{page_number:03}.json"
    page = json.loads(path.read_text())
    page["rows"] = rows
    page["page_confidence"] = "high"
    page["uncertainties"] = [
        {
            "row": None,
            "field": "page_verification",
            "read": "Verified against scan",
            "note": note,
        }
    ]
    page["transcription_note"] = (
        "Scan-verified reconstruction from matching annual Schedule B rows."
    )
    path.write_text(json.dumps(page, indent=2, ensure_ascii=False) + "\n")


def direct_page(annual: list[dict], page_number: int, start: int, stop: int) -> None:
    indexes = list(range(start, stop))
    rows = [clean_row(annual[index]) for index in indexes]
    update_page(
        page_number,
        rows,
        f"All {len(rows)} printed transactions were re-verified against PTR scan "
        f"page {page_number}. Clean fields match the same ordered annual Schedule B "
        f"run (annual pages {source_pages(annual, indexes)}); the PTR scan is "
        "authoritative for presence, order, page boundary, and notification date.",
    )


def rebuild_page_2() -> None:
    path = PTR_TEXT / "page-002.json"
    current = json.loads(path.read_text())
    transactions = [copy.deepcopy(row) for row in current["rows"] if row["kind"] == "tx"]
    assert len(transactions) == 9
    rows = [{"kind": "group", "text": "M&R Trust Partnership"}, *transactions]
    update_page(
        2,
        rows,
        "The account heading and all nine transactions were re-verified directly "
        "against PTR scan page 2; the existing transaction fields match the scan.",
    )


def rebuild_page_3(annual: list[dict]) -> None:
    rows: list[dict] = [
        {
            "kind": "group",
            "text": "Monte and Usha Ahuja 2010 Irrev Trust FBO Grandchildren",
        }
    ]
    rows.extend(clean_row(annual[index]) for index in range(60, 109))
    rows.append({"kind": "group", "text": "Ahuja Grandchildren's Education Trust"})
    rows.extend(clean_row(annual[index]) for index in range(109, 114))
    rows.append({"kind": "group", "text": "Ahuja Khanna Children Irrevocable Trust"})
    rows.extend(clean_row(annual[index]) for index in range(114, 128))
    update_page(
        3,
        rows,
        "All 68 transactions and three printed account headings were re-verified "
        "against PTR scan page 3. Clean fields match annual Schedule B positions "
        "60-127 after the scan sequence and endpoints were matched.",
    )


def rebuild_page_6(annual: list[dict]) -> None:
    rows = [clean_row(annual[index]) for index in range(268, 306)]
    rows.append({"kind": "group", "text": "Ritu Ahuja Declaration of Trust"})
    rows.append(clean_row(annual[306]))
    rows.append({"kind": "group", "text": "Ritu Ahuja 1994 Trust"})
    rows.extend(clean_row(annual[index]) for index in range(307, 336))
    update_page(
        6,
        rows,
        "All 68 transactions and two printed account headings were re-verified "
        "against PTR scan page 6. Clean fields match annual Schedule B positions "
        "268-335; the scan confirms the 1994 trust heading and row boundaries.",
    )


def rebuild_page_11(annual: list[dict]) -> None:
    rows = [clean_row(annual[index]) for index in range(616, 623)]
    rows.append({"kind": "group", "text": "Ritu Ahuja 1995 Trust"})
    rows.extend(clean_row(annual[index]) for index in range(623, 671))
    rows.append({"kind": "group", "text": "M & R TP Primary"})

    # The four GS notes at the bottom are scan-authoritative. The first is an
    # additional 03/01 row; the fourth has 02/17 on the PTR but 01/17 in the
    # annual transcription. Annual rows supply only their clean non-date fields.
    first = clean_row(annual[674])
    first["date"] = "03/01/2022"
    second = clean_row(annual[675])
    third = clean_row(annual[676])
    annual_page_360 = json.loads((ANNUAL_TEXT / "page-360.json").read_text())
    fourth_source = next(
        row
        for row in annual_page_360["rows"]
        if row.get("asset_name") == "GS FINANCE CORP. LINKED TO ESTX BANKS (EUR) PR"
    )
    fourth = clean_row(fourth_source)
    fourth["date"] = "02/17/2022"
    rows.extend([first, second, third, fourth])

    update_page(
        11,
        rows,
        "All 59 transactions and two printed account headings were re-verified "
        "against PTR scan page 11. The first 55 transactions match annual Schedule "
        "B positions 616-670. The scan directly controls the final four GS-note "
        "rows, including the 03/01 and 02/17 dates that conflict with or are absent "
        "from the annual February run.",
    )


def rebuild_page_12() -> None:
    path = PTR_TEXT / "page-012.json"
    current = json.loads(path.read_text())
    transactions = [copy.deepcopy(row) for row in current["rows"] if row["kind"] == "tx"]
    assert len(transactions) == 42
    blocks = [transactions[0:14], transactions[14:28], transactions[28:42]]
    for block in blocks:
        block[0]["date"] = "02/02/2022"

    rows: list[dict] = []
    headings = [
        ("MURA Holdings", "MARA"),
        ("MURA Holdings", "Grandchildren Trust (Khanna Portion)"),
        ("MURA Holdings", "2020 Trust FBO Khanna Children"),
    ]
    for block, (first_heading, second_heading) in zip(blocks, headings):
        rows.append({"kind": "group", "text": first_heading})
        rows.append({"kind": "group", "text": second_heading})
        rows.extend(block)
    update_page(
        12,
        rows,
        "All 42 transactions and six printed account headings were re-verified "
        "against PTR scan page 12. The scan confirms three repeated 14-row account "
        "blocks and 02/02/2022 as the transaction date of each opening GS zero-"
        "coupon note; 02/04/2027 is the note maturity printed in its asset name.",
    )


def main() -> None:
    annual = load_february_rows()
    rebuild_page_2()
    rebuild_page_3(annual)
    for page_number, (start, stop) in PAGE_RANGES.items():
        direct_page(annual, page_number, start, stop)
    rebuild_page_6(annual)
    rebuild_page_11(annual)
    rebuild_page_12()

    tx_total = 0
    group_total = 0
    for page_number in range(2, 13):
        page = json.loads((PTR_TEXT / f"page-{page_number:03}.json").read_text())
        tx_total += sum(row.get("kind") == "tx" for row in page["rows"])
        group_total += sum(row.get("kind") == "group" for row in page["rows"])
    assert tx_total == 666, tx_total
    assert group_total == 14, group_total
    print("Rebuilt 666 scan-verified transactions and 14 group rows across pages 002-012")


if __name__ == "__main__":
    main()
