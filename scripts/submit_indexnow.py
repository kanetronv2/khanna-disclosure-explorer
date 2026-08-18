#!/usr/bin/env python3
"""Notify IndexNow participants about canonical site URLs after a verified deployment."""

from __future__ import annotations

import argparse
import json
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
ORIGIN = "https://www.rokhanna.money"
KEY = "264f47e7ac6f754571619ef2cfe0c4af"
KEY_LOCATION = f"{ORIGIN}/{KEY}.txt"
ENDPOINT = "https://api.indexnow.org/indexnow"


def sitemap_urls():
    tree = ET.parse(ROOT / "sitemap.xml")
    namespace = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    return [node.text.strip() for node in tree.findall("s:url/s:loc", namespace) if node.text]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="print the request without submitting it")
    parser.add_argument("--url", action="append", dest="urls", help="submit only this same-origin URL; repeatable")
    args = parser.parse_args()

    urls = args.urls or sitemap_urls()
    urls = list(dict.fromkeys(url for url in urls if urlparse(url).netloc == "www.rokhanna.money"))
    if not urls:
        raise SystemExit("No same-origin URLs to submit")
    payload = {
        "host": "www.rokhanna.money",
        "key": KEY,
        "keyLocation": KEY_LOCATION,
        "urlList": urls,
    }
    if args.dry_run:
        print(json.dumps(payload, indent=2))
        return

    request = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        if response.status not in (200, 202):
            raise SystemExit(f"IndexNow returned HTTP {response.status}")
        print(f"IndexNow accepted {len(urls)} URLs (HTTP {response.status})")


if __name__ == "__main__":
    main()
