#!/usr/bin/env python3
"""Fail fast when an LLM discovery, facts, evidence, or API surface drifts."""

from __future__ import annotations

import json
import re
import subprocess
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path

import build_pages as pages


ROOT = Path(__file__).resolve().parents[1]
YEARS = [str(year) for year in range(2016, 2027)]


def require(condition, message):
    if not condition:
        raise AssertionError(message)


class JsonLdParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self._active = False
        self._buffer = []
        self.blocks = []

    def handle_starttag(self, tag, attrs):
        if tag == "script" and dict(attrs).get("type") == "application/ld+json":
            self._active = True
            self._buffer = []

    def handle_data(self, data):
        if self._active:
            self._buffer.append(data)

    def handle_endtag(self, tag):
        if tag == "script" and self._active:
            self.blocks.append("".join(self._buffer))
            self._active = False


def schema_nodes(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from schema_nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from schema_nodes(child)


def audit_dataset_json_ld():
    dataset_count = 0
    for path in sorted(ROOT.rglob("*.html")):
        if any(part in {".git", "build", "node_modules"} for part in path.parts):
            continue
        parser = JsonLdParser()
        parser.feed(path.read_text(encoding="utf-8"))
        for index, block in enumerate(parser.blocks, 1):
            try:
                structured = json.loads(block)
            except json.JSONDecodeError as error:
                raise AssertionError(f"{path.relative_to(ROOT)} JSON-LD block {index}: {error}") from error
            for node in schema_nodes(structured):
                node_type = node.get("@type")
                types = [node_type] if isinstance(node_type, str) else node_type or []
                if "Dataset" not in types:
                    continue
                dataset_count += 1
                label = f"{path.relative_to(ROOT)} Dataset {node.get('name')!r}"
                for field in ("name", "description", "creator", "license"):
                    require(node.get(field), f"{label}: missing {field}")
                require(50 <= len(node["description"]) <= 5000,
                        f"{label}: description must be 50–5000 characters")
    require(dataset_count > 0, "no Dataset JSON-LD found")
    return dataset_count


def main():
    summaries = pages.load_summaries()
    require(sorted(summaries) == YEARS, "summary years do not match 2016–2026")

    llms = (ROOT / "llms.txt").read_text(encoding="utf-8")
    full = (ROOT / "llms-full.txt").read_text(encoding="utf-8")
    require(len(llms) < 20_000, "llms.txt should remain a concise discovery document")
    require("API documentation" in llms and "Citation and interpretation" in llms, "llms.txt is incomplete")
    require("issuers/nvidia/comparisons/2024-2025.json" in llms,
            "llms.txt lacks the canonical cross-year API resource")
    require("issuers/nvidia/comparisons/2024-2025.txt" in llms,
            "llms.txt lacks the answer-ready text representation")
    require(len(full) > len(llms), "llms-full.txt should contain expanded context")

    heading_eyebrow = re.compile(
        r'<div class="section-heading">(?:(?!</div>).)*<span class="section-kicker"', re.S
    )
    heading_sources = [ROOT / "templates/index.html", ROOT / "templates/stock-trades.html",
                       ROOT / "index.html", ROOT / "stock-trades/index.html"]
    heading_sources.extend(ROOT / year / "index.html" for year in YEARS)
    for path in heading_sources:
        require(not heading_eyebrow.search(path.read_text(encoding="utf-8")),
                f"{path.relative_to(ROOT)}: section headings must not use eyebrow labels")

    issuer_registry = json.loads((ROOT / "lib/issuer-registry.json").read_text(encoding="utf-8"))
    require(issuer_registry and len({row["id"] for row in issuer_registry}) == len(issuer_registry),
            "issuer registry IDs must be present and unique")
    require(len({row["slug"] for row in issuer_registry}) == len(issuer_registry),
            "issuer registry slugs must be unique")
    for issuer in issuer_registry:
        require(issuer.get("name") and issuer.get("aliases") and issuer.get("security_name_patterns"),
                f"{issuer.get('id')}: issuer identity is incomplete")
        featured = issuer.get("featured_comparison") or []
        require(not featured or (len(featured) == 2 and all(2016 <= int(year) <= 2026 for year in featured)),
                f"{issuer.get('id')}: featured comparison must contain two filing years")
        for pattern in issuer["security_name_patterns"]:
            re.compile(pattern)
    require("require('./issuer-registry.json')" in (ROOT / "lib/issuer.js").read_text(encoding="utf-8"),
            "runtime issuer registry must remain beside its helper because /data is excluded from Vercel")
    evidence_config = json.loads((ROOT / "lib/evidence-config.json").read_text(encoding="utf-8"))
    require(str(evidence_config.get("evidence_origin") or "").startswith("https://"),
            "runtime evidence origin must be HTTPS")
    for script in (ROOT / "api/v1/search.js", ROOT / "api/v1/evidence.js"):
        require("../../lib/evidence.js" in script.read_text(encoding="utf-8"),
                f"{script.name}: source documents must use the configurable evidence origin")

    for year in YEARS:
        facts = json.loads((ROOT / year / "facts.json").read_text(encoding="utf-8"))
        markdown = (ROOT / year / "index.md").read_text(encoding="utf-8")
        summary = summaries[year]
        require(facts["year"] == int(year), f"{year}: wrong facts year")
        require(facts["metrics"]["reported_transactions"]["count"] == summary["counts"]["transactions"],
                f"{year}: transaction count drift")
        require(facts["metrics"]["reported_holdings"]["minimum_usd"] == summary["holdings"]["lo"],
                f"{year}: holdings minimum drift")
        require(facts.get("comparability", {}).get("cross_year_holdings", {}).get("status"),
                f"{year}: machine-readable holdings comparability missing")
        require(f"/api/v1/years/{year}/summary.json" in markdown, f"{year}: Markdown lacks facts URL")

        for kind, singular in (("assets", "asset"), ("transactions", "transaction")):
            data_path = ROOT / summary["files"][kind]
            rows = json.loads(data_path.read_text(encoding="utf-8"))
            if rows:
                require(rows[0]["id"] == f"{singular}:{year}:000001", f"{year}: first {kind} ID drift")
                require(rows[-1]["id"] == f"{singular}:{year}:{len(rows):06d}", f"{year}: last {kind} ID drift")
                require(rows[0]["evidence_path"].endswith(rows[0]["id"]), f"{year}: {kind} evidence URL drift")
                require(rows[0].get("doc") and rows[0].get("page"),
                        f"{year}: {kind} source pointers missing")

        html = (ROOT / year / "index.html").read_text(encoding="utf-8")
        require(f'href="https://www.rokhanna.money/{year}/index.md"' in html,
                f"{year}: HTML Markdown alternate missing")
        require(f'href="https://www.rokhanna.money/{year}/facts.json"' in html,
                f"{year}: HTML JSON alternate missing")

        page_details = sorted((ROOT / "site-data" / year / "pages").glob("*.json"))
        require(page_details, f"{year}: page-detail data missing")
        sample = json.loads(page_details[0].read_text(encoding="utf-8"))
        require(str(summary.get("evidence_origin") or "").startswith("https://"),
                f"{year}: evidence origin must be absolute")
        require(str(sample.get("image") or "").startswith(("docs/", "ocr/pages/")),
                f"{year}: page evidence path drift")

    config = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
    rewrites = {item["source"]: item["destination"] for item in config.get("rewrites") or []}
    require(rewrites.get("/api/v1") == "/machine/v1/index.json", "API discovery rewrite missing")
    require(rewrites.get("/api/v1/issuers.json") == "/machine/v1/issuers.json",
            "issuer index rewrite missing")
    require(rewrites.get("/api/v1/issuers/:slug.json") == "/machine/v1/issuers/:slug.json",
            "generic issuer JSON rewrite missing")
    require(rewrites.get("/api/v1/issuers/:slug.txt") == "/machine/v1/issuers/:slug.txt",
            "generic issuer text rewrite missing")
    require(rewrites.get("/api/v1/issuers/:slug/comparisons/:range.json") ==
            "/api/v1/compare?entity=:slug&years=:range&resource=1",
            "canonical comparison JSON rewrite missing")
    require(rewrites.get("/api/v1/issuers/:slug/comparisons/:range.txt") ==
            "/api/v1/compare?entity=:slug&years=:range&resource=1&format=text",
            "canonical comparison text rewrite missing")
    for year in YEARS:
        for kind in ("assets", "transactions", "pages"):
            source = f"/api/v1/years/{year}/{kind}.json"
            require(source in rewrites, f"missing rewrite {source}")
            require((ROOT / rewrites[source].lstrip("/")).is_file(), f"rewrite target missing: {rewrites[source]}")

    openapi = json.loads((ROOT / "machine/v1/openapi.json").read_text(encoding="utf-8"))
    require(openapi.get("openapi") == "3.1.0", "OpenAPI version drift")
    require(all(path in openapi["paths"] for path in (
        "/search", "/evidence", "/compare", "/issuers/{slug}.json", "/issuers/{slug}.txt",
        "/issuers/{slug}/comparisons/{range}.json", "/issuers/{slug}/comparisons/{range}.txt")),
            "API operations missing")
    operation_ids = [operation["operationId"] for item in openapi["paths"].values()
                     for operation in item.values() if isinstance(operation, dict) and operation.get("operationId")]
    require(len(operation_ids) == len(set(operation_ids)), "OpenAPI operation IDs must be unique")
    comparison_schema = openapi["components"]["schemas"]["ComparisonResult"]
    require(comparison_schema.get("examples") and comparison_schema["properties"].get("evidence") and
            comparison_schema["properties"].get("calculation"),
            "OpenAPI comparison schema lacks examples, evidence, or calculation semantics")

    nvidia = json.loads((ROOT / "machine/v1/issuers/nvidia.json").read_text(encoding="utf-8"))
    require(nvidia["entity"]["ticker"] == "NVDA", "NVIDIA issuer identity drift")
    nvidia_years = {row["year"]: row for row in nvidia["years"]}
    require(nvidia_years[2024]["holding_count"] == 5, "NVIDIA 2024 holding count drift")
    require(nvidia_years[2024]["reported_value"]["minimum_usd"] == 851005 and
            nvidia_years[2024]["reported_value"]["maximum_usd"] == 1765000,
            "NVIDIA 2024 aggregate drift")
    require(nvidia_years[2025]["holding_count"] == 8, "NVIDIA 2025 holding count drift")
    require(nvidia_years[2025]["reported_value"]["minimum_usd"] == 1210008 and
            nvidia_years[2025]["reported_value"]["maximum_usd"] == 2550000,
            "NVIDIA 2025 aggregate drift")
    target = next(row for row in nvidia["comparisons"]
                  if row["from_year"] == 2024 and row["to_year"] == 2025)
    require(target["reported_bounds_direction"] == "both_increased" and not target["directly_comparable"],
            "NVIDIA comparison must preserve both the reported direction and the 2025 warning")
    require(target["conservative_range_relation"] == "overlapping_reported_ranges" and
            "not directly comparable" in target["answer"],
            "NVIDIA comparison must be answer-ready without overstating the evidence")
    require(target.get("answer_basis") and target.get("calculation") and target.get("limitations") and
            target.get("evidence"), "NVIDIA comparison lacks answer-ready provenance fields")
    require(nvidia.get("generated_at") and nvidia.get("canonical_url") ==
            "https://www.rokhanna.money/api/v1/issuers/nvidia.json",
            "issuer resource lacks stable generation/canonical metadata")
    require(nvidia["entity"]["url"] == nvidia["entity"]["data_url"] and
            "/companies/" not in json.dumps(nvidia), "issuer identity still points to a presentation page")
    issuer_text = (ROOT / "machine/v1/issuers/nvidia.txt").read_text(encoding="utf-8")
    require(target["answer"] in issuer_text and "Canonical JSON:" in issuer_text,
            "issuer text representation is incomplete")
    require(not (ROOT / "companies").exists(), "API-only architecture must not generate issuer pages")
    dataset_count = audit_dataset_json_ld()

    robots = (ROOT / "robots.txt").read_text(encoding="utf-8")
    for agent in ("OAI-SearchBot", "ChatGPT-User", "GPTBot", "ClaudeBot", "PerplexityBot", "Google-Extended"):
        require(f"User-agent: {agent}" in robots, f"robots.txt lacks {agent}")
    require("Disallow: /site-data/" in robots and "Allow: /site-data/summaries.js" in robots,
            "robots crawl-budget rules drifted")

    tree = ET.parse(ROOT / "sitemap.xml")
    namespace = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    sitemap_urls = {node.text for node in tree.findall("s:url/s:loc", namespace)}
    for url in ("https://www.rokhanna.money/llms.txt", "https://www.rokhanna.money/api/v1/openapi.json",
                "https://www.rokhanna.money/api/v1/issuers/nvidia.json",
                "https://www.rokhanna.money/api/v1/issuers/nvidia.txt",
                "https://www.rokhanna.money/api/v1/issuers/nvidia/comparisons/2024-2025.json",
                "https://www.rokhanna.money/api/v1/issuers/nvidia/comparisons/2024-2025.txt"):
        require(url in sitemap_urls, f"sitemap lacks {url}")
    require(not any("/companies/" in url for url in sitemap_urls),
            "sitemap still exposes removed issuer presentation pages")

    api_headers = next(item["headers"] for item in config["headers"] if item["source"] == "/api/v1/(.*)")
    api_header_map = {item["key"]: item["value"] for item in api_headers}
    for key in ("Access-Control-Allow-Origin", "Cache-Control", "Vary", "X-Robots-Tag", "Link"):
        require(key in api_header_map, f"API delivery header missing: {key}")

    key = "264f47e7ac6f754571619ef2cfe0c4af"
    require((ROOT / f"{key}.txt").read_text(encoding="utf-8").strip() == key, "IndexNow key file drift")

    for script in (ROOT / "api/v1/search.js", ROOT / "api/v1/evidence.js", ROOT / "api/v1/compare.js"):
        result = subprocess.run(["node", "--check", str(script)], capture_output=True, text=True)
        require(result.returncode == 0, f"{script.name}: {result.stderr.strip()}")
    handler_check = subprocess.run(
        ["node", str(ROOT / "scripts/check_api_handlers.js")], capture_output=True, text=True
    )
    require(handler_check.returncode == 0, handler_check.stderr.strip() or "API handler audit failed")

    # Guard against accidental unescaped control text in generated JSON and Markdown URLs.
    require(not re.search(r"https://www\.rokhanna\.money//", llms + full), "double-slash URL in LLM documents")
    print(f"llm access audit: PASS (11 years, {dataset_count} Dataset schemas, discovery, Markdown, facts, API-only issuer JSON/text, comparison, evidence, robots, sitemap, IndexNow)")


if __name__ == "__main__":
    main()
