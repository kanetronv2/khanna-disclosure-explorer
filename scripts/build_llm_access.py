#!/usr/bin/env python3
"""Generate compact, stable, provenance-first surfaces for LLMs and data agents.

The browser application deliberately keeps its large per-year arrays in hashed files.  This
builder publishes stable API routes to those files, concise JSON facts, Markdown mirrors, and
the llms.txt discovery documents without duplicating the underlying data in the deployment.
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path

import build_pages as pages


ROOT = Path(__file__).resolve().parents[1]
ORIGIN = pages.ORIGIN
API_ROOT = f"{ORIGIN}/api/v1"
MACHINE = ROOT / "machine" / "v1"
ISSUER_REGISTRY = ROOT / "data" / "issuer-registry.json"


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def absolute(url: str | None) -> str:
    if not url:
        return pages.SOURCE_INDEX
    return url if url.startswith(("http://", "https://")) else f"{ORIGIN}/{url.lstrip('/')}"


def amount_range(block: dict) -> dict:
    return {
        "minimum_usd": block.get("lo", 0),
        "calculated_upper_floor_usd": block.get("hiF", 0),
        "open_ended_entries": block.get("open", 0),
        "display": pages.rng_sum(block),
    }


def value_band(row: dict | None) -> dict | None:
    if not row:
        return None
    return {
        "minimum_usd": row.get("vlo"),
        "maximum_usd": row.get("vhi"),
        "open_ended": row.get("vhi") is None,
        "display": pages.rng_pair(row.get("vlo"), row.get("vhi")),
        "asset_id": row.get("id"),
        "asset_name": row.get("name"),
        "evidence_url": f"{API_ROOT}/evidence?id={row.get('id')}" if row.get("id") else None,
    }


def year_url(ctx: pages.Context, year: str) -> str:
    return ORIGIN + ctx.url_for(year)


def facts_for(ctx: pages.Context, year: str) -> dict:
    summary = ctx.summaries[year]
    counts = summary["counts"]
    active_days = counts.get("active_trading_days", 0)
    dated = counts.get("dated_transactions", 0)
    ptr_only = pages.is_ptr_only(summary)
    documents = summary.get("source_documents") or []
    caveats = [
        "Dollar figures are statutory disclosure ranges, not exact values.",
        "Household scope can include the filer, spouse, and dependent children.",
        "A null maximum with open_ended=true is a disclosed lower threshold, not missing data.",
        "This is an independent transcription; consequential claims should be checked against the linked scans.",
    ]
    if pages.caveat(summary):
        caveats.insert(0, pages.caveat(summary))
    if ptr_only:
        caveats.insert(0, "This year contains periodic transaction reports, not an annual holdings statement.")
    year_caveat = pages.caveat(summary)
    if ptr_only:
        comparability = {
            "cross_year_holdings": {
                "status": "unavailable",
                "reason": "This filing year has no annual holdings statement.",
            }
        }
    elif year_caveat:
        comparability = {
            "cross_year_holdings": {
                "status": "not_directly_comparable",
                "reason": year_caveat,
            }
        }
    else:
        comparability = {
            "cross_year_holdings": {
                "status": "no_year_specific_basis_warning",
                "reason": "No filing-specific value-basis warning is recorded for this year; statutory ranges still do not disclose exact values.",
            }
        }
    return {
        "schema_version": "1.0.0",
        "described_by": f"{API_ROOT}/openapi.json",
        "dataset_version": ctx.modified,
        "id": f"kde:financial-disclosure:{year}",
        "url": year_url(ctx, year),
        "year": int(year),
        "filing_type": "periodic_transaction_reports" if ptr_only else "annual_financial_disclosure",
        "subject": {
            "name": "Ro Khanna",
            "alternate_name": "Rohit Khanna",
            "office": "U.S. Representative",
            "district": "California 17th congressional district",
        },
        "metrics": {
            "reported_holdings": amount_range(summary["holdings"]),
            "reported_unearned_income": amount_range(summary["income"]),
            "reported_transactions": {
                "count": counts["transactions"],
                "dated_count": dated,
                "active_trading_days": active_days,
                "average_per_active_trading_day": round(dated / active_days, 1) if active_days else None,
                "combined_value_range": amount_range(summary["transaction_total"]),
            },
            "largest_disclosed_value_band": value_band((summary.get("top_holdings") or [None])[0]),
            "source_linked_asset_entries": counts["assets"],
            "source_pages": counts["pages"],
        },
        "method": {
            "range_aggregation": "Sum each reported statutory minimum and maximum. For open-ended entries, the displayed upper total remains a floor.",
            "average_trades_per_day": "Dated reported transactions divided by distinct calendar dates containing at least one reported transaction.",
            "transcription": "Full-page and cropped image transcription cross-checked against OCR, with unresolved readings retained as uncertainties.",
        },
        "coverage": {
            "latest_readable_transaction_date": ctx.through(year) or None,
            "annual_filing_pages": (summary.get("annual_doc") or {}).get("total"),
            "loaded_pages": summary["all_docs"]["total"],
            "unresolved_transcription_flags": summary.get("uncertainties", 0),
        },
        "sources": [
            {
                "document_id": item["document_id"],
                "label": item["label"],
                "pages": item["pages"],
                "url": absolute(item["url"]),
            }
            for item in documents
        ],
        "api": {
            "summary": f"{API_ROOT}/years/{year}/summary.json",
            "assets": f"{API_ROOT}/years/{year}/assets.json",
            "transactions": f"{API_ROOT}/years/{year}/transactions.json",
            "pages": f"{API_ROOT}/years/{year}/pages.json",
            "search": f"{API_ROOT}/search?year={year}&kind=transactions&q=example",
            "evidence_lookup": f"{API_ROOT}/evidence?id=transaction:{year}:000001",
        },
        "license": "CC0-1.0 for original dataset contributions; source records retain their own legal status.",
        "caveats": caveats,
        "comparability": comparability,
        "updated": ctx.modified,
    }


def md_escape(value) -> str:
    return str(value if value is not None else "—").replace("|", "\\|").replace("\n", " ")


def markdown_for(ctx: pages.Context, year: str, facts: dict) -> str:
    summary = ctx.summaries[year]
    metrics = facts["metrics"]
    tx = metrics["reported_transactions"]
    holdings = metrics["reported_holdings"]
    largest = metrics["largest_disclosed_value_band"]
    lines = [
        f"# Ro Khanna {year} financial disclosure",
        "",
        f"> Canonical page: {facts['url']}",
        f"> Machine-readable facts: {API_ROOT}/years/{year}/summary.json",
        f"> Dataset version: {facts['dataset_version']}",
        "",
        "This is an independent, source-linked transcription of U.S. House financial-disclosure scans. Values are reported statutory ranges, not exact personal net worth.",
        "",
        "## Key facts",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Filing type | {md_escape(facts['filing_type'])} |",
        f"| Reported household holdings | {md_escape(holdings['display'])} |",
        f"| Open-ended holdings | {holdings['open_ended_entries']:,} |",
        f"| Reported transactions | {tx['count']:,} |",
        f"| Active trading days | {tx['active_trading_days']:,} |",
        f"| Average trades per active day | {md_escape(tx['average_per_active_trading_day'])} |",
        f"| Combined transaction range | {md_escape(tx['combined_value_range']['display'])} |",
        f"| Source-linked asset entries | {metrics['source_linked_asset_entries']:,} |",
    ]
    if largest:
        lines.append(f"| Largest disclosed value band | {md_escape(largest['display'])} |")
    lines.extend(["", "## Important caveats", ""])
    lines.extend(f"- {item}" for item in facts["caveats"])
    lines.extend(["", "## Sources", ""])
    lines.extend(
        f"- [{md_escape(item['label'])}]({item['url']}) — {item['pages']:,} "
        f"{'page' if item['pages'] == 1 else 'pages'}; document `{item['document_id']}`."
        for item in facts["sources"]
    )
    lines.extend(["", "## Largest disclosed holdings", ""])
    if summary.get("top_holdings"):
        lines.extend(["| Asset | Owner | Value band | Evidence |", "| --- | --- | ---: | --- |"])
        for row in summary["top_holdings"]:
            evidence = f"{API_ROOT}/evidence?id={row['id']}" if row.get("id") else f"{facts['url']}#p{row.get('page')}"
            lines.append(
                f"| {md_escape(row.get('name'))} | {md_escape(row.get('owner'))} | "
                f"{md_escape(pages.rng_pair(row.get('vlo'), row.get('vhi')))} | [record]({evidence}) |"
            )
    else:
        lines.append("No annual holdings statement is loaded for this year.")
    lines.extend(["", "## Transaction categories", ""])
    if summary.get("transaction_types"):
        lines.extend(["| Type | Transactions | Combined range |", "| --- | ---: | ---: |"])
        for row in summary["transaction_types"]:
            lines.append(f"| {md_escape(row['name'])} | {row['n']:,} | {md_escape(pages.rng_sum(row))} |")
    else:
        lines.append("No transactions are assigned to this filing year.")
    lines.extend([
        "",
        "## Data access",
        "",
        f"- [Facts JSON]({API_ROOT}/years/{year}/summary.json)",
        f"- [Assets JSON]({API_ROOT}/years/{year}/assets.json)",
        f"- [Transactions JSON]({API_ROOT}/years/{year}/transactions.json)",
        f"- [Page index JSON]({API_ROOT}/years/{year}/pages.json)",
        f"- [API schema]({API_ROOT}/openapi.json)",
        "",
        "## Citation guidance",
        "",
        "Cite the canonical year page for calculated totals. For a specific holding or transaction, resolve and cite its evidence endpoint, then verify consequential claims against `source_document_url` and `source_page_url`.",
        "",
    ])
    return "\n".join(lines)


def issuer_registry() -> list[dict]:
    """Return the deliberately small, reviewed issuer identity registry."""
    return json.loads(ISSUER_REGISTRY.read_text(encoding="utf-8"))


def issuer_matches(row: dict, issuer: dict) -> bool:
    if str(row.get("cls") or "").casefold() != "common stock":
        return False
    name = str(row.get("name") or "").strip()
    return any(re.search(pattern, name, re.I) for pattern in issuer.get("security_name_patterns") or [])


def issuer_public(issuer: dict) -> dict:
    return {
        "id": issuer["id"],
        "slug": issuer["slug"],
        "name": issuer["name"],
        "ticker": issuer.get("ticker"),
        "aliases": issuer.get("aliases") or [],
        "url": f"{ORIGIN}/companies/{issuer['slug']}/",
        "markdown_url": f"{ORIGIN}/companies/{issuer['slug']}/index.md",
        "data_url": f"{API_ROOT}/issuers/{issuer['slug']}.json",
    }


def aggregate_issuer_year(ctx: pages.Context, year: str, issuer: dict) -> dict:
    asset_path = ROOT / ctx.summaries[year]["files"]["assets"]
    rows = [row for row in json.loads(asset_path.read_text(encoding="utf-8")) if issuer_matches(row, issuer)]
    minimum = sum(row.get("vlo") or 0 for row in rows)
    upper_floor = sum((row.get("vhi") if row.get("vhi") is not None else row.get("vlo")) or 0 for row in rows)
    open_ended = sum(row.get("vlo") is not None and row.get("vhi") is None for row in rows)
    return {
        "year": int(year),
        "holding_count": len(rows),
        "reported_value": {
            "minimum_usd": minimum if rows else None,
            "calculated_upper_floor_usd": upper_floor if rows else None,
            "maximum_usd": upper_floor if rows and not open_ended else None,
            "open_ended_entries": open_ended,
            "display": pages.rng_sum({"lo": minimum, "hiF": upper_floor, "open": open_ended, "any": bool(rows)}),
        },
        "reported_names": list(dict.fromkeys(row.get("name") for row in rows)),
        "records": [{
            **row,
            "issuer": issuer_public(issuer),
            "url": f"{API_ROOT}/evidence?id={row['id']}",
            "source_page_url": f"{ORIGIN}/{year}/#p{row.get('page')}",
        } for row in rows],
    }


def issuer_payload(ctx: pages.Context, facts: dict[str, dict], issuer: dict) -> dict:
    annual = [year for year in ctx.years if not pages.is_ptr_only(ctx.summaries[year])]
    by_year = [aggregate_issuer_year(ctx, year, issuer) for year in annual]
    by_year = [item for item in by_year if item["holding_count"]]
    comparisons = []
    for old, new in zip(by_year, by_year[1:]):
        old_value, new_value = old["reported_value"], new["reported_value"]
        old_hi, new_hi = old_value["calculated_upper_floor_usd"], new_value["calculated_upper_floor_usd"]
        old_lo, new_lo = old_value["minimum_usd"], new_value["minimum_usd"]
        lower = "increased" if new_lo > old_lo else "decreased" if new_lo < old_lo else "unchanged"
        upper = "increased" if new_hi > old_hi else "decreased" if new_hi < old_hi else "unchanged"
        warnings = []
        for year in (str(old["year"]), str(new["year"])):
            cross_year = facts[year]["comparability"]["cross_year_holdings"]
            if cross_year["status"] == "not_directly_comparable" and cross_year["reason"] not in warnings:
                warnings.append(cross_year["reason"])
        if old_value["maximum_usd"] is None or new_value["maximum_usd"] is None:
            relation = "not_comparable"
        elif new_lo > old_value["maximum_usd"]:
            relation = "higher_non_overlapping_range"
        elif new_value["maximum_usd"] < old_lo:
            relation = "lower_non_overlapping_range"
        elif (new_lo, new_value["maximum_usd"]) == (old_lo, old_value["maximum_usd"]):
            relation = "same_reported_range"
        else:
            relation = "overlapping_reported_ranges"
        bounds_direction = "both_increased" if lower == upper == "increased" else (
            "both_decreased" if lower == upper == "decreased" else "mixed_or_unchanged"
        )
        direction_text = bounds_direction.replace("_", " ")
        caveat_text = (f"The filing years are not directly comparable: {' '.join(warnings)}"
                       if warnings else
                       "The disclosures report ranges rather than exact values, so an exact change cannot be calculated.")
        comparisons.append({
            "from_year": old["year"],
            "to_year": new["year"],
            "lower_bound_direction": lower,
            "upper_bound_direction": upper,
            "reported_bounds_direction": bounds_direction,
            "conservative_range_relation": relation,
            "directly_comparable": not warnings,
            "actual_holdings_change": "cannot_be_inferred",
            "warnings": warnings,
            "answer": f"The aggregate reported range's bounds {direction_text}, from {old_value['display']} in {old['year']} to {new_value['display']} in {new['year']}. {caveat_text}",
        })
    return {
        "schema_version": "1.0.0",
        "dataset_version": ctx.modified,
        "entity": issuer_public(issuer),
        "scope": "Annual Schedule A common-stock holdings aggregated across the household interests and portfolio groups printed in each filing.",
        "years": by_year,
        "comparisons": comparisons,
        "compare_api_example": f"{API_ROOT}/compare?entity={issuer.get('ticker') or issuer['slug']}&years=2024,2025",
        "interpretation": [
            "Values are statutory reported ranges, not exact market values or share counts.",
            "Owner codes describe household disclosure attribution and do not establish who directed an investment decision.",
            "Raw security names are preserved on every evidence record; issuer identity is a separate curated normalization.",
        ],
    }


def issuer_markdown(payload: dict) -> str:
    entity = payload["entity"]
    lines = [
        f"# Ro Khanna reported {entity['name']} holdings",
        "",
        f"> Canonical page: {entity['url']}",
        f"> Machine-readable issuer data: {entity['data_url']}",
        f"> Dataset version: {payload['dataset_version']}",
        "",
        f"This page groups reviewed filing-name variants under **{entity['name']} ({entity['ticker']})** while preserving every raw security name and evidence link. Values are household disclosure ranges, not exact holdings or share counts.",
        "",
        "## Annual reported ranges",
        "",
        "| Filing year | Entries | Aggregated reported range | Evidence |",
        "| --- | ---: | ---: | --- |",
    ]
    for year in payload["years"]:
        evidence = " ".join(f"[{index + 1}]({row['url']})" for index, row in enumerate(year["records"]))
        lines.append(f"| [{year['year']}]({ORIGIN}/{year['year']}/) | {year['holding_count']} | {year['reported_value']['display']} | {evidence} |")
    target = next((item for item in payload["comparisons"] if item["from_year"] == 2024 and item["to_year"] == 2025), None)
    if target:
        old = next(item for item in payload["years"] if item["year"] == 2024)
        new = next(item for item in payload["years"] if item["year"] == 2025)
        lines.extend([
            "",
            "## Did the reported range increase from 2024 to 2025?",
            "",
            f"Both reported bounds increased: **{old['reported_value']['display']}** in 2024 to **{new['reported_value']['display']}** in 2025. However, 2025 uses a different filing value-bracket basis, so this does not establish that actual holdings increased.",
        ])
    lines.extend([
        "",
        "## Interpretation",
        "",
        *[f"- {item}" for item in payload["interpretation"]],
        "- The 2025 filing's value-basis warning must accompany comparisons with earlier years.",
        "",
        "## Data access",
        "",
        f"- [Issuer JSON]({entity['data_url']})",
        f"- [Cross-year comparison API]({payload['compare_api_example']})",
        f"- [API schema]({API_ROOT}/openapi.json)",
        "",
    ])
    return "\n".join(lines)


def issuer_html(payload: dict) -> str:
    entity = payload["entity"]
    rows = []
    for year in payload["years"]:
        evidence = " ".join(
            f'<a href="{html.escape(row["url"], quote=True)}">{index + 1}</a>'
            for index, row in enumerate(year["records"])
        )
        rows.append(
            f"<tr><th><a href=\"/{year['year']}/\">{year['year']}</a></th><td>{year['holding_count']}</td>"
            f"<td>{html.escape(year['reported_value']['display'])}</td><td>{evidence}</td></tr>"
        )
    structured = json.dumps({
        "@context": "https://schema.org",
        "@type": "Dataset",
        "name": f"Ro Khanna reported {entity['name']} holdings",
        "url": entity["url"],
        "dateModified": payload["dataset_version"],
        "distribution": [{"@type": "DataDownload", "encodingFormat": "application/json", "contentUrl": entity["data_url"]}],
    }, ensure_ascii=False).replace("</", "<\\/")
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ro Khanna reported {html.escape(entity['name'])} holdings</title>
<meta name="description" content="Source-linked annual reported ranges for {html.escape(entity['name'])} holdings in Ro Khanna household financial disclosures.">
<link rel="canonical" href="{entity['url']}"><link rel="alternate" type="text/markdown" href="{entity['markdown_url']}">
<link rel="alternate" type="application/json" href="{entity['data_url']}"><link rel="describedby" type="application/json" href="{API_ROOT}/openapi.json">
<script type="application/ld+json">{structured}</script>
<style>body{{margin:0;background:#fafafa;color:#17191d;font:16px/1.55 system-ui,sans-serif}}main{{max-width:900px;margin:auto;padding:48px 22px}}h1{{font-size:clamp(2rem,5vw,3.4rem);line-height:1.05}}table{{width:100%;border-collapse:collapse;background:white}}th,td{{padding:10px;border:1px solid #ddd;text-align:left}}a{{color:#174ea6}}.note{{color:#555;max-width:72ch}}</style></head>
<body><main><p><a href="/">Ro Khanna Financial Disclosure Explorer</a></p><h1>Reported {html.escape(entity['name'])} holdings</h1>
<p class="note">Reviewed issuer normalization for {html.escape(', '.join(entity['aliases']))}. Raw filed names and source evidence remain attached to every record. Values are household disclosure ranges, not exact holdings or share counts.</p>
<h2>Annual reported ranges</h2><table><thead><tr><th>Filing year</th><th>Entries</th><th>Aggregated reported range</th><th>Evidence</th></tr></thead><tbody>{''.join(rows)}</tbody></table>
<h2>How to interpret 2024–2025</h2><p>Both reported bounds increased, but the 2025 filing uses a different value-bracket basis. The comparison therefore does not establish that actual holdings increased.</p>
<p><a href="{entity['markdown_url']}">Markdown version</a> · <a href="{entity['data_url']}">JSON data</a> · <a href="{payload['compare_api_example']}">Run the comparison API</a></p></main></body></html>'''


def api_index(ctx: pages.Context) -> dict:
    return {
        "name": "Khanna Disclosure Explorer read-only API",
        "version": "1.0.0",
        "dataset_version": ctx.modified,
        "documentation": f"{API_ROOT}/openapi.json",
        "years": f"{API_ROOT}/years.json",
        "issuers": f"{API_ROOT}/issuers.json",
        "search": f"{API_ROOT}/search?year=2025&kind=transactions&q=apple",
        "compare": f"{API_ROOT}/compare?entity=NVDA&years=2024,2025",
        "evidence": f"{API_ROOT}/evidence?id=transaction:2025:000001",
        "license": "CC0-1.0 for original dataset contributions; see the site license notice.",
    }


def openapi(ctx: pages.Context) -> dict:
    error = {"type": "object", "properties": {"error": {"type": "string"}}}
    not_found = {"description": "Resource not found", "content": {"application/json": {"schema": error}}}
    evidence_record = {
        "type": "object",
        "required": ["id", "doc", "page", "name"],
        "properties": {
            "id": {"type": "string", "description": "Deterministic dataset record ID."},
            "evidence_path": {"type": "string", "description": "Stable lookup path for the evidence record."},
            "doc": {"type": "string", "description": "Source document ID."},
            "page": {"type": "integer", "description": "Page position in the filing-year collection."},
            "label": {"type": ["string", "null"], "description": "Printed filing page label."},
            "name": {"type": "string", "description": "Reported asset or security name."},
            "owner": {"type": ["string", "null"], "description": "Owner code printed on the filing."},
            "cls": {"type": ["string", "null"], "description": "Normalized asset class."},
            "desc": {"type": ["string", "null"], "description": "Plain-language instrument description."},
            "issuer": {"type": ["object", "null"], "description": "Reviewed issuer identity when available; separate from the raw reported name."},
            "url": {"type": "string", "format": "uri", "description": "Absolute evidence lookup URL; present on lookup/search responses."},
            "source_document_url": {"type": "string", "format": "uri", "description": "Source disclosure PDF; present on lookup/search responses."},
            "source_page_url": {"type": "string", "format": "uri", "description": "Explorer URL for the filed page; present on lookup/search responses."},
        },
    }
    return {
        "openapi": "3.1.0",
        "info": {
            "title": "Khanna Disclosure Explorer API",
            "version": "1.0.0",
            "description": "Read-only, source-linked access to Ro Khanna financial-disclosure transcriptions. Statutory ranges are not exact values.",
            "license": {"name": "CC0-1.0 with source-material notice", "url": f"{pages.REPO}/blob/main/DATA_LICENSE.md"},
        },
        "servers": [{"url": API_ROOT}],
        "security": [],
        "components": {"schemas": {
            "EvidenceRecord": evidence_record,
            "SearchResults": {
                "type": "object",
                "required": ["year", "kind", "total", "returned", "results"],
                "properties": {
                    "year": {"type": "integer"},
                    "kind": {"type": "string", "enum": ["assets", "transactions"]},
                    "total": {"type": "integer"},
                    "returned": {"type": "integer"},
                    "next_offset": {"type": ["integer", "null"]},
                    "results": {"type": "array", "items": {"$ref": "#/components/schemas/EvidenceRecord"}},
                },
            },
            "YearFacts": {
                "type": "object",
                "required": ["schema_version", "dataset_version", "year", "metrics", "sources", "caveats"],
                "properties": {
                    "schema_version": {"type": "string"},
                    "dataset_version": {"type": "string", "format": "date"},
                    "year": {"type": "integer"},
                    "filing_type": {"type": "string"},
                    "metrics": {"type": "object"},
                    "sources": {"type": "array", "items": {"type": "object"}},
                    "caveats": {"type": "array", "items": {"type": "string"}},
                    "comparability": {"type": "object", "description": "Machine-readable warning status for cross-year holdings interpretation."},
                },
            },
            "IssuerComparison": {
                "type": "object",
                "required": ["entity", "years", "comparisons", "interpretation"],
                "properties": {
                    "entity": {"type": "object", "description": "Curated issuer identity, separate from raw filed security names."},
                    "years": {"type": "array", "items": {"type": "object"}},
                    "comparisons": {"type": "array", "items": {"type": "object"}},
                    "interpretation": {"type": "array", "items": {"type": "string"}},
                },
            },
        }},
        "paths": {
            "/years.json": {"get": {"operationId": "getYears", "summary": "List filing years", "responses": {"200": {"description": "Year index"}, "404": not_found}}},
            "/issuers.json": {"get": {"operationId": "getIssuers", "summary": "List reviewed issuer identities and their indexable pages", "responses": {"200": {"description": "Issuer index"}, "404": not_found}}},
            "/issuers/{slug}.json": {"get": {"operationId": "getIssuer", "summary": "Get source-linked annual holdings for one reviewed issuer", "parameters": [{"name": "slug", "in": "path", "required": True, "schema": {"type": "string"}}], "responses": {"200": {"description": "Issuer holdings and comparisons", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/IssuerComparison"}}}}, "404": not_found}}},
            "/years/{year}/summary.json": {"get": {"operationId": "getYearSummary", "summary": "Get calculated facts and provenance for one year", "parameters": [{"name": "year", "in": "path", "required": True, "schema": {"type": "integer", "minimum": 2016, "maximum": 2026}}], "responses": {"200": {"description": "Year facts", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/YearFacts"}}}}, "404": not_found}}},
            "/years/{year}/{kind}.json": {"get": {"operationId": "getYearRecords", "summary": "Download all records of one kind for a year", "parameters": [{"name": "year", "in": "path", "required": True, "schema": {"type": "integer", "minimum": 2016, "maximum": 2026}}, {"name": "kind", "in": "path", "required": True, "schema": {"type": "string", "enum": ["assets", "transactions", "pages"]}}], "responses": {"200": {"description": "Record array", "content": {"application/json": {"schema": {"type": "array", "items": {"$ref": "#/components/schemas/EvidenceRecord"}}}}}, "404": not_found}}},
            "/search": {"get": {"operationId": "searchRecords", "summary": "Search assets or transactions within one year", "parameters": [{"name": "year", "in": "query", "required": True, "schema": {"type": "integer"}}, {"name": "kind", "in": "query", "required": True, "schema": {"type": "string", "enum": ["assets", "transactions"]}}, {"name": "q", "in": "query", "schema": {"type": "string"}}, {"name": "owner", "in": "query", "schema": {"type": "string"}}, {"name": "class", "in": "query", "schema": {"type": "string"}}, {"name": "type", "in": "query", "schema": {"type": "string"}}, {"name": "limit", "in": "query", "schema": {"type": "integer", "minimum": 1, "maximum": 100, "default": 25}}, {"name": "offset", "in": "query", "schema": {"type": "integer", "minimum": 0, "default": 0}}], "responses": {"200": {"description": "Search results", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/SearchResults"}}}}, "400": {"description": "Invalid query", "content": {"application/json": {"schema": error}}}}}},
            "/compare": {"get": {"operationId": "compareIssuerHoldings", "summary": "Compare one issuer's annual reported common-stock holdings across filing years", "description": "Resolves reviewed aliases such as NVDA, preserves raw filed names, sums statutory bands, and returns machine-readable comparability warnings. An increase in reported bounds is not necessarily an increase in actual holdings.", "parameters": [{"name": "entity", "in": "query", "required": True, "example": "NVDA", "schema": {"type": "string"}}, {"name": "years", "in": "query", "required": False, "example": "2024,2025", "schema": {"type": "string", "default": "2024,2025"}}], "responses": {"200": {"description": "Source-linked issuer comparison", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/IssuerComparison"}}}}, "400": {"description": "Invalid entity or filing years", "content": {"application/json": {"schema": error}}}}}},
            "/evidence": {"get": {"operationId": "getEvidence", "summary": "Resolve a deterministic asset or transaction ID", "parameters": [{"name": "id", "in": "query", "required": True, "schema": {"type": "string", "pattern": "^(asset|transaction):20[0-9]{2}:[0-9]{6}$"}}], "responses": {"200": {"description": "Evidence record", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/EvidenceRecord"}}}}, "404": {"description": "Unknown record", "content": {"application/json": {"schema": error}}}}}},
        },
    }


def update_vercel_routes(ctx: pages.Context) -> None:
    path = ROOT / "vercel.json"
    config = json.loads(path.read_text(encoding="utf-8"))
    rewrites = [
        {"source": "/api/v1", "destination": "/machine/v1/index.json"},
        {"source": "/api/v1/index.json", "destination": "/machine/v1/index.json"},
        {"source": "/api/v1/openapi.json", "destination": "/machine/v1/openapi.json"},
        {"source": "/api/v1/years.json", "destination": "/machine/v1/years.json"},
        {"source": "/api/v1/issuers.json", "destination": "/machine/v1/issuers.json"},
    ]
    for issuer in issuer_registry():
        rewrites.append({
            "source": f"/api/v1/issuers/{issuer['slug']}.json",
            "destination": f"/machine/v1/issuers/{issuer['slug']}.json",
        })
    for year in ctx.years:
        files = ctx.summaries[year]["files"]
        rewrites.extend([
            {"source": f"/api/v1/years/{year}/summary.json", "destination": f"/{year}/facts.json"},
            {"source": f"/api/v1/years/{year}/assets.json", "destination": f"/{files['assets']}"},
            {"source": f"/api/v1/years/{year}/transactions.json", "destination": f"/{files['transactions']}"},
            {"source": f"/api/v1/years/{year}/pages.json", "destination": f"/{files['pages']}"},
        ])
    config["rewrites"] = rewrites
    path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    ctx = pages.Context(pages.load_summaries())
    facts = {year: facts_for(ctx, year) for year in ctx.years}
    markdown = {year: markdown_for(ctx, year, facts[year]) for year in ctx.years}
    issuers = issuer_registry()
    issuer_payloads = {issuer["slug"]: issuer_payload(ctx, facts, issuer) for issuer in issuers}

    for year in ctx.years:
        write_json(ROOT / year / "facts.json", facts[year])
        (ROOT / year / "index.md").write_text(markdown[year], encoding="utf-8")

    first, last = ctx.tx_span()
    trades_md = [
        f"# Ro Khanna reported stock trades, {first}–{last}",
        "",
        f"> Canonical page: {ORIGIN}/stock-trades/",
        f"> Dataset version: {ctx.modified}",
        "",
        f"The loaded House filings contain {ctx.tx_total:,} reported household transactions. Amounts are statutory value bands, not exact trade values, and the filings do not establish who made an investment decision.",
        "",
        "## Filing-year coverage",
        "",
        "| Year | Reported transactions | Active trading days | Combined value range |",
        "| --- | ---: | ---: | ---: |",
    ]
    for year in reversed(ctx.years):
        summary = ctx.summaries[year]
        trades_md.append(
            f"| [{year}]({ORIGIN}/{year}/index.md) | {summary['counts']['transactions']:,} | "
            f"{summary['counts'].get('active_trading_days', 0):,} | {pages.rng_sum(summary['transaction_total'])} |"
        )
    trades_md.extend([
        "",
        "## Data access",
        "",
        f"- [Year index]({API_ROOT}/years.json)",
        f"- [API schema]({API_ROOT}/openapi.json)",
        f"- [Search example]({API_ROOT}/search?year={last}&kind=transactions&q=apple)",
        "",
    ])
    (ROOT / "stock-trades" / "index.md").write_text("\n".join(trades_md), encoding="utf-8")

    MACHINE.mkdir(parents=True, exist_ok=True)
    write_json(MACHINE / "index.json", api_index(ctx))
    write_json(MACHINE / "openapi.json", openapi(ctx))
    write_json(MACHINE / "years.json", {
        "dataset_version": ctx.modified,
        "years": [{
            "year": int(year),
            "filing_type": facts[year]["filing_type"],
            "canonical_url": facts[year]["url"],
            "summary_url": f"{API_ROOT}/years/{year}/summary.json",
            "markdown_url": f"{ORIGIN}/{year}/index.md",
        } for year in reversed(ctx.years)],
    })
    write_json(MACHINE / "issuers.json", {
        "dataset_version": ctx.modified,
        "scope": "Reviewed issuer identities used to join raw filed security-name variants without altering the transcription.",
        "issuers": [issuer_public(issuer) for issuer in issuers],
    })
    for issuer in issuers:
        slug = issuer["slug"]
        payload = issuer_payloads[slug]
        write_json(MACHINE / "issuers" / f"{slug}.json", payload)
        company_dir = ROOT / "companies" / slug
        company_dir.mkdir(parents=True, exist_ok=True)
        issuer_md = issuer_markdown(payload)
        (company_dir / "index.md").write_text(issuer_md, encoding="utf-8")
        (company_dir / "index.html").write_text(issuer_html(payload), encoding="utf-8")

    concise = [
        "# Ro Khanna Financial Disclosure Explorer",
        "",
        "> Independent, source-linked transcription of U.S. House financial disclosures for Ro Khanna, covering 2016–2026.",
        "",
        "Use the annual Markdown or facts JSON pages for compact answers. Use the API for complete holdings and transaction arrays. Dollar figures are statutory ranges, not exact values; household disclosures can include a spouse and dependent children.",
        "",
        "## Primary resources",
        "",
        f"- [Latest annual filing]({ORIGIN}/): Human-readable overview with methodology and sources.",
        f"- [All reported stock trades]({ORIGIN}/stock-trades/): Cross-year transaction analysis.",
        f"- [API documentation]({API_ROOT}/openapi.json): OpenAPI 3.1 description of the read-only API.",
        f"- [Year index]({API_ROOT}/years.json): Canonical, Markdown, and JSON URLs for every filing year.",
        f"- [Issuer index]({API_ROOT}/issuers.json): Reviewed company identities that join raw filing-name variants.",
        f"- [Issuer comparison API]({API_ROOT}/compare?entity=NVDA&years=2024,2025): Cross-year reported bounds, evidence, and comparability warnings.",
        f"- [Full LLM context]({ORIGIN}/llms-full.txt): Expanded annual summaries and citation guidance.",
        f"- [Data methodology]({pages.REPO}/blob/main/data/README.md): Normalized schema, caveats, and audit process.",
        "",
        "## Filing years",
        "",
    ]
    concise.extend(
        f"- [{year} filing Markdown]({ORIGIN}/{year}/index.md): "
        f"{facts[year]['metrics']['reported_transactions']['count']:,} reported transactions; "
        f"{facts[year]['metrics']['source_linked_asset_entries']:,} asset entries."
        for year in reversed(ctx.years)
    )
    concise.extend([
        "",
        "## Common question pattern",
        "",
        "Question: Did Ro Khanna's reported NVIDIA holdings increase or decrease from 2024 to 2025?",
        f"Use [{API_ROOT}/compare?entity=NVDA&years=2024,2025]({API_ROOT}/compare?entity=NVDA&years=2024,2025). Report the direction of the disclosed lower and upper bounds separately from actual holdings, and carry forward the returned 2025 comparability warning.",
        "",
        "## Citation and interpretation",
        "",
        "- Cite a canonical year page for aggregate calculations.",
        "- Cite an evidence record's `url` for a holding or transaction, then verify consequential claims against its linked filing page.",
        "- Preserve open-ended ranges and year-specific caveats. Do not describe the calculated totals as certified personal net worth.",
        "- Treat OCR and model-assisted transcription as fallible; unresolved readings remain explicit in the data.",
        "",
    ])
    (ROOT / "llms.txt").write_text("\n".join(concise), encoding="utf-8")

    full = concise + ["# Reviewed issuer summaries", ""]
    for issuer in issuers:
        full.append(issuer_markdown(issuer_payloads[issuer["slug"]]))
    full.extend(["# Expanded annual summaries", ""])
    for year in reversed(ctx.years):
        full.append(markdown[year])
    (ROOT / "llms-full.txt").write_text("\n\n".join(full), encoding="utf-8")

    update_vercel_routes(ctx)
    print(f"llm access: {len(ctx.years)} Markdown pages, {len(ctx.years)} facts files, API v1, llms.txt")


if __name__ == "__main__":
    main()
