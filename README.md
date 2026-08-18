# Ro Khanna Financial Disclosure Open Data

An open, reproducible data dump and static explorer of Rep. Ro Khanna's U.S. House financial
disclosure filings from 2016–2026. The repository includes the source PDFs, 4,057 page images,
page-level structured transcriptions, raw Tesseract text, normalized analysis tables, quality
reports, and the code used to compile them.

The data is designed for independent analysis. Every normalized record links back to a page,
source JSON file, and scan. Dollar figures remain the statutory ranges reported on the forms;
the filings generally do not disclose exact values.

Machine clients can begin at [`llms.txt`](llms.txt), use the OpenAPI description at
`/api/v1/openapi.json`, or retrieve a compact Markdown and facts JSON document from each year
directory. Stable API routes expose the complete per-year arrays without requiring a client to
discover content-hashed website files. The issuer comparison API joins reviewed filing-name
variants without rewriting the raw transcription; for example,
`/api/v1/compare?entity=NVDA&years=2024,2025` returns the reported bounds, evidence records,
and any cross-year comparability warning together.

## Use the data

Start with [`data/README.md`](data/README.md). The main tables are in `data/normalized/`, in
both newline-delimited JSON and CSV:

- `assets` — annual Schedule A holdings with numeric lower and upper bounds.
- `transactions` — annual Schedule B and PTR transactions with reported and ISO dates.
- `documents`, `pages`, and `page_rows` — source/provenance indexes and every raw row.
- `uncertainties` — OCR and transcription warnings linked to individual pages.

`data/manifest.json` provides row counts and SHA-256 checksums. `data/quality-report.json`
records the latest full audit.

## Reproduce the release

Python 3 is the only runtime dependency:

```sh
make open-data
```

That command recompiles every year, rebuilds the normalized dump, and fails if the structural
audit finds missing source artifacts, pending pages, blank required text, invalid ranges, or
drift in the LLM/API discovery surfaces.

## Run the website

```sh
python3 -m http.server 8742
# open http://localhost:8742/
```

The explorer is static: generated HTML, lazy chunks under `site-data/`, `timeline-data.js`, and
the page images. The overview loads only a compact summary; holdings, transactions, document
indexes, page transcriptions, and scans load when requested. The Overview, Assets, Transactions,
and Document views allow browsing the same source-backed records without writing code.

The served HTML is generated, not hand-edited. `templates/index.html` is the single source; run

```sh
make pages
```

to render `index.html` (the newest annual filing) plus one directory per remaining year
(`2019/index.html`, …) and regenerate `sitemap.xml`. Each page ships the overview figures as
real markup rather than leaving them to client-side rendering, so the filing totals are
readable without JavaScript and every year has its own indexable URL.

`make pages` also generates `llms.txt`, `llms-full.txt`, annual `index.md` and `facts.json`
documents, the OpenAPI files, and stable Vercel rewrites for the read-only API. After a verified
production deployment, `make indexnow` submits the canonical sitemap URLs to IndexNow.

## Repository map

```text
data/normalized/       generated JSONL and CSV analysis tables
data/manifest.json     checksums, counts, coverage, schema version
data/quality-report.json structural audit result
docs/src/              original PDFs for 2016–2023 and 2025–2026
docs/<document>/pages/ readable page scans
docs/<document>/text/  page-level structured transcriptions
docs/<document>/tess/  raw Tesseract output
ocr/                   equivalent 2024 source/transcription pipeline
data-YYYY.js           generated website datasets
site-data/             generated, content-hashed lazy website chunks
machine/v1/            generated API discovery and OpenAPI documents
api/v1/                read-only evidence lookup and search handlers
companies/             generated, indexable issuer summaries with Markdown alternates
data/issuer-registry.json reviewed issuer aliases kept separate from raw filed names
templates/index.html   source template for every generated page
index.html, YYYY/      generated HTML, Markdown, and facts JSON (build with: make pages)
scripts/               release, audit, and page-rendering tooling
```

## Method and limitations

The filings are image scans. Pages were transcribed from full-page images and high-resolution
crops, cross-checked against Tesseract, and annotated with uncertainties. This is a best-effort
transcription and can contain errors. Verify consequential findings against the included scans
and official filings. Open-ended reported ranges retain a null upper bound and an explicit
`*_has_open_upper_bound` flag; they must not be treated as zero.

Code is MIT licensed. Contributor-created transcriptions and normalized data are dedicated to
the public domain under CC0. See [`DATA_LICENSE.md`](DATA_LICENSE.md) for source-material and
third-party-rights caveats.
