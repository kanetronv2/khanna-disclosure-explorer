#!/usr/bin/env python3
"""Build a conservative, source-traceable 2024-versus-2025 asset comparison."""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data" / "normalized" / "assets.csv"
OUTPUT = ROOT / "data" / "asset-comparison-2024-2025.csv"
YEARS = ("2024", "2025")


def ordered_unique(values):
    """Keep the source order while dropping blank/repeated values."""
    return list(dict.fromkeys(value for value in values if value))


def aggregate(rows):
    """Combine the separately reported holdings of one named asset in a filing year."""
    if not rows:
        return None
    lower_bounds = [int(row["value_min_usd"]) for row in rows if row["value_min_usd"]]
    has_unparsed_bound = len(lower_bounds) != len(rows)
    upper_bounds = [int(row["value_max_usd"]) for row in rows if row["value_max_usd"]]
    has_open_upper_bound = any(
        row["value_has_open_upper_bound"].lower() == "true" for row in rows
    )
    return {
        "asset_class": " | ".join(ordered_unique(row["asset_class"] for row in rows)),
        "description": " | ".join(ordered_unique(row["description"] for row in rows)),
        "holding_count": len(rows),
        "reported_value_bands": " | ".join(
            ordered_unique(row["reported_value"] for row in rows)
        ),
        "value_min_usd": "" if has_unparsed_bound else sum(lower_bounds),
        "value_max_usd": "" if has_unparsed_bound or has_open_upper_bound else sum(upper_bounds),
        "value_has_open_upper_bound": has_open_upper_bound,
    }


def comparison(old, new):
    """Only call a direction where the reported statutory ranges prove one."""
    if not old or not new:
        return ""
    old_lo, old_hi = old["value_min_usd"], old["value_max_usd"]
    new_lo, new_hi = new["value_min_usd"], new["value_max_usd"]
    if "" in (old_lo, old_hi, new_lo, new_hi):
        return "not_comparable"
    if (old_lo, old_hi) == (new_lo, new_hi):
        return "same_reported_range"
    if new_lo > old_hi:
        return "higher"
    if new_hi < old_lo:
        return "lower"
    return "overlapping_reported_ranges"


def values(year, aggregate):
    """Return the year-specific CSV cells, blank when the asset was not reported."""
    if not aggregate:
        return {
            f"{year}_asset_class": "",
            f"{year}_description": "",
            f"{year}_holding_count": "",
            f"{year}_reported_value_bands": "",
            f"{year}_value_min_usd": "",
            f"{year}_value_max_usd": "",
            f"{year}_value_has_open_upper_bound": "",
        }
    return {
        f"{year}_asset_class": aggregate["asset_class"],
        f"{year}_description": aggregate["description"],
        f"{year}_holding_count": aggregate["holding_count"],
        f"{year}_reported_value_bands": aggregate["reported_value_bands"],
        f"{year}_value_min_usd": aggregate["value_min_usd"],
        f"{year}_value_max_usd": aggregate["value_max_usd"],
        f"{year}_value_has_open_upper_bound": aggregate["value_has_open_upper_bound"],
    }


def main():
    with INPUT.open(encoding="utf-8", newline="") as fh:
        source_rows = [row for row in csv.DictReader(fh) if row["year"] in YEARS]

    grouped = defaultdict(lambda: defaultdict(list))
    for row in source_rows:
        # Asset names are the only consistent identifier across the two annual filings.
        # Normalizing case/spacing makes the match resilient without attempting fuzzy matches.
        key = " ".join(row["asset_name"].upper().split())
        grouped[key][row["year"]].append(row)

    output_rows = []
    for _, by_year in sorted(grouped.items(), key=lambda item: item[0]):
        old = aggregate(by_year["2024"])
        new = aggregate(by_year["2025"])
        asset_name = (by_year["2025"] or by_year["2024"])[0]["asset_name"]
        output_rows.append({
            "asset_name": asset_name,
            **values("2024", old),
            **values("2025", new),
            "2025_vs_2024": comparison(old, new),
        })

    fields = list(output_rows[0]) if output_rows else ["asset_name", "2025_vs_2024"]
    with OUTPUT.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(output_rows)
    print(f"wrote {len(output_rows):,} assets to {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
