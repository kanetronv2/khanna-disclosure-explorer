# Ro Khanna Financial Disclosure Open Data

An open, reproducible data dump and static explorer of Rep. Ro Khanna's U.S. House financial
disclosure filings from 2016–2026. The repository includes the source PDFs, 4,460 page images,
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
`/api/v1/issuers/nvidia/comparisons/2024-2025.json` returns the reported bounds, calculation,
evidence records, and cross-year comparability warning together. A `.txt` representation is
available at the same resource path. The legacy `/api/v1/compare` query remains available for
compatibility and unregistered-name searches.

## Fork this for another House member

You can fork this repository and ask a coding LLM to turn it into the same kind of explorer for
another member of the U.S. House. This is a reproducible project, but it is not yet a one-command
white-label template: the current filing corpus, member identity, domain, repository links,
photograph, source registry, examples, and some validation assertions are specific to Ro Khanna.
An LLM should migrate those surfaces deliberately and regenerate the derived files. A blind global
name replacement is not sufficient and must never be run across filing transcriptions.

### Information to give the LLM

Collect these details before starting. It is fine to leave optional fields blank and ask the LLM
to find them from official sources.

| Field | Example format |
| --- | --- |
| Public display name | `Rep. Jane Smith` |
| Name printed on filings | `Jane A. Smith` |
| State and district | `New York 12th` / `NY-12` |
| Congress.gov or Bioguide identifier | `S000000` |
| Filing years to include | `2022–2026` |
| Official House Clerk filing URLs or IDs | One annual filing and every PTR for each year |
| New public domain | `https://disclosures.example.org` |
| Fork URL | `https://github.com/owner/repository` |
| Evidence-file origin | An HTTPS bucket/domain for PDFs and page scans |
| Portrait and attribution | A licensed local image plus source/credit text |

Use the official House Clerk disclosure site as the authority for annual reports and periodic
transaction reports (PTRs). Preserve the filing ID and original PDF for every document. If an
official field is blank, illegible, internally inconsistent, or printed with an unusual date,
record that limitation rather than inventing a correction.

Rebuilding the included corpus needs only Python 3. Ingesting a new corpus may also require a PDF
rasterizer such as Poppler (`pdftoppm`) and an OCR engine such as Tesseract. OCR accelerates review;
it does not replace visual verification of the filed page.

### Copy-paste LLM request

Replace the bracketed values, paste this request into a coding LLM opened at the root of your fork,
and attach or identify the filing PDFs. The prompt is intentionally explicit so the agent performs
the rebuild instead of merely proposing one.

```text
Rebuild this repository as a financial-disclosure explorer for a different U.S. House member.

Target member
- Display name: [DISPLAY NAME]
- Filing/legal name: [NAME PRINTED ON FILINGS]
- State and district: [STATE AND DISTRICT]
- Bioguide or Congress.gov ID: [ID OR UNKNOWN]
- Filing years: [YEARS]
- Official filing URLs/IDs: [LIST, OR "find them on the official House Clerk site"]
- Canonical site origin: [HTTPS DOMAIN]
- GitHub repository: [FORK URL]
- Evidence origin: [HTTPS EVIDENCE ORIGIN]
- Portrait path, alt text, and credit: [IMAGE DETAILS]

Do the migration; do not stop at a plan.

1. Begin with read-only discovery. Read README.md, data/README.md, docs/VERIFY_NOTES.md,
   Makefile, the templates, the build scripts, the API handlers, and the deployment workflow.
   Check git status and preserve unrelated work. Inventory every member-specific string with rg,
   including names, district labels, domains, repository URLs, official links, image names,
   issuer examples, schema metadata, tests, and generated pages.

2. Create one central member/site configuration file for identity, district, canonical origin,
   repository, portrait metadata, and date coverage. Refactor generators and checks to read it.
   Keep document-specific official URLs and filing IDs in lib/source-registry.json. Do not merely
   scatter the new member's name through the same hard-coded locations.

3. Replace the Khanna filing corpus with the target member's corpus. Keep each original PDF and a
   stable document ID. Render every page, retain OCR as a secondary aid, and create page-level
   structured JSON matching the existing schemas. Remove old-member data only after resolving the
   exact replacement scope; never mix records belonging to two members.

4. Verify scans before structured data. The scan is authoritative, the structured JSON follows
   it, and OCR is only a third opinion. Check whole-row alignment, account/trust headings, owner
   codes, dates, notification dates, transaction type, amount band, and checkbox fields. Do not
   "fix" a suspicious date without confirming that the asset and every other field belong to the
   same printed row. Preserve genuine filed-form anomalies and document uncertainty explicitly.

5. Replace the public identity and editorial surfaces: titles, descriptions, schema.org Person and
   Dataset objects, FAQ copy, navigation, portrait/credit, domain, repository links, methodology,
   source provenance, API descriptions, llms.txt, facts files, OpenAPI, robots/sitemap rules, and
   the not-found page. Remove Khanna-specific political/editorial links unless an equivalent,
   sourced statement is appropriate for the target member.

6. Review lib/issuer-registry.json rather than inheriting its examples blindly. Retain aliases only
   when the target corpus supports them, and rebuild all issuer comparison/API output from the new
   records. Never rewrite the raw filed asset name merely to match a registry entry.

7. Regenerate outputs; do not hand-edit generated HTML, data-YYYY.js, site-data, normalized CSV or
   JSONL, facts files, llms files, OpenAPI, sitemap, or vercel.json. Update the owning templates,
   configuration, source JSON, and generators, then run the build.

8. Validate the finished migration with at least:
      make open-data
      make audit
      node scripts/check_api_handlers.js
      python3 -m py_compile scripts/*.py docs/compile17.py
      git diff --check
   Serve it locally with python3 -m http.server 8742 and inspect the root page, every year,
   Assets, Transactions, Document, /stock-trades/, API discovery, evidence links, desktop layout,
   and mobile layout. Exercise dynamic API handlers, not just static files.

9. Prove that the old member is gone from code and public/generated output. Review every remaining
   match from a case-insensitive search for Ro Khanna, Rohit Khanna, rokhanna, CA-17,
   California 17th, khanna.house.gov, and the original repository/domain. Do not delete legitimate
   license or Git-history references without reason, but report every intentional remainder.

10. Report the exact filing/document/page/row counts, unresolved scan limitations, commands run,
    browser checks, and changed paths. Do not commit, push, publish evidence, or deploy unless I
    explicitly ask for those actions.
```

### Migration map

The LLM should discover the current tree rather than rely only on this list, but these are the main
ownership boundaries:

- `docs/src/`, `docs/<document>/`, and `ocr/` hold the original filings, scans, OCR, and page JSON.
- `docs/compile17.py` and `ocr/compile.py` compile those source records into yearly datasets.
- `lib/source-registry.json` maps local document IDs to official House filing URLs.
- `lib/evidence-config.json` and the `EVIDENCE_ORIGIN` environment variable control scan/PDF URLs.
- `templates/` owns the rendered site structure; `scripts/build_pages.py` supplies page metadata
  and copy; `scripts/build_llm_access.py` owns machine-readable discovery documents.
- `scripts/build_open_data.py`, `scripts/build_site_data.py`, and `scripts/evidence_assets.py` own
  normalized data, compact site chunks, and source provenance.
- `lib/issuer-registry.json` is reviewed normalization metadata, not a substitute for transcription.
- `scripts/check_llm_access.py`, API-handler checks, and deploy-tree checks include domain- and
  corpus-specific assertions that must be migrated with the site.
- `data-YYYY.js`, `data/normalized/`, `site-data/`, `YYYY/index.html`, `machine/`, `llms*.txt`,
  `sitemap.xml`, and `vercel.json` are generated outputs.

The migration is complete only when every public record belongs to the target member, every record
links to its source page, generated counts come from the new corpus, the audit passes, and no public
surface silently retains the old member's identity or filings.

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

## Slim production deployment

The source repository intentionally retains filing PDFs, page scans, OCR material, and generated
open data. Vercel applies `.vercelignore` only after cloning, so those multi-gigabyte source objects
must not be reachable from the branch Vercel clones.

Production uses two release surfaces:

- `main` remains the auditable source and generated-data history.
- An orphan `deploy` branch contains only the website, read-only API handlers, compact `site-data`,
  and discovery documents. Filing PDFs and page scans are served from the HTTPS origin configured
  as `EVIDENCE_ORIGIN`.

Build or validate the immutable evidence manifest with:

```sh
make evidence-manifest
make evidence-check
```

`scripts/publish_evidence.py` uploads exactly the files named in that manifest through an
already-configured `rclone` remote. It deliberately uses `copy`, not `sync`, so publishing cannot
delete remote evidence accidentally. Verify the remote after uploading:

```sh
python3 scripts/publish_evidence.py r2:member-disclosures
python3 scripts/publish_evidence.py r2:member-disclosures --check-only
```

To exercise the slim tree in a disposable checkout:

```sh
EVIDENCE_ORIGIN=https://evidence.example.org python3 scripts/build_site_data.py
EVIDENCE_ORIGIN=https://evidence.example.org python3 scripts/build_pages.py
EVIDENCE_ORIGIN=https://evidence.example.org python3 scripts/build_llm_access.py
EVIDENCE_ORIGIN=https://evidence.example.org make deploy-tree
```

The deploy-tree validator rejects local scan/PDF directories, relative evidence URLs, trees over
200 MiB, and runtime configuration that disagrees with the generated evidence origin. The GitHub
workflow `.github/workflows/publish-deploy.yml` performs a blob-filtered sparse checkout and
force-publishes a one-commit `deploy` branch only after the repository variable
`EVIDENCE_ORIGIN` is configured. Point Vercel's Production Branch at `deploy` only after the
evidence origin and a preview deployment have both passed live verification. The generated
deploy-branch `vercel.json` disables automatic deployments from `main`, preventing future source
pushes from cloning the multi-gigabyte branch for unused previews.

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
machine/v1/            generated API discovery, issuer JSON/text, and OpenAPI documents
api/v1/                read-only evidence, search, and comparison handlers
lib/issuer-registry.json reviewed issuer aliases kept separate from raw filed names
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
