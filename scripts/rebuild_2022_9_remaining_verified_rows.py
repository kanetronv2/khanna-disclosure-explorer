#!/usr/bin/env python3
"""Apply additional scan-verified 2022-9 PTR row reconstructions."""
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ANNUAL = ROOT / "docs/2022-15/text"
PTR = ROOT / "docs/2022-9/text"
NOTIFIED = "09/06/2022"


def source(page, start, end):
    rows = json.loads((ANNUAL / f"page-{page:03}.json").read_text())["rows"]
    return [deepcopy(row) for row in rows[start:end] if row.get("kind") == "tx"]


def replace(page, rows, note):
    path = PTR / f"page-{page:03}.json"
    data = json.loads(path.read_text())
    for row in rows:
        if row.get("kind") != "tx":
            continue
        row["date"] = datetime.strptime(row["date"], "%m/%d/%Y").strftime("%m/%d/%Y")
        row["notification_date"] = NOTIFIED
        row["partial_sale"] = row.get("tx_type") == "Partial Sale"
    data["rows"] = rows
    data["uncertainties"] = [{"field": "rows", "note": note}]
    data["page_confidence"] = "high"
    path.write_text(json.dumps(data, indent=2) + "\n")


replace(
    10,
    source(206, 3, 7) + source(228, 17, 30) + source(229, 0, 2),
    "All 19 printed transactions re-verified against the PTR scan and matching annual Schedule B rows (annual pp. 206, 228, and 229).",
)

replace(
    13,
    source(230, 10, 20)
    + [{"kind": "group", "text": "Ritu Ahuja Declaration of Trust"}]
    + source(238, 16, 17)
    + [{"kind": "group", "text": "Ritu Ahuja 1994 Trust"}]
    + source(240, 20, 21) + source(250, 5, 10),
    "All 17 printed transactions re-verified against the PTR scan and matching annual Schedule B rows (annual pp. 230, 238, 240, and 250).",
)

page18_options = source(285, 12, 13) + source(335, 13, 16)
for option in page18_options:
    option["asset_name"] = option["asset_name"].replace("PUTXSP", "PUT/XSP")

replace(
    18,
    source(284, 27, 30) + source(285, 0, 12) + page18_options,
    "All 19 printed transactions re-verified against the PTR scan and matching annual Schedule B rows (annual pp. 284-285 and 335), including the four printed PUT/XSP option rows.",
)

page19 = json.loads((PTR / "page-019.json").read_text())
replace(
    19,
    [
        row for row in page19["rows"]
        if row.get("asset_name") not in {
            "ALPHABET INC. CMN CLASS C",
            "PHILIP MORRIS INTL INC CMN",
        }
    ] + source(335, 16, 17),
    "All printed transactions re-verified against the PTR scan; replaced the unprinted trailing Alphabet row with the scan-printed Philip Morris row from annual Schedule B p. 335.",
)
