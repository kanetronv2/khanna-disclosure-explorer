#!/usr/bin/env python3
"""Fail fast when an LLM discovery, facts, evidence, or API surface drifts."""

from __future__ import annotations

import json
import re
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import build_pages as pages


ROOT = Path(__file__).resolve().parents[1]
YEARS = [str(year) for year in range(2016, 2027)]


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    summaries = pages.load_summaries()
    require(sorted(summaries) == YEARS, "summary years do not match 2016–2026")

    llms = (ROOT / "llms.txt").read_text(encoding="utf-8")
    full = (ROOT / "llms-full.txt").read_text(encoding="utf-8")
    require(len(llms) < 20_000, "llms.txt should remain a concise discovery document")
    require("API documentation" in llms and "Citation and interpretation" in llms, "llms.txt is incomplete")
    require(len(full) > len(llms), "llms-full.txt should contain expanded context")

    for year in YEARS:
        facts = json.loads((ROOT / year / "facts.json").read_text(encoding="utf-8"))
        markdown = (ROOT / year / "index.md").read_text(encoding="utf-8")
        summary = summaries[year]
        require(facts["year"] == int(year), f"{year}: wrong facts year")
        require(facts["metrics"]["reported_transactions"]["count"] == summary["counts"]["transactions"],
                f"{year}: transaction count drift")
        require(facts["metrics"]["reported_holdings"]["minimum_usd"] == summary["holdings"]["lo"],
                f"{year}: holdings minimum drift")
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

    config = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
    rewrites = {item["source"]: item["destination"] for item in config.get("rewrites") or []}
    require(rewrites.get("/api/v1") == "/machine/v1/index.json", "API discovery rewrite missing")
    for year in YEARS:
        for kind in ("assets", "transactions", "pages"):
            source = f"/api/v1/years/{year}/{kind}.json"
            require(source in rewrites, f"missing rewrite {source}")
            require((ROOT / rewrites[source].lstrip("/")).is_file(), f"rewrite target missing: {rewrites[source]}")

    openapi = json.loads((ROOT / "machine/v1/openapi.json").read_text(encoding="utf-8"))
    require(openapi.get("openapi") == "3.1.0", "OpenAPI version drift")
    require("/search" in openapi["paths"] and "/evidence" in openapi["paths"], "API operations missing")

    robots = (ROOT / "robots.txt").read_text(encoding="utf-8")
    for agent in ("OAI-SearchBot", "ChatGPT-User", "GPTBot", "ClaudeBot", "PerplexityBot", "Google-Extended"):
        require(f"User-agent: {agent}" in robots, f"robots.txt lacks {agent}")
    require("Disallow: /site-data/" in robots and "Allow: /site-data/summaries.js" in robots,
            "robots crawl-budget rules drifted")

    tree = ET.parse(ROOT / "sitemap.xml")
    namespace = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    sitemap_urls = {node.text for node in tree.findall("s:url/s:loc", namespace)}
    for url in ("https://www.rokhanna.money/llms.txt", "https://www.rokhanna.money/api/v1/openapi.json"):
        require(url in sitemap_urls, f"sitemap lacks {url}")

    key = "264f47e7ac6f754571619ef2cfe0c4af"
    require((ROOT / f"{key}.txt").read_text(encoding="utf-8").strip() == key, "IndexNow key file drift")

    for script in (ROOT / "api/v1/search.js", ROOT / "api/v1/evidence.js"):
        result = subprocess.run(["node", "--check", str(script)], capture_output=True, text=True)
        require(result.returncode == 0, f"{script.name}: {result.stderr.strip()}")
    handler_check = subprocess.run(
        ["node", str(ROOT / "scripts/check_api_handlers.js")], capture_output=True, text=True
    )
    require(handler_check.returncode == 0, handler_check.stderr.strip() or "API handler audit failed")

    # Guard against accidental unescaped control text in generated JSON and Markdown URLs.
    require(not re.search(r"https://www\.rokhanna\.money//", llms + full), "double-slash URL in LLM documents")
    print("llm access audit: PASS (11 years, discovery, Markdown, facts, evidence, API, robots, sitemap, IndexNow)")


if __name__ == "__main__":
    main()
