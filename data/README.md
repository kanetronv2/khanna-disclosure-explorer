# Open data release

This directory is the analysis-ready export of Rep. Ro Khanna's House financial disclosure
filings for 2016–2026. It is generated from the repository's page-level transcriptions; do not
hand-edit generated files.

## Files

Each table is available as newline-delimited JSON (`.jsonl`) and UTF-8 CSV:

- `documents`: one source filing, its type, PDF, and page count.
- `pages`: one scanned page, its normalized and raw page type, confidence, source JSON,
  Tesseract text, image, and uncertainty count.
- `page_rows`: every transcribed row from every filing, including rows intentionally excluded
  from the website's annual aggregates. Its source path and row number locate the complete,
  lossless object in the tracked page-level JSON.
- `assets`: annual Schedule A holdings, including reported ranges and numeric lower/upper bounds.
- `transactions`: Schedule B and PTR trades, including original date text and parsed ISO dates.
- `uncertainties`: every page-level OCR/transcription warning, linked back to its source page.

`manifest.json` lists row counts, SHA-256 checksums, source coverage, schema version, and license.
`quality-report.json` contains the most recent structural audit. The canonical schema is
`schema/open-data.schema.json`.

## Important semantics

- Dollar amounts are statutory ranges, not exact values. `*_min_usd` and `*_max_usd` are the
  disclosed bounds. A null maximum with `*_has_open_upper_bound=true` means the form reported an
  open-ended amount such as “over $1,000,000”; it does not mean zero or missing data.
- `*_reported` fields preserve the transcription exactly enough to audit parsing. Parsed ISO
  dates are nullable; ambiguous or explicitly unknown dates remain in their reported field.
- `owner_code` contains only normalized filing codes (`SP`, `DC`, `JT`, or `SELF`). Illegible or
  unknown source values become null there and remain visible in `owner_reported`.
- On asset and transaction rows, `collection_page_number` is the page's position in a year's
  combined website dataset. `document_page_number` is its page number within the individual
  source PDF/image directory. The canonical `pages` table contains each physical source page
  once, even where the website deliberately reuses a filing in more than one year's view.
- Stable IDs are deterministic for this release schema. They are not identifiers assigned by
  the Clerk of the House.
- OCR and model-assisted transcription can be wrong. Use `page_id`, `source_json_path`, and
  `page_image_path` to verify consequential findings against the filing.

## Rebuild and audit

From the repository root:

```sh
make open-data
```

This recompiles the website datasets, rebuilds the normalized tables and lazy `site-data/`
chunks, checks every referenced
PDF/page image/source JSON/Tesseract file, validates required descriptions and numeric ranges,
and exits nonzero on a hard error. `make audit` rebuilds and audits without recompiling the
website datasets first.

Example with Python:

```python
import json

with open("data/normalized/assets.jsonl") as fh:
    assets = [json.loads(line) for line in fh]

upper_bound = sum(row["value_max_usd"] or 0 for row in assets if row["year"] == 2024)
```

See `DATA_LICENSE.md` for the CC0 dedication and source-material notice.
