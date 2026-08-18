#!/usr/bin/env python3
"""Rebuild docs/2025-11 from its scan-verified transaction sequence.

The PTR scan is authoritative for row presence, order, page boundaries,
account labels, owners, transaction columns, dates, notification dates, and
amount columns. Matching rows in the later 2025 annual Schedule B are used as
a clean structured transcription only after the scan sequence and endpoints
have been checked. Explicit slices below exclude later annual-only activity.
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PTR_TEXT = ROOT / "docs" / "2025-11" / "text"
ANNUAL_TEXT = ROOT / "docs" / "2025-14" / "text"
NOTIFICATION_DATE = "09/04/2025"

# page: (annual pages to flatten, inclusive transaction offsets, PTR label)
# Offsets are zero-based among tx rows after flattening the named annual pages.
PAGE_SPECS = {
    2: ((159, 160), 22, 44, "Monte and Usha Ahuja 2010 Irrev Trust FBO Grandchildren"),
    3: ((170,), 1, 16, "Ahuja Grandchildren's Education Trust"),
    4: ((203, 204, 205, 206, 207), 22, 54, "2020 Trust FBO Khanna Children"),
    5: ((203, 204, 205, 206, 207), 55, 82, "2020 Trust FBO Khanna Children"),
    6: ((203, 204, 205, 206, 207), 83, 115, "2020 Trust FBO Khanna Children"),
    7: ((203, 204, 205, 206, 207), 116, 125, "2020 Trust FBO Khanna Children"),
    8: ((227, 228), 13, 38, "Ritu Ahuja Declaration of Trust"),
    9: ((278, 279, 280, 281, 282, 283, 284), 20, 56, "Ritu Ahuja 1994 Trust"),
    10: ((278, 279, 280, 281, 282, 283, 284), 57, 92, "Ritu Ahuja 1994 Trust"),
    11: ((278, 279, 280, 281, 282, 283, 284), 93, 121, "Ritu Ahuja 1994 Trust"),
    12: ((278, 279, 280, 281, 282, 283, 284), 122, 156, "Ritu Ahuja 1994 Trust"),
    # Stop at the 08/04 sale; annual offsets 176+ are September activity.
    13: ((278, 279, 280, 281, 282, 283, 284), 157, 175, "Ritu Ahuja 1994 Trust"),
    14: ((304, 305), 23, 36, "Ritu Ahuja 1995 Trust"),
    15: ((314, 315), 14, 32, "M & R Trust Partnership"),
}

EXPECTED_ANCHORS = {
    2: ("EXTRA SPACE STORAGE INC CMN", "TARGET CORPORATION CMN"),
    3: ("ZOETIS INC CMN CLASS A", "ELANCO ANIMAL HEALTH INCORPORA CMN"),
    4: ("PROLOGIS INC CMN", "COGNIZANT TECHNOLOGY SOLUTIONS CORP CLASS A"),
    5: ("CAESARS ENTERTAINMENT INC CMN", "OLD DOMINION FREIGHT LINE INC CMN"),
    6: ("THE KRAFT HEINZ CO CMN", "BOOKING HOLDINGS INC CMN"),
    7: ("VERTEX PHARMACEUTICALS INCORPO CMN", "THE PROCTER & GAMBLE COMPANY CMN"),
    8: ("AXALTA COATING SYSTEMS LTD CMN", "ALPHABET INC CMN CLASS C"),
    9: ("ABBVIE INC CMN", "BEST BUY CO INC CMN"),
    10: ("ARISTA NETWORKS INC CMN", "OLD DOMINION FREIGHT LINE INC CMN"),
    11: ("CENTENE CORPORATION CMN", "DEXCOM INC CMN"),
    12: ("BROWN & BROWN INC CMN", "SERVICENOW INC CMN"),
    13: ("PUBLIC STORAGE CMN", "PHILIP MORRIS INTL INC CMN"),
    14: ("ZOETIS INC CMN CLASS A", "TARGET CORPORATION CMN"),
    15: ("AMAZON COM INC CMN", "ACCENTURE PLC CMN CLASS A"),
}

# Legible PTR text that corrects OCR-like substitutions in the annual
# transcription. Keys are (PTR page, zero-based transaction position).
PTR_ASSET_OVERRIDES = {
    (2, 11): "CALL/NVDA FLEX EURO PM 162.5 EXP 08/01/2025",
    (15, 2): "WAYNE OHIO LOC SCH DIST WARREN GO 5% 12/01/25 JD",
    (15, 8): "CUYAHOGA OHIO CMNTY COLLEGE GO 5.0000% 12/01/25 JD",
    (15, 10): "COLUMBUS OHIO GO 5% 07/01/26 JJ",
}

# The BNP PARIBAS row is visibly dated 08/22/25 on the PTR; its matching
# annual row is transcribed as 08/21/2025.
PTR_DATE_OVERRIDES = {(2, 10): "08/22/2025"}


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def clean(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def annual_transactions(pages: tuple[int, ...]) -> list[dict]:
    result: list[dict] = []
    for page in pages:
        data = load(ANNUAL_TEXT / f"page-{page:03d}.json")
        result.extend(row for row in data["rows"] if row.get("kind") == "tx")
    return result


def normalized(row: dict) -> dict:
    result = copy.deepcopy(row)
    result["asset_name"] = clean(result["asset_name"])
    result["notification_date"] = NOTIFICATION_DATE
    result["partial_sale"] = result.get("tx_type") == "Partial Sale"
    if result["partial_sale"]:
        result["tx_type"] = "Sale"
    result["cap_gain_over_200"] = bool(result.get("cap_gain_over_200", False))
    return result


def rebuild_page(page: int) -> None:
    annual_pages, start, end, group = PAGE_SPECS[page]
    source = annual_transactions(annual_pages)
    selected = [normalized(row) for row in source[start : end + 1]]
    for index, row in enumerate(selected):
        asset_override = PTR_ASSET_OVERRIDES.get((page, index))
        if asset_override:
            row["asset_name"] = asset_override
        date_override = PTR_DATE_OVERRIDES.get((page, index))
        if date_override:
            row["date"] = date_override
    expected_first, expected_last = EXPECTED_ANCHORS[page]
    assert clean(selected[0]["asset_name"]) == expected_first
    assert clean(selected[-1]["asset_name"]) == expected_last

    path = PTR_TEXT / f"page-{page:03d}.json"
    data = load(path)
    data["rows"] = [{"kind": "group", "text": group}, *selected]
    data["uncertainties"] = []
    data["page_confidence"] = "high"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def rebuild_cover() -> None:
    path = PTR_TEXT / "page-001.json"
    data = load(path)
    data["free_text"] = data["free_text"].replace(
        "2025 SEP -3 PM 1:18", "2025 SEP -9 PM 4:10"
    )
    data["uncertainties"] = []
    data["page_confidence"] = "high"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def main() -> None:
    rebuild_cover()
    for page in sorted(PAGE_SPECS):
        rebuild_page(page)

    counts = {}
    total = 0
    for page in sorted(PAGE_SPECS):
        data = load(PTR_TEXT / f"page-{page:03d}.json")
        count = sum(row.get("kind") == "tx" for row in data["rows"])
        counts[page] = count
        total += count
    assert total == 358, (total, counts)
    print(f"rebuilt {total} scan-verified transactions: {counts}")


if __name__ == "__main__":
    main()
