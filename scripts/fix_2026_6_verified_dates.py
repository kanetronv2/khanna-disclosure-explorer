#!/usr/bin/env python3
"""Reapply the scan-verified June 30 date corrections in PTR 2026-6."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "2026-6" / "text"
CORRECTIONS = {
    20: {
        "COCA-COLA COMPANY (THE) CMN": (9, "Coca-Cola"),
        "BOSTON SCIENTIFIC CORP. COMMON STOCK": (10, "Boston Scientific"),
        "NEWMONT CORP CMN": (15, "Newmont"),
    },
    21: {"INTL BUSINESS MACHINES CORP CMN": (2, "IBM")},
    22: {"PAYPAL HOLDINGS, INC. CMN": (3, "PayPal")},
    24: {"COGNIZANT TECHNOLOGY SOLUTIONS CORP CLASS A": (5, "Cognizant")},
    25: {"FORD MOTOR COMPANY CMN": (2, "Ford")},
}


def main() -> None:
    changed = 0
    for page_number, expected in CORRECTIONS.items():
        path = DOC / f"page-{page_number:03d}.json"
        page = json.loads(path.read_text(encoding="utf-8"))
        by_name = {row.get("asset_name"): (index, row) for index, row in enumerate(page["rows"])}
        for asset_name, (expected_index, short_name) in expected.items():
            index, row = by_name[asset_name]
            assert index == expected_index, (path, asset_name, index, expected_index)
            assert row.get("date") in {"06/20/2026", "06/30/2026"}, (path, asset_name, row.get("date"))
            row["date"] = "06/30/2026"
            note = {
                "row": index,
                "field": "date",
                "read": "06/30/26",
                "note": (
                    "High-resolution scan re-check corrected an earlier 06/20/2026 "
                    f"digit slip for {short_name}."
                ),
            }
            if note not in page["uncertainties"]:
                page["uncertainties"].append(note)
            changed += 1
        path.write_text(json.dumps(page, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"2026-6: enforced {changed} scan-verified 06/30/2026 transaction dates")


if __name__ == "__main__":
    main()
