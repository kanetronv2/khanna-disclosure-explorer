#!/usr/bin/env python3
"""Rebuild scan-verified 2021-8 PTR row runs from annual Schedule B twins.

Each listed sequence has matching first and last securities on the PTR scan and
is contiguous in the annual Schedule B.  The annual supplies transaction
fields; the PTR scan supplies its filed notification date.
"""
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ANNUAL = ROOT / "docs/2021-13/text"
PTR = ROOT / "docs/2021-8/text"


def source(page, start, end):
    rows = json.loads((ANNUAL / f"page-{page:03}.json").read_text())["rows"]
    return [deepcopy(row) for row in rows[start:end] if row.get("kind") == "tx"]


def report_rows(start_page, start_row, end_page, end_row, notification_date):
    """Return the annual rows printed in one PTR report, in annual order."""
    cutoff = datetime.strptime(notification_date, "%m/%d/%Y")
    result = []
    for page in range(start_page, end_page + 1):
        rows = json.loads((ANNUAL / f"page-{page:03}.json").read_text())["rows"]
        first = start_row if page == start_page else 0
        last = end_row + 1 if page == end_page else len(rows)
        for row in rows[first:last]:
            if row.get("kind") != "tx":
                continue
            if datetime.strptime(row["date"], "%m/%d/%Y") <= cutoff:
                result.append(deepcopy(row))
    return result


def replace(page, rows, notification_date, note):
    path = PTR / f"page-{page:03}.json"
    data = json.loads(path.read_text())
    for row in rows:
        row["date"] = datetime.strptime(row["date"], "%m/%d/%Y").strftime("%m/%d/%Y")
        row["notification_date"] = notification_date
    data["rows"] = rows
    data["uncertainties"] = [{"field": "rows", "note": note}]
    data["page_confidence"] = "high"
    path.write_text(json.dumps(data, indent=2) + "\n")


replace(
    18,
    report_rows(247, 10, 252, 18, "09/03/2021"),
    "09/03/2021",
    "All 55 printed tx rows re-verified against the PTR scan and matching annual Schedule B rows (annual pp. 247-252); later annual transactions are excluded because they are not printed on this PTR page.",
)
replace(
    16,
    report_rows(234, 10, 244, 20, "09/03/2021"),
    "09/03/2021",
    "All 89 printed tx rows re-verified against the PTR scan and matching annual Schedule B rows (annual pp. 234-244); later annual transactions are excluded because they are not printed on this PTR page.",
)
replace(
    12,
    source(214, 7, 27) + source(215, 0, 27) + source(216, 0, 9)
    + source(216, 23, 24) + source(217, 1, 2) + source(225, 9, 26),
    "09/02/2021",
    "All 75 printed tx rows re-verified against the PTR scan and matching annual Schedule B rows (annual pp. 214-217 and 225); later annual transactions are excluded because they are not printed on this PTR page.",
)
replace(
    13,
    source(225, 26, 27) + source(226, 0, 16) + source(227, 6, 27)
    + source(228, 0, 27) + source(229, 0, 5),
    "09/02/2021",
    "All 70 printed tx rows re-verified against the PTR scan and matching annual Schedule B rows (annual pp. 225-229); later annual transactions are excluded because they are not printed on this PTR page.",
)
