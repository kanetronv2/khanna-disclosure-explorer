# 2024 versus 2025 asset comparison

`asset-comparison-2024-2025.csv` compares annual Schedule A asset holdings from the
normalized 2024 and 2025 filings. Run `python3 scripts/build_asset_comparison.py` from
the repository root to rebuild it.

Each row represents one exact printed asset name, matched case-insensitively and after
whitespace normalization. Holdings under that name are aggregated across owners and
portfolio groups within each annual filing. The `*_holding_count` columns make that
aggregation explicit; `*_reported_value_bands` preserves each distinct filed band, while
the numeric `*_value_min_usd` and `*_value_max_usd` columns are their combined bounds.

The forms report ranges, not exact valuations. `2025_vs_2024` is `higher` or `lower` only
when the two combined reported ranges do not overlap. It is `same_reported_range` for
identical bounds, `overlapping_reported_ranges` where the data cannot establish a direction,
and blank when the asset appears in only one year. `not_comparable` indicates an unparsed
or open-ended bound that prevents a directional conclusion.

The year-specific description columns preserve the filings' prose descriptions. An asset
that has multiple descriptions within a year retains all distinct descriptions separated by
` | `.
