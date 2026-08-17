# OCR extraction spec — Khanna 2016/2017 filings (Form B, Form A, PTRs)

15 scanned documents under `docs/` in /Users/multivac/Code/khanna:
- `2016-1` — CY-2016 Financial Disclosure STATEMENT (Form B, new member), 116 pages
- `2017-1` — CY-2017 Financial Disclosure REPORT (Form A annual), 149 pages
- `2017-2` … `2017-14` — Periodic Transaction Reports (PTRs) filed during 2017, 3–11 pages each

All are rotated-then-corrected image scans. Per document `<doc>`, per page NNN (001-based per document):
- `docs/<doc>/pages/page-NNN.jpg` — full page, readable orientation (layout + row inventory)
- `docs/<doc>/quads/page-NNN-{TL,TR,BL,BR}.jpg` — hi-res overlapping crops (fine print, exact X columns; ~8% overlap)
- `docs/<doc>/tess/page-NNN.txt` — tesseract cross-check (names/dates only)

Output: `docs/<doc>/text/page-NNN.json` — SAME JSON schema as the 2024 spec (`ocr/SPEC.md`), with these notes:

## Page types
Everything from ocr/SPEC.md plus:
- `cover` — Form B/Form A cover: transcribe all fields & yes/no answers into `free_text` (markdown).
- `ptr_cover` — PTR first page (NAME, filing status boxes, example row): `free_text`, plus any real data rows if present.
- `ptr` — PTR continuation/attachment pages listing transactions.

## Schedule A grids (both 2016-1 and 2017-1)
Same method as 2024: Block A owner+asset name (left crops), Blocks B/C/D/E checkbox columns (right crops), row-position alignment. IMPORTANT: these older forms may use slightly different bucket labels than 2024 — transcribe the EXACT printed column-header text for whichever column holds the X (e.g. if the form prints "$1,000,001-$5,000,000" or "Over $50,000,000", copy that verbatim). Same for income-type columns (older forms may list e.g. EXCEPTED/BLIND TRUST). Do not force 2024 wording.

## PTR transaction rows
```json
{"kind": "tx", "owner": "SP", "asset_name": "MEGA CORP COMMON STOCK",
 "tx_type": "Purchase" | "Sale" | "Exchange",
 "date": "02/05/2015", "notification_date": "03/07/2015",
 "amount": "$15,001-$50,000"}
```
- `owner` from the SP/DC/JT column (may be blank).
- Dates are printed MMDDYY or MM/DD/YY — normalize to MM/DD/YYYY (e.g. 020515 → 02/05/2015).
- `amount` = exact printed bucket text of the checked column (A–K).
- Some PTR pages are typed attachment tables ("Please see the attached") rather than the grid — transcribe those tables row by row with the same fields.
- Ignore the greyed "Example: Mega Corp" row.

## Schedule B (2017-1 annual) — same as 2024 spec (tx rows with cap_gain_over_200, date, amount).

## Cover/label discipline
Record the printed page label you actually see in `printed_label` (these documents use styles like "1/116", "Page 1 of 5", or handwritten numbers; copy as printed, null if absent).

All other rules from ocr/SPEC.md apply verbatim: transcribe exactly, never skip a row, flag anything uncertain in `uncertainties`, one valid JSON file per page written IMMEDIATELY after each page.

## 2018 documents (added later)
Same conventions and schema as above, `docs/<doc>/...`. The set:
- `2018-4` — 2018 Annual Financial Disclosure REPORT (Form A), 309 pages (holdings + Schedule B; expect the same typed-spreadsheet attachments and transposed grids as 2017-1).
- `2018-2, 2018-5..2018-16` — Periodic Transaction Reports (PTRs).
- `2018-17` — PTR AMENDMENT (2p; "Amendment" box checked, amends the 11/09/2018 report). Page 1 is the cover, page 2 the attached tx table.
- `2018-3` — Gift Disclosure Waiver Request (1p): transcribe the whole form into `free_text`, page_type `letter`, rows [].
- `2018-18` — Financial Disclosure Extension Request (1p): same treatment, page_type `letter`, rows [].

## 2019 documents
Same conventions/schema, `docs/<doc>/...`. The set:
- `2019-2` — 2019 Annual Financial Disclosure REPORT (Form A), 210 pages (holdings + Schedule B; same typed-spreadsheet/transposed layouts).
- `2019-1, 2019-3, 2019-5..2019-14` — Periodic Transaction Reports (PTRs).
- `2019-4` — PTR AMENDMENT (2p; amends the 01/10/2019 report).
- `2019-15` — Financial Disclosure Extension Request (1p, text-native): page_type `letter`, rows [], full form into `free_text`.

## 2020 documents
Same conventions/schema, `docs/<doc>/...`. The set:
- `2020-14` — 2020 Annual Financial Disclosure REPORT (Form A), 326 pages (holdings + Schedule B; same typed-spreadsheet/transposed layouts).
- `2020-1..2020-13, 2020-15` — Periodic Transaction Reports (PTRs); some may be amendments (check the cover's "Amendment" box).
- `2020-16` — Financial Disclosure Extension Request (1p, text-native): page_type `letter`, rows [], full form into `free_text`.

## 2021 & 2022 documents
Same conventions/schema, `docs/<doc>/...`.
- 2021: annual = `2021-13` (303p, Form A); `2021-12` (1p) = Extension Request (letter); rest = PTRs (`2021-8` is 23p).
- 2022: annual = `2022-15` (367p, Form A); `2022-14` (1p) = Extension Request (letter); rest = PTRs (several long: 2022-6 67p, 2022-7 34p, 2022-10 32p — heavy trading year). Check each PTR cover for the "Amendment" box.

## 2025 documents — annual (added Aug 2026)
The twelve 2025 PTRs (`2025-1..2025-12`) and the Extension Request (`2025-13`) were transcribed
earlier under the generic PTR rules above. The annual arrived later:
- `2025-14` — 2025 Annual Financial Disclosure REPORT (Form A), 353 pages, Clerk ID 9116272,
  hand-delivered, received 2026-08-10 (filed under the 90-day extension granted 02/21/2026).
  Printed labels run "Page N of 353" and match the PDF 1:1. Scans are ALREADY UPRIGHT —
  prep2025b.sh applies no rotation (do not run prep2025.sh on this doc).

Layout is the same OmniPage checkbox-grid scan as the 2024 annual; follow `ocr/SPEC.md`
verbatim, with 2024 conventions:
- `schedule_a` rows: `owner, asset_name, value, income_types, other_income_spec,
  amount_of_income, transaction` — exact printed bucket text for whichever column holds the X.
  Add optional `"eif": true` when the EIF (excepted investment fund) column is marked
  (2024 convention); omit the key otherwise.
  Block E `transaction` uses the COMMA form when several codes are printed together —
  `"P,S"`, `"P,S,S(part)"` — matching the rest of the corpus (5,134 comma vs 3 space).
  The form prints them space-separated; normalize to commas.
- `schedule_b` rows: `tx_type` ("Purchase" / "Sale" / "Partial Sale" / "Exchange"),
  `cap_gain_over_200`, `date`, `notification_date` (usually blank on the annual's Schedule B),
  `amount` — dates normalized to MM/DD/YYYY.
- Page 1 cover → `page_type: "cover"`, everything into `free_text`.
- FILER NOTES (p. 353) → `page_type: "other"`, transcribe verbatim into `free_text`.
  NOTE: the filer states that "Pursuant to the 2026 Instruction Guide … the value bracket that
  represents the percentage interest in the asset is selected" — i.e. value brackets may encode
  a percentage interest rather than the full asset value. Transcribe the brackets exactly as
  printed; this caveat lives in the free_text, not in the row data.
