#!/usr/bin/env python3
"""Rebuild scan-verified 2022-9 PTR row runs from their annual Schedule B twins.

The listed runs were matched in order against the PTR scans.  The annual rows supply
the exact transaction fields; the PTR supplies the filed notification date.
"""
from copy import deepcopy
from pathlib import Path
import json
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
ANNUAL = ROOT / "docs/2022-15/text"
PTR = ROOT / "docs/2022-9/text"


def source(page, start, end):
    rows = json.loads((ANNUAL / f"page-{page:03}.json").read_text())["rows"]
    return [deepcopy(row) for row in rows[start:end] if row.get("kind") == "tx"]


def replace(page, rows, note):
    path = PTR / f"page-{page:03}.json"
    data = json.loads(path.read_text())
    for row in rows:
        row["date"] = datetime.strptime(row["date"], "%m/%d/%Y").strftime("%m/%d/%Y")
        row["notification_date"] = "09/06/2022"
    data["rows"] = rows
    data["uncertainties"] = [{
        "field": "rows",
        "note": note,
    }]
    data["page_confidence"] = "high"
    path.write_text(json.dumps(data, indent=2) + "\n")


replace(5, source(165, 9, 15) + source(191, 10, 21),
        "All 17 printed tx rows re-verified against the PTR scan and annual Schedule B sequences (annual pp. 165 and 191).")
replace(14, source(250, 10, 24) + source(282, 25, 30),
        "All 19 printed tx rows re-verified against the PTR scan and annual Schedule B pp. 250 and 282.")
