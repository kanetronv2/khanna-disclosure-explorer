#!/usr/bin/env python3
"""Apply two isolated core-field values read from their filed PTR scans."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def save(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def fix_stryker() -> None:
    path = ROOT / "docs" / "2023-6" / "text" / "page-028.json"
    value = load(path)
    rows = [row for row in value["rows"] if row.get("kind") == "tx"]
    matches = [row for row in rows if row.get("asset_name") == "STRYKER CORPORATION CMN"]
    assert len(matches) == 2 and matches[1].get("notification_date") == "07/06/23"
    matches[1]["date"] = "06/22/23"
    value["uncertainties"] = [{
        "row": 8,
        "field": "date",
        "read": "06/22/23",
        "note": "Date read directly from the high-resolution filed PTR scan.",
    }]
    value["page_confidence"] = "high"
    save(path, value)


def fix_tiger_global() -> None:
    path = ROOT / "docs" / "2023-9" / "text" / "page-014.json"
    value = load(path)
    rows = [row for row in value["rows"] if row.get("kind") == "tx"]
    matches = [row for row in rows if row.get("asset_name") == "Tiger Global Crossover Access LLC Class A1 Series 11"]
    assert len(matches) == 1 and matches[0].get("notification_date") == "10/05/23"
    row = matches[0]
    row["date"] = "09/25/23"
    row["amount"] = "$250,001-$500,000"
    row.pop("notes", None)
    row["confidence"] = "high"
    value["uncertainties"] = [{
        "row": 16,
        "field": "date/amount",
        "read": "09/25/23; $250,001-$500,000",
        "note": "Date and amount-column E mark read directly from the high-resolution filed PTR scan.",
    }]
    value["page_confidence"] = "high"
    save(path, value)


def main() -> None:
    fix_stryker()
    fix_tiger_global()


if __name__ == "__main__":
    main()
