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
        if row.get("kind") != "tx":
            continue
        row["date"] = datetime.strptime(row["date"], "%m/%d/%Y").strftime("%m/%d/%Y")
        row["notification_date"] = row.get("notification_date") or notification_date
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

# Page 5 contains two visibly separate account blocks.  The latter changes
# notification date partway through the block; preserve that printed boundary
# rather than assigning a page-wide date.
page5_first = source(190, 1, 14)
page5_early = source(195, 21, 26) + source(196, 0, 27) + source(197, 0, 14)
page5_late = source(197, 14, 27) + source(198, 0, 5)
for row in page5_first + page5_early:
    row["notification_date"] = "09/03/2021"
for row in page5_late:
    row["notification_date"] = "10/04/2021"
replace(
    5,
    page5_first
    + [{"kind": "group", "text": "Annual Investment Group"}]
    + page5_early
    + page5_late,
    None,
    "All 77 printed tx rows re-verified against the PTR scan and matching annual Schedule B rows (annual pp. 190 and 195-198). The scan's 09/03/2021 and 10/04/2021 notification-date runs are preserved; the printed account separator is retained.",
)

# Page 22 starts three rows earlier than the old transcription, ends the SP
# sale run at JetBlue, then switches to the Ritu Ahuja trust's bond rows.
# These bonds were filed in distinct PTRs, so their scan-printed notification
# dates are deliberately per-row rather than inherited from the sale block.
page22_sales = source(275, 16, 27) + source(276, 0, 27) + source(277, 0, 17)
for row in page22_sales:
    row["notification_date"] = "09/02/2021"
page22_bonds = source(285, 25, 26) + source(286, 0, 11)
bond_notifications = [
    "02/02/2021",  # Sedgwick
    "11/05/2021", "11/05/2021",  # New Mexico, Phoenix
    "01/03/2022",  # Dallas
    "02/02/2021", "02/02/2021", "02/02/2021", "02/02/2021",
    "04/06/2021", "06/03/2021", "05/30/2021", "07/01/2021",
]
assert len(page22_bonds) == len(bond_notifications)
for row, notification_date in zip(page22_bonds, bond_notifications):
    row["notification_date"] = notification_date
replace(
    22,
    page22_sales
    + [{"kind": "group", "text": "Ritu Ahuja 2010 Trust"}]
    + page22_bonds,
    None,
    "All 67 printed tx rows re-verified against the PTR scan and matching annual Schedule B rows (annual pp. 275-277 and 285-286). Restored the three leading sales, removed unprinted capital calls, and preserved the scan's individual bond notification dates.",
)
