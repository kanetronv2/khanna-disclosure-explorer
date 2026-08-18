#!/usr/bin/env python3
"""Generate compact, stable, provenance-first surfaces for LLMs and data agents.

The browser application deliberately keeps its large per-year arrays in hashed files.  This
builder publishes stable API routes to those files, concise JSON facts, Markdown mirrors, and
the llms.txt discovery documents without duplicating the underlying data in the deployment.
"""

from __future__ import annotations

import json
from pathlib import Path

import build_pages as pages


ROOT = Path(__file__).resolve().parents[1]
ORIGIN = pages.ORIGIN
API_ROOT = f"{ORIGIN}/api/v1"
MACHINE = ROOT / "machine" / "v1"


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


def api_index(ctx: pages.Context) -> dict:
    return {
        "name": "Khanna Disclosure Explorer read-only API",
        "version": "1.0.0",
        "dataset_version": ctx.modified,
        "documentation": f"{API_ROOT}/openapi.json",
        "years": f"{API_ROOT}/years.json",
        "search": f"{API_ROOT}/search?year=2025&kind=transactions&q=apple",
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
                },
            },
        }},
        "paths": {
            "/years.json": {"get": {"operationId": "getYears", "summary": "List filing years", "responses": {"200": {"description": "Year index"}, "404": not_found}}},
            "/years/{year}/summary.json": {"get": {"operationId": "getYearSummary", "summary": "Get calculated facts and provenance for one year", "parameters": [{"name": "year", "in": "path", "required": True, "schema": {"type": "integer", "minimum": 2016, "maximum": 2026}}], "responses": {"200": {"description": "Year facts", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/YearFacts"}}}}, "404": not_found}}},
            "/years/{year}/{kind}.json": {"get": {"operationId": "getYearRecords", "summary": "Download all records of one kind for a year", "parameters": [{"name": "year", "in": "path", "required": True, "schema": {"type": "integer", "minimum": 2016, "maximum": 2026}}, {"name": "kind", "in": "path", "required": True, "schema": {"type": "string", "enum": ["assets", "transactions", "pages"]}}], "responses": {"200": {"description": "Record array", "content": {"application/json": {"schema": {"type": "array", "items": {"$ref": "#/components/schemas/EvidenceRecord"}}}}}, "404": not_found}}},
            "/search": {"get": {"operationId": "searchRecords", "summary": "Search assets or transactions within one year", "parameters": [{"name": "year", "in": "query", "required": True, "schema": {"type": "integer"}}, {"name": "kind", "in": "query", "required": True, "schema": {"type": "string", "enum": ["assets", "transactions"]}}, {"name": "q", "in": "query", "schema": {"type": "string"}}, {"name": "owner", "in": "query", "schema": {"type": "string"}}, {"name": "class", "in": "query", "schema": {"type": "string"}}, {"name": "type", "in": "query", "schema": {"type": "string"}}, {"name": "limit", "in": "query", "schema": {"type": "integer", "minimum": 1, "maximum": 100, "default": 25}}, {"name": "offset", "in": "query", "schema": {"type": "integer", "minimum": 0, "default": 0}}], "responses": {"200": {"description": "Search results", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/SearchResults"}}}}, "400": {"description": "Invalid query", "content": {"application/json": {"schema": error}}}}}},
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
    ]
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
        "## Citation and interpretation",
        "",
        "- Cite a canonical year page for aggregate calculations.",
        "- Cite an evidence record's `url` for a holding or transaction, then verify consequential claims against its linked filing page.",
        "- Preserve open-ended ranges and year-specific caveats. Do not describe the calculated totals as certified personal net worth.",
        "- Treat OCR and model-assisted transcription as fallible; unresolved readings remain explicit in the data.",
        "",
    ])
    (ROOT / "llms.txt").write_text("\n".join(concise), encoding="utf-8")

    full = concise + ["# Expanded annual summaries", ""]
    for year in reversed(ctx.years):
        full.append(markdown[year])
    (ROOT / "llms-full.txt").write_text("\n\n".join(full), encoding="utf-8")

    update_vercel_routes(ctx)
    print(f"llm access: {len(ctx.years)} Markdown pages, {len(ctx.years)} facts files, API v1, llms.txt")


if __name__ == "__main__":
    main()
