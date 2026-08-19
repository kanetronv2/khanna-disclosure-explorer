#!/usr/bin/env python3
"""Build small overview summaries and lazy, cacheable site data chunks."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

import evidence_assets


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "site-data"
YEARS = [str(year) for year in range(2016, 2027)]
ORIGIN = "https://www.rokhanna.money"


def load_year(year):
    text = (ROOT / f"data-{year}.js").read_text(encoding="utf-8")
    prefix = "window.FD_DATA = "
    if not text.startswith(prefix):
        raise ValueError(f"data-{year}.js does not contain FD_DATA")
    return json.loads(text[len(prefix):].rstrip().rstrip(";"))


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def hash_bytes(value):
    return hashlib.sha256(value).hexdigest()[:12]


def write_hashed(directory, stem, value):
    payload = encoded(value)
    path = directory / f"{stem}.{hash_bytes(payload)}.json"
    path.write_bytes(payload + b"\n")
    return str(path.relative_to(ROOT))


def sum_range(rows, low, high):
    lo = hi = open_count = 0
    any_value = False
    for row in rows:
        value = row.get(low)
        if value is None:
            continue
        any_value = True
        lo += value
        maximum = row.get(high)
        if maximum is None:
            open_count += 1
            hi += value
        else:
            hi += maximum
    return {"lo": lo, "hiF": hi, "open": open_count, "any": any_value}


def transaction_date_coverage(rows):
    """Count transactions with a valid reported date and the calendar months they occupy."""
    dated = 0
    months = set()
    days = set()
    for row in rows:
        match = re.match(r"^\s*(\d{1,2})/(\d{1,2})/(\d{2}|\d{4})\s*$", str(row.get("date") or ""))
        if not match:
            continue
        month, day, year = map(int, match.groups())
        year += 2000 if year < 70 else 1900
        try:
            date(year, month, day)
        except ValueError:
            continue
        dated += 1
        months.add((year, month))
        days.add((year, month, day))
    return {"dated_transactions": dated, "active_transaction_months": len(months),
            "active_trading_days": len(days)}


def grouped(rows, key, low, high, label):
    groups = defaultdict(list)
    for row in rows:
        groups[row.get(key) or label].append(row)
    result = []
    for name, members in groups.items():
        result.append({"name": name, "n": len(members), **sum_range(members, low, high)})
    return sorted(result, key=lambda item: (-item["lo"], item["name"]))


def page_progress(pages):
    total = len(pages)
    done = sum(page.get("page_type") != "pending" for page in pages)
    return {"done": done, "total": total, "pending": total - done}


def annual_progress(pages):
    documents = defaultdict(list)
    for page in pages:
        documents[page.get("doc") or "unknown"].append(page)
    for doc, members in documents.items():
        label = members[0].get("doc_label") or ""
        if re.search(r"annual financial disclosure|financial disclosure report|financial disclosure statement|form [ab]", label, re.I):
            return {"doc": doc, "label": label, **page_progress(members)}
    return None


def document_url(doc, primary_url=None, is_primary=False):
    if is_primary and str(primary_url or "").startswith(("http://", "https://")):
        return primary_url
    if is_primary and primary_url:
        return evidence_assets.public_url(primary_url)
    path = "disclosures.pdf" if doc == "2024-1" else f"docs/src/{doc}.pdf"
    return evidence_assets.public_url(path)


def document_path(doc):
    return "disclosures.pdf" if doc == "2024-1" else f"docs/src/{doc}.pdf"


def document_provenance(doc, primary_url=None, is_primary=False):
    path = document_path(doc)
    local = ROOT / path
    registered = evidence_assets.official_source(doc, primary_url if is_primary else None)
    checksum = evidence_assets.sha256(local) if local.is_file() else None
    return {
        "url": document_url(doc, primary_url, is_primary),
        "mirror_url": evidence_assets.public_url(path),
        "official_url": registered.get("official_url"),
        "filing_id": registered.get("filing_id"),
        "sha256": checksum,
    }


def source_documents(pages, primary_url, annual):
    documents = {}
    for page in pages:
        doc = page.get("doc") or "unknown"
        current = documents.setdefault(doc, {
            "document_id": doc,
            "label": page.get("doc_label") or doc,
            "pages": 0,
        })
        current["pages"] += 1
    for doc, item in documents.items():
        item.update(document_provenance(doc, primary_url, bool(annual and annual.get("doc") == doc)))
    def doc_key(value):
        match = re.match(r"^(\d{4})-(\d+)$", value)
        return (int(match.group(1)), int(match.group(2))) if match else (9999, value)
    return [documents[key] for key in sorted(documents, key=doc_key)]


def evidence_rows(rows, year, singular):
    enriched = []
    for index, source in enumerate(rows, 1):
        row = dict(source)
        row["doc"] = row.get("doc") or f"{year}-1"
        record_id = f"{singular}:{year}:{index:06d}"
        row.update({
            "id": record_id,
            "evidence_path": f"/api/v1/evidence?id={record_id}",
        })
        enriched.append(row)
    return enriched


def build_year(year):
    data = load_year(year)
    assets = data.get("assets") or []
    transactions = data.get("transactions") or []
    pages = data.get("pages") or []
    annual = annual_progress(pages)
    primary_url = data.get("source_pdf")
    assets = evidence_rows(assets, year, "asset")
    transactions = evidence_rows(transactions, year, "transaction")
    year_dir = OUT / year
    page_dir = year_dir / "pages"
    page_dir.mkdir(parents=True, exist_ok=True)

    assets_path = write_hashed(year_dir, "assets", assets)
    transactions_path = write_hashed(year_dir, "transactions", transactions)

    page_index = []
    for page in pages:
        detail = dict(page)
        doc = page.get("doc") or f"{year}-1"
        page_match = re.search(r"page-(\d+)\.jpg$", page.get("image") or "")
        document_page = int(page_match.group(1)) if page_match else int(page["pdf_page"])
        token = evidence_assets.version_token(page["image"])
        detail["image"] = page["image"]
        if token:
            detail["image"] += f"?v={token}"
        payload = encoded(detail)
        detail_path = page_dir / f"{int(page['pdf_page']):04d}.{hash_bytes(payload)}.json"
        detail_path.write_bytes(payload + b"\n")
        provenance = document_provenance(doc, primary_url, bool(annual and annual.get("doc") == doc))
        page_index.append({
            "id": f"page:{doc}:{document_page:04d}",
            "url": f"{ORIGIN}/{year}/#p{page['pdf_page']}",
            "source_document_url": provenance["url"],
            "source_document_mirror_url": provenance["mirror_url"],
            "official_source_url": provenance["official_url"],
            "house_filing_id": provenance["filing_id"],
            "source_document_sha256": provenance["sha256"],
            "pdf_page": page["pdf_page"],
            "printed_label": page.get("printed_label"),
            "section": page.get("section"),
            "page_type": page.get("page_type"),
            "page_confidence": page.get("page_confidence"),
            "doc": page.get("doc"),
            "doc_label": page.get("doc_label"),
            "row_count": sum(row.get("kind") != "group" for row in page.get("rows") or []),
            "uncertainty_count": len(page.get("uncertainties") or []),
            "detail": str(detail_path.relative_to(ROOT)),
        })
    pages_path = write_hashed(year_dir, "pages-index", page_index)

    owners = grouped(assets, "owner", "vlo", "vhi", "UNSPECIFIED")
    classes = grouped(assets, "cls", "vlo", "vhi", "Other")
    groups = grouped(assets, "group", "vlo", "vhi", "(not under a listed trust)")
    transaction_types = grouped(transactions, "tx_type", "lo", "hi", "?")
    confidence = Counter(page.get("page_confidence") or "unknown" for page in pages)
    public_source_pdf = evidence_assets.public_url(primary_url) if primary_url else None
    primary_doc = annual.get("doc") if annual else (pages[0].get("doc") if pages else None)
    primary_source = document_provenance(primary_doc, primary_url, True) if primary_doc else {}
    public_meta = dict(data.get("meta") or {})
    meta_source_pdf = public_meta.get("source_pdf")
    if meta_source_pdf:
        public_meta["source_pdf"] = evidence_assets.public_url(meta_source_pdf)
        if public_meta.get("why_html"):
            public_meta["why_html"] = public_meta["why_html"].replace(
                str(meta_source_pdf), public_meta["source_pdf"]
            )
    summary = {
        "meta": public_meta,
        "evidence_origin": evidence_assets.evidence_origin(),
        "source_pdf": public_source_pdf,
        "official_source_pdf": primary_source.get("official_url"),
        "source_pdf_mirror": primary_source.get("mirror_url"),
        "source_pdf_sha256": primary_source.get("sha256"),
        "house_filing_id": primary_source.get("filing_id"),
        "filer": data.get("filer"),
        "filing": data.get("filing"),
        "counts": {"assets": len(assets), "transactions": len(transactions), "pages": len(pages),
                   **transaction_date_coverage(transactions)},
        "holdings": sum_range(assets, "vlo", "vhi"),
        "income": sum_range(assets, "ilo", "ihi"),
        "transaction_total": sum_range(transactions, "lo", "hi"),
        "all_docs": page_progress(pages),
        "annual_doc": annual,
        "source_documents": source_documents(pages, primary_url, annual),
        "owners": owners,
        "classes": classes,
        "groups": groups,
        "transaction_types": transaction_types,
        "top_holdings": sorted(assets, key=lambda row: -(row.get("vlo") or 0))[:12],
        "confidence": dict(sorted(confidence.items())),
        "uncertainties": sum(len(page.get("uncertainties") or []) for page in pages),
        "verified_pages": sum(bool(page.get("verified")) for page in pages),
        "files": {"assets": assets_path, "transactions": transactions_path, "pages": pages_path},
    }
    return summary


def write_timeline(summaries):
    """Regenerate timeline-data.js from the summaries.

    This file used to be maintained by hand, which let it drift silently out of step with
    the compiled data (2026 sat 11 transactions light until it was regenerated). It is pure
    derived data, so it is now written here.
    """
    def block(rng):
        return f"{{lo:{rng['lo']},hi:{rng['hiF']},open:{rng['open']}}}"

    rows = []
    for year in YEARS:
        s = summaries[year]
        rows.append(
            f'  {{year:"{year}",ptrOnly:{"true" if (s.get("meta") or {}).get("ptr_only") else "false"},'
            f'assets:{s["counts"]["assets"]},transactions:{s["counts"]["transactions"]},'
            f'holdings:{block(s["holdings"])},income:{block(s["income"])},'
            f'transactionValue:{block(s["transaction_total"])}}}')
    (ROOT / "timeline-data.js").write_text(
        "window.FD_TIMELINE = [\n" + ",\n".join(rows) + "\n];\n", encoding="utf-8")


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    summaries = {year: build_year(year) for year in YEARS}
    write_timeline(summaries)
    payload = "window.FD_SUMMARIES = " + json.dumps(
        summaries, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ) + ";\n"
    (OUT / "summaries.js").write_text(payload, encoding="utf-8")
    print(f"site data: {len(summaries)} years, {sum(s['counts']['pages'] for s in summaries.values())} page views")


if __name__ == "__main__":
    main()
