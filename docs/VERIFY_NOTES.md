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
