#!/usr/bin/env python3
"""Build and audit the repository's normalized, analysis-ready data release."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "normalized"
YEARS = [str(year) for year in range(2016, 2027)]
SCHEMA_VERSION = "1.0.0"
OWNER_LABELS = {
    "SP": "Spouse",
    "DC": "Dependent child",
    "JT": "Joint",
    "SELF": "Filer",
}
PAGE_TYPE_ALIASES = {
    "extension_request": "letter",
    "filer_notes": "other",
}
PAGE_TYPES = {
    "cover", "ptr_cover", "ptr_transactions", "letter", "schedule_a", "schedule_b",
    "schedule_c", "schedule_d", "schedule_h", "other",
}
PAGE_TYPE_ALIASES["ptr"] = "ptr_transactions"

TEXT_QUALITY_PATTERNS = {
    "embedded_account_header": re.compile(
        r"\b(?:MURA Holdings|Declaration of Trust|Trust FBO|Grandchildren(?:'s)? Education Trust)\b",
        re.I,
    ),
    "ocr_table_debris": re.compile(
        r"={2,}|\b(?:Transact(?:ion)?|Spous(?:e|r)|Depend(?:ent|ant)|Provide full name)\b",
        re.I,
    ),
    "checkbox_artifact": re.compile(r"(?:\s|_)[xX]{1,2}\s*$"),
    # Rotated table scans sometimes pull marks and headings from adjacent columns into
    # the asset-name cell.  These are review signals, not automatic normalizations:
    # every correction must still be read against the filed page image.
    "embedded_grid_debris": re.compile(r"[=—]|(?:^|\s)[xX](?:\s|$|[!.,;])"),
    "mixed_case_ocr_artifact": re.compile(r"(?:^[a-z]|[a-z][A-Z]|[A-Z][a-z][A-Z])"),
    "embedded_owner_code": re.compile(r"^[•\s]*(?:SP|DC|JT)(?=\s|[._])"),
    "repeated_security_marker": re.compile(
        r"(?:\bCMN\b.*\bCMN\b|\bCOMMON STOCK\b.*\bCOMMON STOCK\b)", re.I
    ),
}
TEXT_FRAGMENT_NAMES = {
    "CMN", "ICMN", "PERPETUAL", "STOCK", "COMMON STOCK", "IN CMN", "CMN CLASS A",
}

# Scan-verified text that is incomplete or unusual on the filed form itself.
# These remain preserved verbatim in source JSON, but are reported separately
# from actionable transcription findings.
REVIEWED_TEXT_QUALITY_EXCEPTIONS = {
    ("2023-5", 5, 12, "standalone_fragment"):
        "The PTR scan itself prints only COMMON STOCK in this asset cell.",
    ("2023-5", 19, 20, "standalone_fragment"):
        "The PTR scan itself prints only COMMON STOCK in this asset cell.",
    ("2023-6", 5, 15, "standalone_fragment"):
        "The PTR scan itself prints only COMMON STOCK in this asset cell.",
    ("2023-6", 18, 5, "standalone_fragment"):
        "The PTR scan itself prints only COMMON STOCK in this asset cell.",
    ("2023-6", 23, 1, "standalone_fragment"):
        "The PTR scan itself prints only CMN in this asset cell.",
    ("2023-14", 162, 10, "standalone_fragment"):
        "The annual scan itself prints only COMMON STOCK in this asset cell.",
    ("2023-14", 164, 17, "standalone_fragment"):
        "The annual scan itself prints only COMMON STOCK in this asset cell.",
    ("2023-14", 262, 23, "standalone_fragment"):
        "The annual scan itself prints only COMMON STOCK in this asset cell.",
    ("2023-14", 270, 3, "standalone_fragment"):
        "The annual scan itself prints only COMMON STOCK in this asset cell.",
    ("2025-8", 3, 11, "repeated_security_marker"):
        "The PTR scan prints two securities in one asset cell with one transaction.",
}


def clean(value):
    if not isinstance(value, str):
        return value
    value = re.sub(r"\s+", " ", value).strip()
    return value or None


def clean_multiline(value):
    if not isinstance(value, str):
        return value
    value = "\n".join(line.rstrip() for line in value.strip().splitlines())
    return value or None


def parse_date(value, rollback_log=None):
    """Parse a reported MM/DD/YY(YY) date. If the literal year is implausibly far in the
    future (e.g. a two-digit year misread, or a bond maturity date misread into the
    transaction-date column), roll a two-digit year back a century as a best effort — but
    record the event in `rollback_log` when given, so callers can surface it as a data
    -quality issue instead of letting it pass silently (see docs/VERIFY_NOTES.md)."""
    value = clean(value)
    if not value or value.startswith("["):
        return None
    for fmt in ("%m/%d/%Y", "%m/%d/%y", "%d-%b-%y", "%d-%b-%Y"):
        try:
            parsed = dt.datetime.strptime(value, fmt).date()
            if parsed.year > dt.date.today().year + 1:
                if rollback_log is not None:
                    rollback_log.append((value, parsed.isoformat()))
                parsed = parsed.replace(year=parsed.year - 100)
            return parsed.isoformat()
        except ValueError:
            pass
    return None


def owner(value):
    reported = clean(value)
    reported = reported.upper() if reported else None
    code = reported if reported in OWNER_LABELS else None
    return code, OWNER_LABELS.get(code, "Unknown / not stated"), reported


def bucket_range(value):
    value = clean(value)
    if not value:
        return None, None
    lowered = value.lower()
    if lowered == "none":
        return 0, 0
    numbers = [int(number.replace(",", "")) for number in re.findall(r"[\d,]+", value)]
    numbers = [number for number in numbers if number > 0]
    if not numbers:
        return None, None
    if "over" in lowered or len(numbers) == 1:
        return numbers[0] + (1 if "over" in lowered else 0), None
    return numbers[0], numbers[1]


def page_type(value):
    raw = clean(value) or "other"
    normalized = PAGE_TYPE_ALIASES.get(raw, raw)
    return normalized if normalized in PAGE_TYPES else "other"


def uses_new_ptr_checkbox_schema(document_id):
    """Return whether a PTR uses the form with cap-gain and partial-sale columns."""
    year, sequence = (int(value) for value in document_id.split("-", 1))
    return year > 2020 or (year == 2020 and sequence >= 5)


def read_data(year):
    path = ROOT / f"data-{year}.js"
    text = path.read_text(encoding="utf-8")
    prefix = "window.FD_DATA = "
    if not text.startswith(prefix):
        raise ValueError(f"{path}: expected {prefix!r}")
    return json.loads(text[len(prefix):].rstrip().rstrip(";"))


def local_page_number(image):
    match = re.search(r"page-(\d+)\.jpg$", image or "")
    return int(match.group(1)) if match else None


def source_paths(year, page):
    image = page.get("image")
    n = local_page_number(image)
    if year == "2024":
        return image, f"ocr/text/page-{n:03d}.json", f"ocr/tess/page-{n:03d}.txt"
    doc = page.get("doc")
    return image, f"docs/{doc}/text/page-{n:03d}.json", f"docs/{doc}/tess/page-{n:03d}.txt"


def source_pdf(doc):
    return "disclosures.pdf" if doc == "2024-1" else f"docs/src/{doc}.pdf"


def text_quality_rules(value):
    """Return conservative, review-oriented flags for visibly corrupted row text."""
    name = clean(value) or ""
    rules = [label for label, pattern in TEXT_QUALITY_PATTERNS.items() if pattern.search(name)]
    # Preserve filed brand styling. These mixed-case names are deliberate,
    # rather than lowercase OCR characters embedded in all-caps text.
    valid_mixed_case_prefixes = (
        "Capital call for ",
        "CoStar ",
        "ConocoPhillips ",
        "FedEx ",
        "iShares ",
        "PagerDuty ",
        "PayPal ",
        "RealPage ",
        "ServiceNow ",
        "UnitedHealth ",
    )
    if name.startswith(valid_mixed_case_prefixes) and "mixed_case_ocr_artifact" in rules:
        rules.remove("mixed_case_ocr_artifact")
    # Structured-note identifiers are printed as Ref=<identifier> on the form;
    # that equals sign is content, not a transaction-grid remnant.
    if re.search(r"\bRef=[A-Z0-9]+\b", name) and "embedded_grid_debris" in rules:
        rules.remove("embedded_grid_debris")
    # "X Y" is part of the filed municipal issuer name, not a checkbox mark.
    if "[POLAND] X Y CERT SCH" in name and "embedded_grid_debris" in rules:
        rules.remove("embedded_grid_debris")
    option_contracts = re.findall(r"\b(?:PUT|CALL)(?:\s|/|\()", name, re.I)
    if len(option_contracts) > 1:
        rules.append("multiple_option_contracts")
    if len(name) > 120:
        rules.append("implausibly_long")
    if name.upper().strip("[]()'\" .,:;-_") in TEXT_FRAGMENT_NAMES:
        rules.append("standalone_fragment")
    normalized = re.sub(r"[^A-Z0-9]", "", name.upper())
    if len(normalized) >= 24 and len(normalized) % 2 == 0:
        half = len(normalized) // 2
        if normalized[:half] == normalized[half:]:
            rules.append("duplicated_text")
    return sorted(set(rules))


def page_text_quality_rules(page):
    """Return page-level provenance warnings that apply to every transaction row."""
    uncertainty_text = json.dumps(page.get("uncertainties") or [], ensure_ascii=False)
    rules = []
    if re.search(r"OCR-assisted extraction|local Vision OCR|OCR noise or possible merged text", uncertainty_text, re.I):
        rules.append("ocr_assisted_page")
    if re.search(r"(?:tx_type|checkbox).*(?:not confidently|lower confidence)", uncertainty_text, re.I):
        rules.append("ambiguous_transaction_columns")
    return sorted(set(rules))


def write_jsonl(path, rows):
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
            fh.write("\n")


def csv_value(value):
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return value


def write_csv(path, rows):
    fields = list(rows[0]) if rows else []
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: csv_value(row.get(key)) for key in fields})


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    documents, pages, page_rows, assets, transactions, uncertainties = [], [], [], [], [], []
    document_ids, page_ids = set(), set()
    issues, notes = [], []
    source_jsons, source_tess, source_images, source_pdfs = set(), set(), set(), set()
    raw_page_types, normalized_page_types = Counter(), Counter()
    unparsed_dates = Counter()
    date_century_rollbacks = []
    new_form_checkbox_rows = 0
    new_form_checkbox_issues = []
    page_index = {}
    page_text_rules = {}

    for year in YEARS:
        data = read_data(year)
        year_pages = data.get("pages") or []
        seen_docs = defaultdict(list)
        for source_page in year_pages:
            pdf_page = source_page.get("pdf_page")
            doc = source_page.get("doc") or f"{year}-1"
            seen_docs[doc].append(source_page)
            image, source_json, tess = source_paths(year, source_page)
            source_images.add(image)
            source_jsons.add(source_json)
            source_tess.add(tess)
            ptype_raw = clean(source_page.get("page_type")) or "other"
            ptype = page_type(ptype_raw)
            document_page = local_page_number(image)
            page_id = f"page:{doc}:{document_page:04d}"
            page_index[(year, int(pdf_page))] = (page_id, doc)
            page_text_rules[page_id] = page_text_quality_rules(source_page)
            if page_id not in page_ids:
                page_ids.add(page_id)
                raw_page_types[ptype_raw] += 1
                normalized_page_types[ptype] += 1
                pages.append({
                    "page_id": page_id,
                    "year": int(doc.split("-", 1)[0]),
                    "document_id": doc,
                    "document_page_number": document_page,
                    "printed_label": clean(source_page.get("printed_label")),
                    "section": clean(source_page.get("section")),
                    "page_type": ptype,
                    "page_type_raw": ptype_raw,
                    "confidence": clean(source_page.get("page_confidence")) or "unknown",
                    "free_text": clean_multiline(source_page.get("free_text")),
                    "row_count": len(source_page.get("rows") or []),
                    "uncertainty_count": len(source_page.get("uncertainties") or []),
                    "page_image_path": image,
                    "source_json_path": source_json,
                    "tesseract_text_path": tess,
                })
                for row_number, row in enumerate(source_page.get("rows") or [], 1):
                    if (
                        ptype == "ptr_transactions"
                        and row.get("kind") == "tx"
                        and uses_new_ptr_checkbox_schema(doc)
                    ):
                        new_form_checkbox_rows += 1
                        missing = [
                            field
                            for field in ("cap_gain_over_200", "partial_sale")
                            if not isinstance(row.get(field), bool)
                        ]
                        legacy_fields = [
                            field
                            for field in ("partial", "partial_transaction")
                            if field in row
                        ]
                        if legacy_fields:
                            missing.extend(f"legacy_{field}_key" for field in legacy_fields)
                        if missing:
                            new_form_checkbox_issues.append({
                                "document_id": doc,
                                "document_page_number": document_page,
                                "row_number": row_number,
                                "asset_name": clean(row.get("asset_name")),
                                "fields": missing,
                            })
                    code, label, reported_owner = owner(row.get("owner"))
                    value_min, value_max = bucket_range(row.get("value"))
                    amount_min, amount_max = bucket_range(row.get("amount"))
                    income = row.get("amount_of_income") or row.get("amount_of_income_preceding_year")
                    income_min, income_max = bucket_range(income)
                    reported_date = clean(row.get("date"))
                    notification_date = clean(row.get("notification_date"))
                    page_rows.append({
                        "page_row_id": f"page-row:{doc}:{document_page:04d}:{row_number:04d}",
                        "page_id": page_id,
                        "year": int(doc.split("-", 1)[0]),
                        "document_id": doc,
                        "document_page_number": document_page,
                        "row_number": row_number,
                        "source_json_path": source_json,
                        "row_kind": clean(row.get("kind")) or "unknown",
                        "group_text": clean(row.get("text")),
                        "owner_code": code,
                        "owner_label": label,
                        "owner_reported": reported_owner,
                        "asset_name": clean(row.get("asset_name")),
                        "reported_value": clean(row.get("value")),
                        "value_min_usd": value_min,
                        "value_max_usd": value_max,
                        "income_types": row.get("income_types") or [],
                        "other_income": clean(row.get("other_income_spec")),
                        "reported_income": clean(income),
                        "income_min_usd": income_min,
                        "income_max_usd": income_max,
                        "transaction_type": clean(row.get("tx_type") or row.get("transaction")),
                        "transaction_date_reported": reported_date,
                        "transaction_date_iso": parse_date(reported_date, date_century_rollbacks),
                        "notification_date_reported": notification_date,
                        "notification_date_iso": parse_date(notification_date, date_century_rollbacks),
                        "reported_amount": clean(row.get("amount")),
                        "amount_min_usd": amount_min,
                        "amount_max_usd": amount_max,
                        "capital_gain_over_200_usd": bool(row.get("cap_gain_over_200")),
                        "partial_sale": bool(row.get("partial_sale")),
                        "eif": row.get("eif"),
                    })
                for offset, text in enumerate(source_page.get("uncertainties") or [], 1):
                    uncertainties.append({
                        "uncertainty_id": f"uncertainty:{doc}:{document_page:04d}:{offset:03d}",
                        "page_id": page_id,
                        "year": int(doc.split("-", 1)[0]),
                        "document_id": doc,
                        "document_page_number": document_page,
                        "text": clean(text),
                        "source_json_path": source_json,
                    })

        for doc, doc_pages in sorted(seen_docs.items()):
            pdf = source_pdf(doc)
            source_pdfs.add(pdf)
            if doc in document_ids:
                continue
            document_ids.add(doc)
            documents.append({
                "document_id": doc,
                "year": int(doc.split("-", 1)[0]),
                "title": clean(doc_pages[0].get("doc_label")) or data.get("filing"),
                "filer": clean(data.get("filer")),
                "document_type": "annual_disclosure" if "Annual" in (doc_pages[0].get("doc_label") or "") else (
                    "extension_request" if "Extension" in (doc_pages[0].get("doc_label") or "") else "periodic_transaction_report"
                ),
                "page_count": len(doc_pages),
                "source_pdf_path": pdf,
            })

        for index, item in enumerate(data.get("assets") or [], 1):
            page_no = int(item.get("page"))
            page_id, inferred_doc = page_index[(year, page_no)]
            document_page = int(page_id.rsplit(":", 1)[1])
            code, label, reported_owner = owner(item.get("owner"))
            lo, hi = item.get("vlo"), item.get("vhi")
            ilo, ihi = item.get("ilo"), item.get("ihi")
            assets.append({
                "asset_id": f"asset:{year}:{index:06d}",
                "year": int(year),
                "document_id": item.get("doc") or inferred_doc,
                "page_id": page_id,
                "collection_page_number": page_no,
                "document_page_number": document_page,
                "owner_code": code,
                "owner_label": label,
                "owner_reported": reported_owner,
                "portfolio_group": clean(item.get("group")),
                "asset_name": clean(item.get("name")),
                "asset_class": clean(item.get("cls")),
                "description": clean(item.get("desc")),
                "reported_value": clean(item.get("value")),
                "value_min_usd": lo,
                "value_max_usd": hi,
                "value_has_open_upper_bound": lo is not None and hi is None,
                "income_types": item.get("income_types") or [],
                "other_income": clean(item.get("other_income")),
                "reported_income": clean(item.get("income_amt")),
                "income_min_usd": ilo,
                "income_max_usd": ihi,
                "income_has_open_upper_bound": ilo is not None and ihi is None,
                "transaction_code": clean(item.get("tx")),
                "printed_page_label": clean(item.get("label")),
            })

        for index, item in enumerate(data.get("transactions") or [], 1):
            page_no = int(item.get("page"))
            page_id, inferred_doc = page_index[(year, page_no)]
            document_page = int(page_id.rsplit(":", 1)[1])
            code, label, reported_owner = owner(item.get("owner"))
            reported_date = clean(item.get("date"))
            notification = clean(item.get("notification_date"))
            date_iso = parse_date(reported_date, date_century_rollbacks)
            notification_iso = parse_date(notification, date_century_rollbacks)
            if reported_date and not date_iso:
                unparsed_dates["transaction_date"] += 1
            if notification and not notification_iso:
                unparsed_dates["notification_date"] += 1
            lo, hi = item.get("lo"), item.get("hi")
            transactions.append({
                "transaction_id": f"transaction:{year}:{index:06d}",
                "year": int(year),
                "document_id": item.get("doc") or inferred_doc,
                "page_id": page_id,
                "collection_page_number": page_no,
                "document_page_number": document_page,
                "owner_code": code,
                "owner_label": label,
                "owner_reported": reported_owner,
                "portfolio_group": clean(item.get("group")),
                "asset_name": clean(item.get("name")),
                "asset_class": clean(item.get("cls")),
                "description": clean(item.get("desc")),
                "transaction_type": clean(item.get("tx_type")),
                "capital_gain_over_200_usd": bool(item.get("cap_gain")),
                "transaction_date_reported": reported_date,
                "transaction_date_iso": date_iso,
                "notification_date_reported": notification,
                "notification_date_iso": notification_iso,
                "reported_amount": clean(item.get("amount")),
                "amount_min_usd": lo,
                "amount_max_usd": hi,
                "amount_has_open_upper_bound": lo is not None and hi is None,
                "printed_page_label": clean(item.get("label")),
            })

    tables = {
        "documents": documents,
        "pages": pages,
        "page_rows": page_rows,
        "assets": assets,
        "transactions": transactions,
        "uncertainties": uncertainties,
    }
    for name, rows in tables.items():
        write_jsonl(OUT / f"{name}.jsonl", rows)
        write_csv(OUT / f"{name}.csv", rows)

    for rel in sorted(source_images | source_jsons | source_tess | source_pdfs):
        if not rel or not (ROOT / rel).is_file():
            issues.append({"check": "source_file_exists", "path": rel, "severity": "error"})
    valid_source_json = 0
    for rel in sorted(source_jsons):
        try:
            raw_page = json.loads((ROOT / rel).read_text(encoding="utf-8"))
            if not isinstance(raw_page, dict) or not isinstance(raw_page.get("rows"), list):
                raise ValueError("expected an object with a rows array")
            valid_source_json += 1
        except Exception as error:
            issues.append({"check": "source_json_valid", "path": rel, "error": str(error), "severity": "error"})
    actual_sources = {
        "page_images": {
            str(path.relative_to(ROOT)) for pattern in ("docs/*/pages/page-*.jpg", "ocr/pages/page-*.jpg")
            for path in ROOT.glob(pattern)
        },
        "page_source_json": {
            str(path.relative_to(ROOT)) for pattern in ("docs/*/text/page-*.json", "ocr/text/page-*.json")
            for path in ROOT.glob(pattern)
        },
        "tesseract_text_files": {
            str(path.relative_to(ROOT)) for pattern in ("docs/*/tess/page-*.txt", "ocr/tess/page-*.txt")
            for path in ROOT.glob(pattern)
        },
    }
    for label, actual in actual_sources.items():
        referenced = {"page_images": source_images, "page_source_json": source_jsons,
                      "tesseract_text_files": source_tess}[label]
        if actual != referenced:
            issues.append({"check": "source_inventory_matches", "source_type": label,
                           "unreferenced": sorted(actual - referenced), "missing": sorted(referenced - actual),
                           "severity": "error"})
    for row in assets:
        if not row["asset_name"] or not row["description"]:
            issues.append({"check": "asset_required_text", "record_id": row["asset_id"], "severity": "error"})
        if row["value_min_usd"] is not None and row["value_max_usd"] is not None and row["value_min_usd"] > row["value_max_usd"]:
            issues.append({"check": "asset_value_range", "record_id": row["asset_id"], "severity": "error"})
    for row in transactions:
        if not row["asset_name"] or not row["description"]:
            issues.append({"check": "transaction_required_text", "record_id": row["transaction_id"], "severity": "error"})
        if row["amount_min_usd"] is not None and row["amount_max_usd"] is not None and row["amount_min_usd"] > row["amount_max_usd"]:
            issues.append({"check": "transaction_amount_range", "record_id": row["transaction_id"], "severity": "error"})
    document_id_set = {row["document_id"] for row in documents}
    page_id_set = {row["page_id"] for row in pages}
    for table_name, rows in (("pages", pages), ("page_rows", page_rows), ("assets", assets),
                             ("transactions", transactions), ("uncertainties", uncertainties)):
        for row in rows:
            if row["document_id"] not in document_id_set:
                issues.append({"check": "document_reference", "table": table_name,
                               "record_id": next(value for key, value in row.items() if key.endswith("_id")),
                               "severity": "error"})
            if table_name != "pages" and row["page_id"] not in page_id_set:
                issues.append({"check": "page_reference", "table": table_name,
                               "record_id": next(value for key, value in row.items() if key.endswith("_id")),
                               "severity": "error"})
    pending = sum(row["page_type_raw"] == "pending" for row in pages)
    if pending:
        issues.append({"check": "no_pending_pages", "count": pending, "severity": "error"})
    if unparsed_dates:
        notes.append({"check": "unparsed_dates_preserved", "counts": dict(unparsed_dates), "severity": "info"})
    if date_century_rollbacks:
        # A reported date parsed to a year more than a year in the future (relative to build
        # time) is almost always a transcription error, not a real future-dated transaction —
        # e.g. a bond's maturity date (printed in the asset name) misread into the date column,
        # or an OCR digit swap. We roll the century back as a display fallback, but a rollback
        # firing at all means a source page-JSON transcription needs to be re-checked against
        # its scan and fixed at the source (see docs/VERIFY_NOTES.md), not silently accepted.
        issues.append({"check": "no_far_future_transaction_dates",
                       "count": len(date_century_rollbacks),
                       "examples": date_century_rollbacks[:10], "severity": "error"})
    if new_form_checkbox_issues:
        issues.append({
            "check": "new_form_transaction_checkboxes_complete",
            "count": len(new_form_checkbox_issues),
            "examples": new_form_checkbox_issues[:25],
            "severity": "error",
        })
    notes.append({
        "check": "new_form_transaction_checkbox_schema",
        "transaction_rows": new_form_checkbox_rows,
        "incomplete_rows": len(new_form_checkbox_issues),
        "severity": "info",
    })
    notes.append({"check": "page_type_normalization", "raw": dict(sorted(raw_page_types.items())),
                  "normalized": dict(sorted(normalized_page_types.items())), "severity": "info"})

    text_quality_findings = []
    reviewed_text_quality_exceptions = []
    for row in page_rows:
        if row["row_kind"] != "tx":
            continue
        rules = sorted(set(text_quality_rules(row["asset_name"]) + page_text_rules.get(row["page_id"], [])))
        actionable_rules = []
        for rule in rules:
            exception_key = (
                row["document_id"], row["document_page_number"], row["row_number"], rule
            )
            note = REVIEWED_TEXT_QUALITY_EXCEPTIONS.get(exception_key)
            if note:
                reviewed_text_quality_exceptions.append({
                    "document_id": row["document_id"],
                    "document_page_number": row["document_page_number"],
                    "row_number": row["row_number"],
                    "source_json_path": row["source_json_path"],
                    "asset_name": row["asset_name"],
                    "rule": rule,
                    "note": note,
                })
            else:
                actionable_rules.append(rule)
        rules = actionable_rules
        if rules:
            text_quality_findings.append({
                "finding_id": f"text-quality:{row['document_id']}:{row['document_page_number']:04d}:{row['row_number']:04d}",
                "year": row["year"],
                "document_id": row["document_id"],
                "document_page_number": row["document_page_number"],
                "row_number": row["row_number"],
                "page_id": row["page_id"],
                "source_json_path": row["source_json_path"],
                "asset_name": row["asset_name"],
                "rules": rules,
                "severity": "warning",
            })
    text_quality_counts = Counter(
        rule for finding in text_quality_findings for rule in finding["rules"]
    )
    text_quality_year_counts = Counter(str(finding["year"]) for finding in text_quality_findings)
    text_quality_document_counts = Counter(finding["document_id"] for finding in text_quality_findings)
    text_quality_path = ROOT / "data" / "text-quality-audit.json"
    text_quality_path.write_text(json.dumps({
        "status": "review_required" if text_quality_findings else "pass",
        "scope": "Every transcribed transaction row in every source filing",
        "finding_count": len(text_quality_findings),
        "rule_counts": dict(sorted(text_quality_counts.items())),
        "year_counts": dict(sorted(text_quality_year_counts.items())),
        "document_counts": dict(sorted(text_quality_document_counts.items())),
        "reviewed_exception_count": len(reviewed_text_quality_exceptions),
        "reviewed_exceptions": reviewed_text_quality_exceptions,
        "findings": text_quality_findings,
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    notes.append({
        "check": "transaction_text_quality",
        "finding_count": len(text_quality_findings),
        "rule_counts": dict(sorted(text_quality_counts.items())),
        "report": "data/text-quality-audit.json",
        "severity": "warning" if text_quality_findings else "info",
    })

    report = {
        "schema_version": SCHEMA_VERSION,
        "status": "pass" if not issues else "fail",
        "checks": {
            "years": YEARS,
            "compiled_year_files": len(YEARS),
            "source_pdfs": len(source_pdfs),
            "page_images": len(source_images),
            "page_source_json": len(source_jsons),
            "valid_page_source_json": valid_source_json,
            "tesseract_text_files": len(source_tess),
            "normalized_records": {name: len(rows) for name, rows in tables.items()},
            "confidence_distribution": dict(sorted(Counter(row["confidence"] for row in pages).items())),
            "page_type_distribution": dict(sorted(normalized_page_types.items())),
            "page_row_kind_distribution": dict(sorted(Counter(row["row_kind"] for row in page_rows).items())),
            "owner_code_distribution": dict(sorted(Counter((row["owner_code"] or "not_stated") for row in page_rows).items())),
            "text_quality_findings": len(text_quality_findings),
            "text_quality_rule_distribution": dict(sorted(text_quality_counts.items())),
            "pending_pages": pending,
            "missing_or_invalid_records": len(issues),
        },
        "issues": issues,
        "notes": notes,
    }
    report_path = ROOT / "data" / "quality-report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")

    files = []
    for path in sorted(OUT.glob("*")):
        if path.is_file():
            stem = path.stem
            files.append({
                "path": str(path.relative_to(ROOT)),
                "format": path.suffix.lstrip("."),
                "records": len(tables[stem]),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            })
    files.append({"path": "data/quality-report.json", "format": "json", "records": 1,
                  "bytes": report_path.stat().st_size, "sha256": sha256(report_path)})
    files.append({"path": "data/text-quality-audit.json", "format": "json",
                  "records": len(text_quality_findings), "bytes": text_quality_path.stat().st_size,
                  "sha256": sha256(text_quality_path)})
    manifest = {
        "title": "Ro Khanna financial disclosure open data",
        "schema_version": SCHEMA_VERSION,
        "years": YEARS,
        "license": "CC0-1.0 for original dataset contributions; see DATA_LICENSE.md",
        "files": files,
        "source_coverage": report["checks"],
    }
    (ROOT / "data" / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8"
    )
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="rebuild and fail if the audit finds errors")
    args = parser.parse_args()
    report = build()
    counts = report["checks"]
    print(f"open-data audit: {report['status'].upper()}")
    print(json.dumps(counts, indent=2, sort_keys=True))
    if args.check and report["status"] != "pass":
        for issue in report["issues"][:25]:
            print("ERROR:", json.dumps(issue, sort_keys=True), file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
