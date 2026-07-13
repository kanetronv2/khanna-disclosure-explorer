#!/usr/bin/env python3
"""Build small overview summaries and lazy, cacheable site data chunks."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "site-data"
YEARS = [str(year) for year in range(2016, 2027)]


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


def file_hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()[:12]


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
        if re.search(r"annual financial disclosure|financial disclosure report|financial disclosure statement|form a", label, re.I):
            return {"doc": doc, "label": label, **page_progress(members)}
    return None


def build_year(year):
    data = load_year(year)
    assets = data.get("assets") or []
    transactions = data.get("transactions") or []
    pages = data.get("pages") or []
    year_dir = OUT / year
    page_dir = year_dir / "pages"
    page_dir.mkdir(parents=True, exist_ok=True)

    assets_path = write_hashed(year_dir, "assets", assets)
    transactions_path = write_hashed(year_dir, "transactions", transactions)

    page_index = []
    for page in pages:
        detail = dict(page)
        image_path = ROOT / page["image"]
        if image_path.is_file():
            detail["image"] = f"{page['image']}?v={file_hash(image_path)}"
        payload = encoded(detail)
        detail_path = page_dir / f"{int(page['pdf_page']):04d}.{hash_bytes(payload)}.json"
        detail_path.write_bytes(payload + b"\n")
        page_index.append({
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
    summary = {
        "meta": data.get("meta") or {},
        "source_pdf": data.get("source_pdf"),
        "filer": data.get("filer"),
        "filing": data.get("filing"),
        "counts": {"assets": len(assets), "transactions": len(transactions), "pages": len(pages)},
        "holdings": sum_range(assets, "vlo", "vhi"),
        "income": sum_range(assets, "ilo", "ihi"),
        "transaction_total": sum_range(transactions, "lo", "hi"),
        "all_docs": page_progress(pages),
        "annual_doc": annual_progress(pages),
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


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    summaries = {year: build_year(year) for year in YEARS}
    payload = "window.FD_SUMMARIES = " + json.dumps(
        summaries, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ) + ";\n"
    (OUT / "summaries.js").write_text(payload, encoding="utf-8")
    print(f"site data: {len(summaries)} years, {sum(s['counts']['pages'] for s in summaries.values())} page views")


if __name__ == "__main__":
    main()
