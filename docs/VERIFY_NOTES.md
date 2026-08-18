# Verification / finalization checklist (run once 2017–2026 fully transcribed)

Accumulated during the 2018–2026 OCR marathon. The transcribed per-page JSON is
faithful; most items below are compile-time (aggregation/display) fixes that need
the FULL structure of each annual visible, plus targeted re-reads.

## 1. Annual Schedule-A block-split merge — TWO layouts (IMPORTANT)
Form A annuals split each asset's attributes across separate sheets. Two layouts seen:
- **Interleaved triplets** (2018-4): pages go Value, Income, Amount for the SAME asset
  set, repeating. Handled by `merge_block_runs` (consecutive disjoint blocks, same group,
  equal counts) — verified collapsing 3→1 on 2018-4 pp55-57.
- **Grouped-by-block** (2019-2): ALL Value pages, then ALL Income pages, then ALL Amount
  pages, each covering different alphabetical subsets of the same trust. Consecutive pages
  share the SAME block, so `merge_block_runs` does NOT merge them → assets fragment into
  value-only / income-only / amount-only rows and inflate counts.
- **FIX (finalization):** replace/augment with **name-based merge within each annual doc**:
  group asset rows by (normalized trust group, asset_name), then combine fields (value,
  income_types/other_income, amount_of_income[_preceding/current], transaction, eif) from
  whichever fragment set each. This handles BOTH layouts uniformly. Re-verify each annual
  year's asset count is sane (no 2x/3x inflation) after.

## 2. Transaction-code decoding (display)
Annual Schedule-A "Transaction Summary" uses P / PS / FS = Purchase / Partial Sale / Full
Sale (not the standard P/S). Extend index.html `txWords` decoder: P→Purchased,
PS→Partial sale, FS→Full sale (keep existing S→Sold, S(part)→Partial sale, E→Exchanged).

## 3. Re-read low/medium-confidence & flagged pages
- Wide **value-matrix** Schedule A pages (e.g. 2019-2 pp29-30): single X across 12 far-apart
  bucket columns — low confidence on exact bucket. Re-read at higher zoom / pixel-column
  detection.
- Amount-of-income block sheets: recurring "whole block could be one bucket off" calibration
  flag (2018-4 pp87/90 etc.). Standardize the Min/Max header→bucket mapping and re-verify.
- Any page with page_confidence low/medium or non-empty uncertainties.

## 4. Cross-year consistency
- All value/income/amount bucket strings match the SPEC enums (no OCR variants).
- Group aliases normalized (e.g. "Ritu Ahuja 1994 Trust" spelling consistent; the 1994 vs
  1995 trust are distinct — confirmed).
- descriptors.json covers 100% of asset names across ALL years (docs/descr-missing-*.json empty).
- Each year (2016–2026) loads in preview: cards, Assets/Transactions tables, filters,
  Document tab, no console errors. PTR-only years (2025/2026) show the "No annual filing"
  card and hidden holdings panels.
- Some docs filed as "PTR" are actually Form A amendments (2018-2, 2019-1) — transcribed with
  asset schema, browsable, correctly NOT feeding aggregates. Confirm.

## 5. Deploy-size check (at push time)
~11 years of page scans (~4,000 JPGs, multiple GB). Assess git/Vercel size; consider Git LFS
or trimming what deploys before pushing.

## 2025-14 checkbox audit (Aug 2026)
`docs/xmarks.py <page> [doc]` pixel-measures each Block B/C/D cell from the 300-dpi hires PNG
and reports which column holds an X, independent of any transcription. Cross-checking it
against the first 113 independently transcribed 2025-14 pages compared 2,592 Schedule A value
cells and produced exactly one disagreement (p.57 ELI LILLY & CO CMN), which inspection of the
scan confirmed was a transcription error, since corrected. Re-running the comparison after the
fix yields zero mismatches.

Caveats: its `rows[]` includes group-header rows, so it aligns with the FULL page-JSON rows
list, not just the asset rows; its column *labels* are the Schedule A bucket names, so on
Schedule B pages use it for column position and map to the printed Schedule B buckets. It
expects 38 detected vlines and warns otherwise.

`docs/bmarks.py` is the Schedule B counterpart (different column map, 20 vlines, and a
lighter lowercase "x"). Its `rows[]` additionally includes the leading "SP DC JT | ASSET"
header strip, so drop the first row before aligning to the page JSON.

Its ink threshold is 0.065, chosen from the data rather than by eye: over 51,480 measured
2025-14 Schedule B cells, cells the transcription marks bottom out at 0.071 and unmarked
cells top out at 0.058. An earlier 0.05 sat inside the noise and produced seven false
positives from scanner specks (0.051-0.058), each of which had to be resolved by hand.
If a future filing scans darker or lighter, re-measure that separation before trusting it.

Some sheets lose the faint owner/asset divider and detect only 19 vlines; bmarks shifts its
column map rather than skipping those pages.

`docs/xmarks_audit.py [doc]` runs both across a whole document and prints every mismatch.
On 2025-14 it compares 22k+ bucket cells (Schedule A value / income type / income amount,
Schedule B tx type / amount / cap gain) and, after eleven corrections, reports zero.

The cap-gain checkbox needed its own threshold (`CG_THRESHOLD`, 0.03). It is an isolated box
rather than one of a row of buckets, so it collects no neighbouring grid ink: unmarked cells
measure 0.000 flat and marked ones start at 0.061, well under the 0.065 used for the bucket
columns. Adding it to the audit immediately surfaced six errors that visual review had passed
- flags set on rows with no X, and one X missed entirely - because nothing had been checking
that column.

Known limits, learned the hard way:
- xmarks' `E_ink` is NOT usable for Block E: blank cells measure 0.06-0.08 from grid-line
  ink, indistinguishable from a single "P". Read Block E visually.
- The last Block C column is the "Other Type of Income" write-in, so text there (e.g. "PTN")
  reads as ink rather than an X; it belongs in `other_income_spec`. The audit ignores it.
- Section-boundary pages with blank spacer rows (e.g. 2025-14 p.131) legitimately have fewer
  JSON rows than detected grid rows; the audit skips and reports them rather than failing.

Recommended before shipping any future Form A year: run `docs/xmarks_audit.py <doc>` and
resolve every mismatch against the scan before compiling.

## 2025 annual (2025-14) — ingestion record, Aug 2026
353 pages, Clerk ID 9116272, transcribed page-by-page and then cross-checked with
`docs/xmarks_audit.py`: 350 grid pages / 22,758 bucket cells, zero remaining mismatches.
The audit found eleven real errors that page-level review had passed — one Schedule A value,
three income amounts, one income-type set, and six cap-gain flags — each confirmed against the
scan before correcting. Page 131 is skipped by the audit (blank spacer rows between sections
are legitimately omitted from the JSON) and was checked by hand: 8/8 value cells agree.

Reconciliation against the independently transcribed 2025 PTRs is corroborating, not a gate.
The annual's Schedule B carries 5,402 transactions against the PTRs' 4,802; 93.5% of PTR
transaction dates appear in Schedule B and 71.2% of PTR rows match a Schedule B row on
name+date. The residual is dominated by the two filings printing the same security
differently (`ALPHABET INC.` vs `ALPHABET INC`, `5%` vs `5 /`) and by genuine differences in
what each document reports, not by transcription drift.

WATCH THIS: the filer's notes page (p.353) states that, per the 2026 Instruction Guide, the
value bracket selected represents the *percentage interest* in the asset. Reported holdings
therefore fall from $98.7M-$314.9M (2024) to $69.2M-$166.7M (2025) without implying any
change in wealth. That is carried as `meta.caveat` in compile17.py and rendered by
build_pages.py in the answer panel, the FAQ, and a footnote under the cross-year table.
Any future year that changes reporting basis should set `meta.caveat` the same way.
Note also that `meta.why_html` is written by the compilers but rendered nowhere.

## Maturity-date-in-date-column audit (Aug 2026)
A recurring OCR failure mode on dense PTR transaction grids: the transcriber misread the
`date`/`notification_date` column and substituted an unrelated date printed elsewhere on the
row — most often a bond's coupon/maturity date embedded in the asset name (e.g. "CLARK CNTY
NEV ... REV 5% 07/01/26" transcribed with date `07/01/2026`), but also plain digit slips
(`12/06/22`→`01/04/23`, i.e. picked up the neighboring notification-date column) and one-row
cascades where a displaced date bled into the next row. Root-caused via
`git log`/systematic-debugging by rendering each flagged page upright (OSD-corrected, content-
cropped, upscaled) and reading the scan directly — Tesseract's own raw text was frequently
*also* wrong on these pages (e.g. misreading `09/24/25` as `03/24/25`), so the scan image, not
`tess/*.txt`, was the adjudication source of truth.
- Audited & fixed 40 pages / 179 rows across docs/2022-13, 2025-4, 2025-11, 2025-12, 2026-2 —
  see each row's added `uncertainties` entry for the specific misread→correction.
- Two pages (2018-16 p4, 2021-13 pp157/160/163) were investigated and left **unchanged**: the
  dates there are genuinely printed on the form (verified against the scan), just outside the
  filing doc's nominal year — correct per the verbatim-transcription rule, not an OCR error.
- **Guard added:** `scripts/build_open_data.py`'s `parse_date()` now logs every time it has to
  roll a parsed year back a century (i.e. the reported date parsed to more than a year in the
  future), and `--check` fails the build (`no_far_future_transaction_dates`) if that ever
  fires — so a future instance of this bug is caught by `make open-data` instead of silently
  auto-corrected into a still-wrong record. This guard itself caught one more instance
  (2025-4 p49 row 12, `notification_date` misread `2028`→`2025`) beyond the original manual
  sweep.

## `date` > `notification_date` audit (fixed/triaged Aug 2026)
Follow-up to the maturity-date audit above: ~438 rows across 63 pages (post-fix) had `date`
reported *after* `notification_date` — chronologically impossible, since a transaction can't
be reported before it happens. Root-caused per-document by rendering each flagged page upright
and reading the scan (same method as above). Two distinct causes turned out to be mixed
together under one symptom:

**A. Simple per-row misreads (fixed, ~76 rows across 2022-5, 2022-9, 2025-4, 2025-11, 2026-1,
2026-2, 2026-3, and isolated 2019/2020/2022/2023 pages).** Digit slips, a date/notification
column swap, or (again) a bond maturity date landing in the date column. Verified the row's
`asset_name` matches the scan at that position before correcting `date`/`notification_date`;
each fix has a matching `uncertainties` entry. A further 16 rows across `docs/2026-2/page-038`,
`docs/2026-3/page-025`, `page-033`, `page-034`, and `docs/2026-2/page-031` were fixed jointly
with the row-merge/omission repairs below (same page, same session, two defects layered on the
same rows) — the date corrections were re-applied on top of the corrected row structure once
both were done, so no row lost either fix.

**B. Row-content misattribution — a distinct, more serious defect (identified and fixed).**
On several pages, whole rows don't match the scan at all: the transcribed `asset_name` at a
given row position is a *different security* than what's actually printed there (not just a
wrong date). Confirmed directly against page scans, e.g.:
- `docs/2021-8/text/page-013.json` row 0 says "ACTIVISION BLIZZARD, INC CMN" — the actual
  scan's row 0 is "CHEVRON CORPORATION CMN". All 65 tx rows on that page are affected.
- `docs/2021-10/text/page-005.json` row 0 says "CATERPILLAR INC (DELAWARE) CMN" — the scan's
  row 0 is "NORFOLK SOUTHERN CORP CMN".
- `docs/2022-9/text/page-014.json` rows 0–13 correctly match the scan; row 14 onward doesn't
  (JSON "WALMART INC CMN" vs. scan "CARTER'S, INC. CMN", etc.) — a clean discontinuity
  partway down the page, the same signature seen on `page-005.json`, `page-010.json`,
  `page-013.json`, `page-018.json`, `page-019.json` in this same document.
- A cross-document case: `docs/2023-3/text/page-011.json` row 20 ("TORONTO DOMINION BANK
  LINKED TO S&P 500 IND") doesn't exist anywhere in `docs/2023-3`'s scans at all (confirmed
  via full-text search of the raw tesseract output) — an identical-looking transaction exists
  instead in `docs/2023-4/text/page-003.json` row 1, with a different `notification_date`.

This is why the misattributed rows correlate so strongly with the date>notification
symptom: whichever OCR/transcription failure produced the wrong content also produced an
internally-inconsistent date pair, since the "date" attached to the wrong row is really some
other row's date.

**Dedicated re-transcription completed** (the row content was re-verified against the scans
before any date correction):
- `docs/2021-8` — pages 005 and 022 have now been re-verified against their
  scans and rebuilt from matching annual Schedule B row runs. Their printed
  account separators and distinct notification-date runs are retained. Pages
  012, 013, 016, and 018 were also re-verified in the same manner.
- `docs/2021-10` — pages 003, 004, 005, and 008 have now been re-verified
  against their scans and rebuilt from matching annual Schedule B row runs.
  The 77 formerly misattributed rows are resolved and their date/notification
  anomalies are gone. The few scan-printed 11/08/2021 and 11/02/2021
  notification dates on page 004 remain verbatim.
- `docs/2022-9` — pages 005, 010, 013, 014, 018, and 019 were re-verified
  against their scans and rebuilt from matching annual Schedule B runs after independently
  confirming their printed dates; page 004 row 17 and page 002's single row were already
  resolved.

**Left unfixed, but for a different reason (verbatim, not a bug):** on `docs/2022-5` pages
017–018, most rows genuinely show a printed "Date of Transaction" one day *after* "Date
Notified" (e.g. 6-Apr-22 date vs. 4-Apr-22 notified) — confirmed against the scan, correct
as transcribed. This looks like a real filer/preparer error on the original government
filing, not an OCR error, so per the verbatim-transcription rule it was left as printed
(only the ~9 rows that were genuinely misread were corrected).

The final corpus-wide chronology sweep also confirms seven other verbatim exceptions: the
single rows on `2019-12/page-008`, `2019-13/page-008`, `2020-2/page-011`,
`2021-11/page-008`, and `2022-9/page-002`, plus both rows on `2020-12/page-008`.
Each was read directly from its page scan; `2022-9/page-002` was additionally cross-checked
against the matching annual Schedule B entry. They remain as filed, rather than being
silently normalized.

**Also surfaced during this audit:** `docs/2025-4` pages
006/010/011/012/014/017/024/043/045/046/048 had missing, merged, or duplicated rows. They
have now been re-transcribed against the filed page scans: omitted assets were restored,
merged names were split, and the MURA account headers on page 043 were put back at their
printed position. The equivalent issues on `docs/2026-2/page-031` and
`docs/2026-3/page-025/033/034` were fixed in the same audit round.

The stray Toronto Dominion Bank linked-note row formerly in `docs/2023-3/page-011` has been
removed: it is not printed in that document and belongs to `docs/2023-4/page-003`, whose filed
notification date is 05/03/2023 rather than 04/03/2023.

**`docs/2026-5` transaction-table re-verification (Aug 2026):** pages 002–041 were read
directly from the filed scans after catalog users surfaced leading checkbox/owner marks and
adjacent-row text in asset names. The entire transaction table was rebuilt from the printed
row runs: OCR debris and merged labels were removed, copied notification dates were replaced
with the printed transaction dates, and 17 omitted transactions were restored. Each rebuilt
page records scan verification and high page confidence; the resulting document contains
615 transactions, and the catalog text-quality audit reports no high-signal artifact finding
for `2026-5`.

**`docs/2023-10` transaction-table re-verification (Aug 2026):** pages 002–040 were read
against the filed PTR scans and aligned to the matching 2023 annual Schedule B rows. The PTR
scans remained authoritative for row presence, account separators, notification dates, and
the several PTR-only transactions absent from the annual form. The rebuild removed OCR grid
debris and split-row fragments, corrected transaction directions and amount bands, restored
four omitted transactions, and restored the printed account separators. The 39 transaction
pages now contain 657 transactions, have high page confidence, produce no text-quality
finding for `2023-10`, and produce no date-after-notification anomaly.

**`docs/2025-4` follow-up transaction-table re-verification (Aug 2026):** pages 003–005,
007–009, 012–042, 044, 046–047, and 049–051 were re-read against the filed scans; this
extends the earlier scan repairs on pages 006, 010–012, 014, 017, 024, 043, 045–046, and
048 noted above. Matching 2025 annual Schedule B rows were used only after the scan's row
count, endpoints, dates, and account boundaries agreed. The rebuild restored omitted rows,
removed duplicated and merged OCR fragments, corrected shifted purchase/sale and amount
columns, and put account separators back at their printed positions. The document now
contains 840 transactions and produces no high-signal text-quality finding for `2025-4`.

**`docs/2022-4` transaction-table re-verification (Aug 2026):** pages 003–010 were read
against the filed PTR scans after the existing transcription was found to contain dozens of
OCR pseudo-rows, merged labels, and shifted or unknown transaction columns. The first 498
transactions were aligned to matching March rows in the 2022 annual Schedule B only after
the scan's page endpoints and complete row runs agreed; the scan remained authoritative for
page breaks, row order, account separators, owners, and the printed 04/04/2022 notification
date. Page 010's three repeated 12-row blocks were independently matched and reordered to
their printed sequence. The rebuild replaces pages 003–010 with 534 scan-verified
transactions, preserves the five already verified page-002 transactions, and leaves the
document with 539 transactions and no text-quality finding for `2022-4`.

**Remaining transaction-text audit rebuilds (Aug 2026):** the corpus-wide high-signal
transaction-name audit exposed several filings whose defects extended well beyond the rows
that triggered a warning. Each filing below was therefore checked page-by-page against its
PTR scan, with matching annual Schedule B rows used as clean structured transcriptions only
after the scan's sequence and endpoints agreed:

- `docs/2022-5` pages 003–016 were rebuilt as 1,002 scan-matched transactions. The old
  transcription had omitted 648 printed rows; the completed document contains 1,081
  transactions. The 72 genuine date-after-notification rows printed on pages 017–018 remain
  verbatim.
- `docs/2022-6` pages 002–067 were rebuilt as 1,166 transactions with eight trust separators,
  restoring 130 net rows and resolving 1,036 unknown dates, 52 unknown owners, and 160 unknown
  amounts. The PTR scan controls the reordered Citigroup/XSP rows, six May rows represented
  differently in the annual filing, the repeated Fidelity row, and the ARECO dates and marks.
- `docs/2022-3` pages 002–012 were rebuilt as 666 transactions with fourteen printed account
  headings. The old transcription omitted 240 transactions and contained three duplicated OCR
  rows. Four Goldman Sachs notes on page 011 and the page-012 transaction dates were read from
  the PTR scan where the annual sequence conflicted or was absent.
- `docs/2022-1` pages 003–009 were rebuilt from lossless PDF images as part of a 495-transaction,
  nine-heading row map, and page 010's six omitted partial-transaction marks were restored.
  Six false or duplicated transactions were removed and five missing account separators were
  restored. Page 009 retains one explicitly documented unreadable municipal-bond suffix rather
  than inferring it from a non-matching annual row.
- `docs/2021-9` pages 002–009 were rebuilt as 416 transactions with six account headings.
  Five omitted transactions were restored, fifteen wrong-identity substitutions were corrected,
  341 placeholder dates were replaced with the legible printed dates, and seventeen previously
  populated dates were corrected. A second high-resolution pass resolved the remaining
  PartnerRe/Vodafone and municipal-bond suffixes; no row-level source uncertainty remains.
- `docs/2022-10` pages 003–032 were rebuilt as 664 transactions, leaving 665 in the document
  with page 002. Six printed account separators were restored and five annual-only rows absent
  from the PTR were excluded. Page 002's blacked-out transaction and notification dates remain
  `[ILLEGIBLE]` rather than guessed. Four unusual purchase rows (Fifth Third, JPMorgan, Corteva,
  and Regions) visibly have the capital-gain-over-$200 box checked on the filed scan and remain
  verbatim.
- `docs/2023-5` was rebuilt as 664 transactions. Nine omitted rows and seven substituted rows
  were repaired. Two asset cells that genuinely print only `COMMON STOCK` remain verbatim and
  are recorded as reviewed source exceptions by the text-quality audit.
- `docs/2025-11` pages 002–015 were rebuilt as 358 transactions, restoring eight printed rows
  and the filed trust separators. Shifted dates, transaction directions, amount bands, owners,
  and cap-gain/partial-transaction marks were replaced with the scan-verified values; later
  annual-only September activity was not imported into the PTR.
- `docs/2025-12` pages 002–020 were rebuilt as 295 transactions, restoring five omitted rows
  and fourteen missing account headings. Of the 290 retained rows, 273 required at least one
  scan-backed field correction. Page 020's separate amendment sequence and 09/04/2025
  notification date are preserved independently from the main September row run. The American
  Express row on page 003 has a genuinely blank owner cell on the PTR and remains null with an
  explicit provenance note.

The text-quality audit now separates scan-verified source anomalies from actionable
transcription findings. Its patterns were also narrowed where scan review showed legitimate
filed text: municipal issuer abbreviations containing owner-like codes, `COMMON STOCK CMN`,
mixed-case brand names, structured-note `Ref=` identifiers, and the filed `[POLAND] X Y`
issuer name are no longer treated as OCR artifacts.

**PTR checkbox-schema completeness audit (Aug 2026):** the cap-gain and partial-transaction
columns first appear in this collection on `docs/2020-5`; 2017–2019 PTRs and `docs/2020-1`
through `docs/2020-4` use the older form and are intentionally exempt. A scan-backed pass over
the 2020 new-form cohort (`2020-5`, `2020-6`, `2020-8`, `2020-9`, `2020-11`, `2020-12`, and
`2020-13`) made both booleans explicit on all 1,785 transactions, adding 747 missing cap-gain
fields and 1,138 canonical partial-sale fields without changing non-boolean data. It preserves
the filed Purchase+Partial XSP row in `2020-6`, five purchase+capital-gain PUT rows in `2020-8`,
the genuinely blank SNAP amount in `2020-11`, and the two filed date-after-notification rows in
`2020-12`. `scripts/build_open_data.py` now fails when a transaction on the newer form lacks
either explicit boolean or retains the obsolete `partial`/`partial_transaction` key.

The same checkbox pass completed 1,314 missing `partial_sale` fields and 180 missing
`cap_gain_over_200` fields across `2021-4`, `2021-5`, `2021-7`, `2021-8`, `2021-11`,
`2022-4`, and `2022-9`. Existing explicit booleans were preserved; missing values came from
direct scan maps (`2021-7` and the two `2021-8/page-002` rows) or already scan-backed
`Partial Sale`/`partial_transaction` evidence. The genuine chronology exceptions on
`2021-11/page-008` and `2022-9/page-002` remain verbatim.

Finally, `2023-10` and `2025-4` received explicit `partial_sale` values on their 646 and 291
previously incomplete rows. The pass visually confirmed the 29 partial marks in `2023-10` and
preserved the earlier full-table rebuild. In `2025-4`, scan review rejected six legacy
`Partial Sale` labels whose partial column is actually blank, restored the marked Baxter row,
and preserved the MKS sale/cap-gain row as non-partial. Both documents now use canonical
`tx_type: Sale` plus the separate boolean for partial transactions.

A separate core-field census checked every remaining null/`[UNKNOWN]`/`[ILLEGIBLE]` value on
PTR transaction rows against the filed form. The residuals are source-authentic: ten
`2018-13/page-004` rows omit type and amount; `2020-11/page-003` SNAP omits amount;
`2022-10/page-002` has blacked-out date marks; `2023-1/page-017` Linde and three
`2025-1/page-032` rows omit amount; and `2025-12/page-003` American Express omits owner. These
remain explicit limitations rather than inferred values. The same census repaired the legible
Stryker date on `2023-6/page-028` and Tiger Global date/amount on `2023-9/page-014`.
