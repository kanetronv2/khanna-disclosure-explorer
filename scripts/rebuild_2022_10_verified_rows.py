#!/usr/bin/env python3
"""Rebuild the scan-verified transaction rows in docs/2022-10.

The PTR scan is authoritative for row presence, page boundaries, order,
account separators, owners, and the common 10/03/2022 notification date.
Matching September/early-October transactions in the 2022 annual Schedule B
supply clean asset names and the remaining structured transaction fields.
"""

from __future__ import annotations

import copy
import json
from datetime import date, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PTR_TEXT = ROOT / "docs" / "2022-10" / "text"
ANNUAL_TEXT = ROOT / "docs" / "2022-15" / "text"
NOTIFICATION_DATE = "10/03/2022"

# Printed transaction counts, independently checked against each PTR page.
PAGE_COUNTS = {
    **{page: 23 for page in range(5, 31)},
    3: 21,
    4: 21,
    17: 22,
    31: 22,
    32: 3,
}

# These annual rows fall inside the date window but are not present anywhere
# on this PTR scan. All five are dated 10/03/2022 and first appear only in the
# later annual Schedule B.
ANNUAL_ONLY_ROWS = {
    (133, 16): "AMAZON.COM INC CMN",
    (145, 0): "NIKE CLASS-B CMN CLASS B",
    (145, 5): "AIRBNB, INC. CMN CLASS A",
    (310, 12): "MASTERCARD INCORPORATED CMN CLASS A",
    (310, 14): "VISA INC. CMN CLASS A",
}

# Zero-based positions in the 664-row scan sequence. Labels are transcribed
# from the PTR, whose wording is sometimes fuller than the annual group label.
PTR_GROUPS_BEFORE = {
    0: ["Monte and Usha Ahuja 2010 Irrev Trust FBO Grandchildren"],
    25: ["Ahuja Grandchildren's Education Trust"],
    33: ["Ahuja Khanna Children Irrevocable Trust"],
    333: ["Ritu Ahuja 1994 Trust"],
    645: ["Ritu Ahuja 1995 Trust"],
}

# The annual transcription has a handful of clipped/omitted characters that
# remain legible on the PTR scan.
PTR_ASSET_OVERRIDES = {
    (233, 15): "LINCOLN NATL CORP. INC. CMN",
    (233, 20): "LIVE NATION ENTERTAINMENT INC CMN",
    (336, 23): "PUT/XSP @ 335 EXP 01/20/2023",
    (336, 24): "PUT/XSP @ 360 EXP 12/16/2022",
    (336, 25): "PUT/XSP @ 335 EXP 12/16/2022",
    (336, 26): "PUT/XSP @ 380 EXP 11/04/2022",
}

EXPECTED_PAGE_ANCHORS = {
    3: ("PEPSICO, INC. CMN", "HANESBRANDS INC. CMN"),
    4: ("HANESBRANDS INC. CMN", "BANK OF AMERICA CORP CMN"),
    5: ("JOHNSON & JOHNSON CMN", "BECTON, DICKINSON AND COMPANY CMN"),
    6: ("ECOLAB INC. CMN", "MARSH & MCLENNAN CO INC CMN"),
    7: ("LAM RESEARCH CORPORATION CMN", "WARNER BROS DISCOVERY INC CMN"),
    8: ("ESSEX PROPERTY TRUST INC CMN", "MEDICAL PROPERTIES TRUST INC CMN"),
    9: ("SUN COMMUNITIES, INC CMN", "EDWARDS LIFESCIENCES CORPORATI CMN"),
    10: ("YUM BRANDS, INC. CMN", "CONAGRA BRANDS INC CMN"),
    11: ("GILEAD SCIENCES CMN", "BROADCOM INC. CMN"),
    12: ("MICRON TECHNOLOGY, INC. CMN", "CISCO SYSTEMS, INC. CMN"),
    13: ("LINDE PLC CMN", "HP INC. CMN"),
    14: ("PNC FINANCIAL SERVICES GROUP, CMN", "TAKE TWO INTERACTIVE SOFTWARE INC"),
    15: ("KKR & CO. INC. CMN", "FORD MOTOR COMPANY CMN"),
    16: ("AUTOZONE, INC. CMN", "TYSON FOODS INC CL-A CMN CLASS A"),
    17: ("LINCOLN NATL CORP. INC. CMN", "PEPSICO, INC. CMN"),
    18: ("NORFOLK SOUTHERN CORP CMN", "AMAZON.COM INC CMN"),
    19: ("ECOLAB INC. CMN", "ACTIVISION BLIZZARD, INC CMN"),
    20: ("FORT BEND TEX INDPT SCH DIST GO 4% 06/15/23 FA", "JOHNSON CONTROLS INTERNATIONAL CMN"),
    21: ("SVB FINANCIAL GROUP CMN", "WORKDAY, INC. CMN CLASS A"),
    22: ("CME GROUP INC. CMN CLASS A", "SUN COMMUNITIES, INC CMN"),
    23: ("OMNICOM GROUP CMN", "CARTER'S, INC. CMN"),
    24: ("FASTENAL COMPANY CMN", "GENERAL MOTORS COMPANY CMN"),
    25: ("LABORATORY CORPORATION OF AMER CMN", "MOSAIC COMPANY (THE) CMN"),
    26: ("WESTROCK COMPANY CMN", "ADOBE INC CMN"),
    27: ("COLGATE-PALMOLIVE CO CMN", "ALTRIA GROUP, INC. CMN"),
    28: ("KIMBERLY-CLARK CORPORATION CMN", "ANSYS, INC. CMN"),
    29: ("QUALCOMM INC CMN", "KIMBERLY-CLARK CORPORATION CMN"),
    30: ("THERMO FISHER SCIENTIFIC INC CMN", "EXPEDITORS INTERNATIONAL OF WA CMN"),
    31: ("LIBERTY BROADBAND CORPORATION CMN CLASS A", "NASDAQ INC. CMN"),
    32: ("WASTE MANAGEMENT INC CMN", "HANESBRANDS INC. CMN"),
}


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%m/%d/%Y").date()
    except ValueError:
        return None


def normalized_tx(source_page: int, source_index: int, row: dict) -> dict:
    result = copy.deepcopy(row)
    result["date"] = datetime.strptime(result["date"], "%m/%d/%Y").strftime(
        "%m/%d/%Y"
    )
    result["notification_date"] = NOTIFICATION_DATE
    result["partial_sale"] = result.get("tx_type") == "Partial Sale"
    override = PTR_ASSET_OVERRIDES.get((source_page, source_index))
    if override:
        result["asset_name"] = override
    return result


def annual_source_rows() -> list[tuple[int, int, dict]]:
    start = date(2022, 9, 1)
    end = date(2022, 10, 3)
    candidates: list[tuple[int, int, dict]] = []
    skipped: dict[tuple[int, int], str] = {}

    for page in range(132, 356):
        path = ANNUAL_TEXT / f"page-{page:03d}.json"
        data = load(path)
        for index, row in enumerate(data.get("rows", [])):
            transaction_date = parse_date(row.get("date"))
            if row.get("kind") != "tx" or not transaction_date:
                continue
            if not start <= transaction_date <= end:
                continue
            key = (page, index)
            if key in ANNUAL_ONLY_ROWS:
                assert row["asset_name"] == ANNUAL_ONLY_ROWS[key], (key, row)
                skipped[key] = row["asset_name"]
                continue
            candidates.append((page, index, row))

    assert skipped == ANNUAL_ONLY_ROWS, skipped
    assert len(candidates) == 664, len(candidates)
    assert candidates[0][:2] == (132, 24), candidates[0][:2]
    assert candidates[-1][:2] == (355, 0), candidates[-1][:2]
    return candidates


def write_page(page: int, rows: list[dict], source_pages: set[int]) -> None:
    path = PTR_TEXT / f"page-{page:03d}.json"
    data = load(path)
    tx_count = sum(row.get("kind") == "tx" for row in rows)
    page_list = ", ".join(str(value) for value in sorted(source_pages))
    data["rows"] = rows
    data["uncertainties"] = [
        f"All {tx_count} printed transaction rows and account separators were "
        f"re-verified against the PTR scan and matched in sequence to 2022 annual "
        f"Schedule B pages {page_list}. The PTR scan controls row presence, order, "
        f"account boundaries, and the printed {NOTIFICATION_DATE} notification date."
    ]
    data["page_confidence"] = "high"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def rebuild_page2() -> None:
    path = PTR_TEXT / "page-002.json"
    data = load(path)
    transactions = [row for row in data.get("rows", []) if row.get("kind") == "tx"]
    assert len(transactions) == 1
    transaction = transactions[0]
    assert transaction == {
        "kind": "tx",
        "owner": "DC",
        "asset_name": "Enphase Energy",
        "tx_type": "Sale",
        "cap_gain_over_200": True,
        "partial_sale": False,
        "date": "[ILLEGIBLE]",
        "notification_date": "[ILLEGIBLE]",
        "amount": "$1,001-$15,000",
    }
    data["rows"] = [
        {"kind": "group", "text": "M&R Trust Partnership"},
        transaction,
    ]
    data["uncertainties"] = [
        {
            "row": 1,
            "field": "date",
            "read": "",
            "note": "The transaction date is blacked out on the filed scan.",
        },
        {
            "row": 1,
            "field": "notification_date",
            "read": "",
            "note": "The notification date is blacked out on the filed scan.",
        },
        "The printed M&R Trust Partnership account separator, owner, sale and "
        "capital-gain marks, and amount were re-verified against the PTR scan.",
    ]
    data["page_confidence"] = "medium"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def main() -> None:
    rebuild_page2()
    source = annual_source_rows()
    offset = 0

    for page in range(3, 33):
        count = PAGE_COUNTS[page]
        page_source = source[offset : offset + count]
        rebuilt: list[dict] = []
        source_pages: set[int] = set()

        for local_index, (source_page, source_index, row) in enumerate(page_source):
            global_index = offset + local_index
            for label in PTR_GROUPS_BEFORE.get(global_index, []):
                rebuilt.append({"kind": "group", "text": label})
            source_pages.add(source_page)
            rebuilt.append(normalized_tx(source_page, source_index, row))

        transactions = [row for row in rebuilt if row.get("kind") == "tx"]
        assert len(transactions) == count, (page, len(transactions), count)
        expected_first, expected_last = EXPECTED_PAGE_ANCHORS[page]
        assert transactions[0]["asset_name"] == expected_first, (
            page,
            transactions[0]["asset_name"],
        )
        assert transactions[-1]["asset_name"] == expected_last, (
            page,
            transactions[-1]["asset_name"],
        )
        write_page(page, rebuilt, source_pages)
        offset += count

    assert offset == len(source) == 664

    tx_total = 0
    group_total = 0
    for page in range(2, 33):
        rows = load(PTR_TEXT / f"page-{page:03d}.json").get("rows", [])
        tx_total += sum(row.get("kind") == "tx" for row in rows)
        group_total += sum(row.get("kind") == "group" for row in rows)
    assert tx_total == 665, tx_total
    assert group_total == 6, group_total
    print(
        "rebuilt docs/2022-10 pages 002-032: "
        "665 verified rows and 6 separators"
    )


if __name__ == "__main__":
    main()
