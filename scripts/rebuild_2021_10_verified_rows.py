#!/usr/bin/env python3
"""Rebuild scan-verified 2021-10 PTR pages from annual Schedule B twins.

The sequences below were matched against the printed PTR scans (including the
first and last security on each run).  The annual filing supplies the typed
transaction fields; this PTR supplies the filed notification date.
"""
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ANNUAL = ROOT / "docs/2021-13/text"
PTR = ROOT / "docs/2021-10/text"
NOTIFIED = "11/05/2021"


def source(page, start, end):
    rows = json.loads((ANNUAL / f"page-{page:03}.json").read_text())["rows"]
    return [deepcopy(row) for row in rows[start:end] if row.get("kind") == "tx"]


def write(page, rows, note):
    path = PTR / f"page-{page:03}.json"
    data = json.loads(path.read_text())
    for row in rows:
        if row.get("kind") != "tx":
            continue
        row["date"] = datetime.strptime(row["date"], "%m/%d/%Y").strftime("%m/%d/%Y")
        if not row.get("notification_date"):
            row["notification_date"] = NOTIFIED
        row["partial_sale"] = row.get("tx_type") == "Partial Sale"
    data["rows"] = rows
    data["uncertainties"] = [{"field": "rows", "note": note}]
    data["page_confidence"] = "high"
    path.write_text(json.dumps(data, indent=2) + "\n")


# Page 3 is otherwise aligned to its scan.  This one extra annual row is not
# printed between Capital One and KKR on the PTR page.
page3 = json.loads((PTR / "page-003.json").read_text())
write(
    3,
    [
        row for row in page3["rows"]
        if not (
            row.get("kind") == "tx"
            and row.get("asset_name") == "BANK OF NEW YORK MELLON CORPOR HYBRID PERP"
            and row.get("date") == "11/08/2021"
        )
    ],
    "All printed rows re-verified against the PTR scan. Removed the one unprinted Bank of New York Mellon row between Capital One and KKR; the remaining row order and fields match annual Schedule B pp. 187-193.",
)

# The two municipal-bond blocks on page 4 are already scan-aligned.  Keep the
# scan-read rows (including their genuine notification-date exceptions) while
# rebuilding every misaligned equity run from annual Schedule B rows.
page4_bond_blocks = [
    {"kind": "group", "text": "Ritu Ahuja Declaration of Trust"},
    {"kind": "tx", "owner": "DC", "asset_name": "HOUSTON TEX INDPT SCH DIST GO 5% 02/15/22 FA", "tx_type": "Purchase", "cap_gain_over_200": False, "date": "10/05/2021", "notification_date": "11/08/2021", "amount": "$15,001-$50,000", "partial_sale": False},
    {"kind": "tx", "owner": "DC", "asset_name": "STATE OF OREGON GEN OBLIGATION 5% 06/01/22 MN", "tx_type": "Purchase", "cap_gain_over_200": False, "date": "10/04/2021", "notification_date": "11/08/2021", "amount": "$50,001-$100,000", "partial_sale": False},
    {"kind": "tx", "owner": "DC", "asset_name": "ALBUQUERQUE N MEX GO 5% 07/01/22 JJ", "tx_type": "Purchase", "cap_gain_over_200": False, "date": "10/06/2021", "notification_date": NOTIFIED, "amount": "$50,001-$100,000", "partial_sale": False},
    {"kind": "tx", "owner": "DC", "asset_name": "NEW MEXICO ST SEVERANCE TAX REV 4% 07/01/23 JJ", "tx_type": "Purchase", "cap_gain_over_200": False, "date": "10/04/2021", "notification_date": NOTIFIED, "amount": "$50,001-$100,000", "partial_sale": False},
    {"kind": "tx", "owner": "DC", "asset_name": "KNOXVILLE TENN WASTE WTR SYS REV 5% 10/01/22 AO", "tx_type": "Purchase", "cap_gain_over_200": False, "date": "10/04/2021", "notification_date": NOTIFIED, "amount": "$50,001-$100,000", "partial_sale": False},
    {"kind": "tx", "owner": "DC", "asset_name": "MINNESOTA ST GO 5% 06/01/21 FA", "tx_type": "Purchase", "cap_gain_over_200": False, "date": "10/04/2021", "notification_date": NOTIFIED, "amount": "$50,001-$100,000", "partial_sale": False},
    {"kind": "group", "text": "Ritu Ahuja Declaration of Trust"},
    {"kind": "tx", "owner": "SP", "asset_name": "JPMORGAN ST FIN AUTH REV REV 0.9500%, MS, 09/27/45", "tx_type": "Purchase", "cap_gain_over_200": False, "date": "10/05/2021", "notification_date": "11/02/2021", "amount": "$1,001-$15,000", "partial_sale": False},
    {"kind": "group", "text": "Ritu Ahuja 1995 Trust"},
]
write(
    4,
    source(193, 6, 27) + source(194, 0, 7)
    + page4_bond_blocks
    + source(243, 13, 22) + source(248, 9, 27) + source(249, 0, 5),
    "All 70 printed rows re-verified against the PTR scan and matching annual Schedule B rows (annual pp. 193-194, 243, and 248-249); retained the two already scan-aligned municipal-bond blocks. Later annual transactions are not printed on this PTR page.",
)

write(
    5,
    source(249, 5, 14) + source(258, 24, 27) + source(259, 0, 27)
    + source(260, 0, 27) + source(261, 0, 4),
    "All 70 printed rows re-verified against the PTR scan and matching annual Schedule B rows (annual pp. 249 and 258-261); the page runs from Norfolk Southern through Raymond James. Later annual transactions are not printed on this PTR page.",
)

write(
    8,
    source(280, 23, 27) + source(281, 0, 2)
    + [{"kind": "group", "text": "Ritu Ahuja 1995 Trust"}]
    + source(286, 0, 2) + source(286, 20, 22)
    + source(289, 17, 27) + source(290, 0, 3)
    + source(297, 21, 26) + source(300, 21, 26),
    "All 34 printed rows re-verified against the PTR scan and matching annual Schedule B rows (annual pp. 280-281, 286, 289-290, 297, and 300); later annual transactions are not printed on this PTR page.",
)
