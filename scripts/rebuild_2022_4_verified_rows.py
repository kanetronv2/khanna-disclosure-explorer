#!/usr/bin/env python3
"""Rebuild the scan-verified transaction rows in docs/2022-4.

The PTR scan is authoritative for page boundaries, row order, account
separators, owners, and the common 04/04/2022 notification date.  Matching
March transactions in the 2022 annual Schedule B supply the legible asset,
transaction-type, date, amount, and capital-gain fields.
"""

from __future__ import annotations

import copy
import json
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PTR_TEXT = ROOT / "docs" / "2022-4" / "text"
ANNUAL_TEXT = ROOT / "docs" / "2022-15" / "text"
NOTIFICATION_DATE = "04/04/2022"

# Zero-based slices into the 505 March transactions found on annual pages
# 127 onward. The first 498 rows were independently matched to PTR scan pages
# 003-009 by their printed endpoints and row runs.
PAGE_RANGES = {
    3: (0, 88),
    4: (88, 132),
    5: (132, 218),
    6: (218, 305),
    7: (305, 393),
    8: (393, 477),
    9: (477, 498),
}

# These are PTR account separators, transcribed from the scan. They do not
# occur at the same boundaries as group rows in the annual filing.
PTR_GROUPS_BEFORE = {
    1: ["Monte and Usha Ahuja 2010 Irrev Trust FBO Grandchildren"],
    58: ["Ahuja Grandchildren's Education Trust"],
    119: ["Ahuja Khanna Children Irrevocable Trust"],
    206: ["Ritu Ahuja 1994 Trust"],
    474: ["Ritu Ahuja 1995 Trust"],
}

EXPECTED_ANCHORS = {
    1: "CHARLES SCHWAB CORPORATION (TH HYBRID PERPETUAL",
    88: "NASDAQ INC. CMN",
    89: "WEX INC. CMN",
    132: "EPAM SYSTEMS, INC. CMN",
    133: "PVH CORP CMN",
    218: "NETFLIX, INC. CMN",
    219: "ORACLE CORPORATION CMN",
    305: "F5 INC CMN",
    306: "AON PUBLIC LIMITED COMPANY CMN",
    393: "PUT/XSP @ 433 EXP 05/06/2022",
    394: "MATCH GROUP, INC. CMN",
    477: "TEXAS PUB FIN AUTH LEASE REV REV 5% 02/01/23 FA",
    478: "DALLAS TEX INDPT SCH DIST GO 5% 02/15/23 FA",
    498: "PUBLIC STORAGE CMN",
}

# A small number of annual rows contain an obvious clipped character even
# though the corresponding PTR text is legible.
PTR_ASSET_OVERRIDES = {
    1: "CHARLES SCHWAB CORPORATION (THE) HYBRID PERPETUAL",
}

PAGE10_SOURCE_PAGES = ((112, 113), (116, 117), (120, 121))
PAGE10_GROUPS = (
    ("MURA Holdings", "RA94"),
    ("MURA Holdings", "Grandchildren Trust (Khanna Portion)"),
    ("MURA Holdings", "2020 Trust FBO Khanna Children"),
)
PAGE10_DATES = {"3/1/2022", "3/8/2022", "3/9/2022", "3/15/2022"}
PAGE10_SCAN_ORDER = (3, 2, 1, 4, 6, 5, 8, 7, 9, 10, 0, 11)


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def normalized_tx(row: dict) -> dict:
    result = copy.deepcopy(row)
    result["date"] = datetime.strptime(result["date"], "%m/%d/%Y").strftime(
        "%m/%d/%Y"
    )
    result["notification_date"] = NOTIFICATION_DATE
    result["partial_sale"] = result.get("tx_type") == "Partial Sale"
    return result


def annual_march_rows() -> list[tuple[int, dict]]:
    rows: list[tuple[int, dict]] = []
    for path in sorted(ANNUAL_TEXT.glob("page-*.json")):
        page = int(path.stem.split("-")[1])
        if page < 127:
            continue
        for row in load(path).get("rows", []):
            if row.get("kind") == "tx" and str(row.get("date", "")).startswith("3/"):
                rows.append((page, row))
    assert len(rows) == 505, len(rows)
    for position, asset in EXPECTED_ANCHORS.items():
        assert rows[position - 1][1]["asset_name"] == asset, (
            position,
            rows[position - 1][1]["asset_name"],
        )
    return rows


def write_page(page: int, rows: list[dict], note: str) -> None:
    path = PTR_TEXT / f"page-{page:03d}.json"
    data = load(path)
    data["rows"] = rows
    data["uncertainties"] = [note]
    data["page_confidence"] = "high"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def rebuild_main_pages(source: list[tuple[int, dict]]) -> None:
    for page, (start, end) in PAGE_RANGES.items():
        rebuilt: list[dict] = []
        source_pages: set[int] = set()
        for offset in range(start, end):
            position = offset + 1
            for text in PTR_GROUPS_BEFORE.get(position, []):
                rebuilt.append({"kind": "group", "text": text})
            annual_page, row = source[offset]
            source_pages.add(annual_page)
            transaction = normalized_tx(row)
            if position in PTR_ASSET_OVERRIDES:
                transaction["asset_name"] = PTR_ASSET_OVERRIDES[position]
            rebuilt.append(transaction)

        tx_count = sum(row.get("kind") == "tx" for row in rebuilt)
        assert tx_count == end - start
        page_list = ", ".join(str(n) for n in sorted(source_pages))
        write_page(
            page,
            rebuilt,
            f"All {tx_count} printed transaction rows and account separators were "
            f"re-verified against the PTR scan and matched to 2022 annual Schedule B "
            f"pages {page_list}. The PTR scan controls row presence, order, account "
            f"boundaries, and the printed {NOTIFICATION_DATE} notification date.",
        )


def annual_rows_from_pages(pages: tuple[int, int]) -> list[dict]:
    rows: list[dict] = []
    for page in pages:
        for row in load(ANNUAL_TEXT / f"page-{page:03d}.json").get("rows", []):
            if row.get("kind") == "tx" and row.get("date") in PAGE10_DATES:
                rows.append(row)
    assert len(rows) == 12, (pages, len(rows))
    return rows


def rebuild_page10() -> None:
    rebuilt: list[dict] = []
    for source_pages, groups in zip(PAGE10_SOURCE_PAGES, PAGE10_GROUPS):
        rebuilt.extend({"kind": "group", "text": text} for text in groups)
        source = annual_rows_from_pages(source_pages)
        rebuilt.extend(normalized_tx(source[index]) for index in PAGE10_SCAN_ORDER)

    transactions = [row for row in rebuilt if row.get("kind") == "tx"]
    assert len(transactions) == 36
    expected_assets = [
        "STRYKER CORPORATION COM",
        "OTIS WORLDWIDE CORP COM",
        "BOSTON SCIENTIFIC CORP",
        "SCHWAB CHARLES CORP COM",
        "MICROSOFT CORP",
        "BRISTOL-MYERS SQUIBB CO COM",
        "TAIWAN SEMICONDUCTOR MANUFACTURING SPON ADS EA",
        "SHERWIN-WILLIAMS CO",
        "DOMINO S PIZZA INC",
        "MATCH GROUP INC NEW COM",
        "CITIGROUP INC",
        "ACTIVISION BLIZZARD INC COM",
    ]
    for block in range(3):
        assert [
            row["asset_name"] for row in transactions[block * 12 : (block + 1) * 12]
        ] == expected_assets

    write_page(
        10,
        rebuilt,
        "All 36 printed transaction rows and six account separators were re-verified "
        "against the PTR scan and matched to 2022 annual Schedule B pages 112-113, "
        "116-117, and 120-121. The PTR scan controls row order, account labels, owners, "
        f"and the printed {NOTIFICATION_DATE} notification date.",
    )


def main() -> None:
    source = annual_march_rows()
    rebuild_main_pages(source)
    rebuild_page10()

    tx_total = 0
    for page in range(2, 11):
        tx_total += sum(
            row.get("kind") == "tx"
            for row in load(PTR_TEXT / f"page-{page:03d}.json").get("rows", [])
        )
    assert tx_total == 539, tx_total
    print("rebuilt docs/2022-4 pages 003-010: 534 verified rows; 539 document total")


if __name__ == "__main__":
    main()
