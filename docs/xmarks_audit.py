#!/usr/bin/env python3
"""Cross-check transcribed Form A pages against the pixel checkbox detector.

Every schedule_a page's Block B/C/D readings are compared against docs/xmarks.py's
geometric measurement of which column holds an X. Disagreements are the pages worth
re-opening against the scan: this is what caught the p.57 ELI LILLY misread in 2025-14.

Usage: python3 docs/xmarks_audit.py [doc]        (default doc: 2025-14)
Exit status is 0 always - this is a review aid, not a gate; read the report.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bmarks
import xmarks

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def one(value_list):
    """The detector's reading when it is unambiguous (exactly one column marked)."""
    return value_list[0] if len(value_list) == 1 else None


def main():
    doc = sys.argv[1] if len(sys.argv) > 1 else "2025-14"
    root = os.path.join(REPO, "docs", doc)
    text_dir = os.path.join(root, "text")
    pages = sorted(int(f[5:8]) for f in os.listdir(text_dir) if f.startswith("page-"))

    checked = skipped = cells = 0
    mismatches, structural = [], []
    for page in pages:
        js = json.load(open(os.path.join(text_dir, f"page-{page:03d}.json")))
        kind = js.get("page_type")
        if kind not in ("schedule_a", "schedule_b"):
            continue
        det = (xmarks if kind == "schedule_a" else bmarks).analyze(page, root)
        if det.get("error") or "rows" not in det:
            structural.append((page, det.get("error", "no rows"))); skipped += 1; continue
        drows = det["rows"]
        # Schedule B grids carry an extra leading "SP DC JT | ASSET" header strip.
        if kind == "schedule_b" and len(drows) == len(js.get("rows") or []) + 1:
            drows = drows[1:]
        if len(js.get("rows") or []) != len(drows):
            structural.append((page, f"row count json={len(js.get('rows') or [])} detector={len(det['rows'])}"))
            skipped += 1; continue
        checked += 1
        if kind == "schedule_b":
            for row, drow in zip(js["rows"], drows):
                if row.get("kind") != "tx":
                    continue
                for field, key in (("tx_type", "tx"), ("amount", "amt")):
                    measured = one(drow[key])
                    if measured is None or row.get(field) is None:
                        continue
                    cells += 1
                    if measured != row[field]:
                        mismatches.append((page, row.get("asset_name", "")[:34], field,
                                           row[field], measured))
                if row.get("cap_gain_over_200") is not None:
                    cells += 1
                    if bool(row["cap_gain_over_200"]) != drow["capgain"]:
                        mismatches.append((page, row.get("asset_name", "")[:34], "cap_gain",
                                           row["cap_gain_over_200"], drow["capgain"]))
            continue
        for row, drow in zip(js["rows"], drows):
            if row.get("kind") != "asset":
                continue
            for field, key in (("value", "value"), ("amount_of_income", "amt")):
                measured = one(drow[key])
                if measured is None or row.get(field) is None:
                    continue
                cells += 1
                if measured != row[field]:
                    mismatches.append((page, row.get("asset_name", "")[:34], field, row[field], measured))
            # The last Block C column is the "Other Type of Income" write-in, so the
            # detector sees the specified text (e.g. "PTN") as ink rather than an X.
            # That text belongs in other_income_spec, not income_types - ignore it here.
            got = set(row.get("income_types") or [])
            want = set(drow["inc"]) - {"OTHER"}
            if got and want and got != want:
                mismatches.append((page, row.get("asset_name", "")[:34], "income_types",
                                   ",".join(sorted(got)), ",".join(sorted(want))))

    print(f"{doc}: {checked} schedule_a+b pages checked, {cells} bucket cells compared, "
          f"{len(mismatches)} mismatches, {skipped} skipped")
    for page, name, field, transcribed, measured in mismatches:
        print(f"  p{page:03d} {name:<34} {field}: json={transcribed!r} detector={measured!r}")
    for page, why in structural:
        print(f"  p{page:03d} SKIPPED: {why}")


if __name__ == "__main__":
    main()
