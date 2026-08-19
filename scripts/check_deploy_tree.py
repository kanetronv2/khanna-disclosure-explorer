#!/usr/bin/env python3
"""Fail if a slim Vercel tree contains source evidence or broken external URLs."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


FORBIDDEN_ROOTS = {"data", "docs", "ocr", "scripts", "templates", "scratch_ocr", "scratchpad"}
REQUIRED = {
    "index.html", "vercel.json", "robots.txt", "sitemap.xml", "llms.txt",
    "api/v1/compare.js", "api/v1/evidence.js", "api/v1/search.js",
    "lib/evidence.js", "lib/evidence-config.json", "lib/issuer.js", "lib/issuer-registry.json",
    "machine/v1/openapi.json", "site-data/summaries.js", "deploy-metadata.json",
}


def fail(message: str) -> None:
    raise SystemExit(message)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("tree", type=Path)
    parser.add_argument("--max-mib", type=int, default=200)
    args = parser.parse_args()
    root = args.tree.resolve()
    if not root.is_dir():
        fail(f"deploy tree does not exist: {root}")

    files = [path for path in root.rglob("*") if path.is_file()]
    relative = {path.relative_to(root).as_posix() for path in files}
    missing = sorted(REQUIRED - relative)
    if missing:
        fail(f"deploy tree is missing required files: {', '.join(missing)}")

    forbidden = sorted(path for path in relative if path.split("/", 1)[0] in FORBIDDEN_ROOTS or
                       re.match(r"data-20\d{2}\.js$", path) or path == "disclosures.pdf")
    if forbidden:
        fail(f"deploy tree contains source evidence or build inputs: {', '.join(forbidden[:10])}")

    total = sum(path.stat().st_size for path in files)
    if total > args.max_mib * 1024 * 1024:
        fail(f"deploy tree is {total / 1024 / 1024:.1f} MiB; limit is {args.max_mib} MiB")
    oversized = [path.relative_to(root).as_posix() for path in files if path.stat().st_size > 100 * 1024 * 1024]
    if oversized:
        fail(f"deploy tree contains files over 100 MiB: {', '.join(oversized)}")

    metadata = json.loads((root / "deploy-metadata.json").read_text(encoding="utf-8"))
    origin = str(metadata.get("evidence_origin") or "").rstrip("/")
    if not origin.startswith("https://") or origin == "https://www.rokhanna.money":
        fail("deploy metadata must contain an external HTTPS evidence origin")
    runtime = json.loads((root / "lib/evidence-config.json").read_text(encoding="utf-8"))
    if runtime.get("evidence_origin") != origin:
        fail("runtime evidence origin does not match deploy metadata")
    vercel = json.loads((root / "vercel.json").read_text(encoding="utf-8"))
    if (vercel.get("git") or {}).get("deploymentEnabled", {}).get("main") is not False:
        fail("slim Vercel config must disable automatic deployments from main")

    page_details = list((root / "site-data").glob("*/pages/*.json"))
    if not page_details:
        fail("deploy tree has no page-detail data")
    for path in page_details:
        payload = json.loads(path.read_text(encoding="utf-8"))
        image = str(payload.get("image") or "")
        if not image.startswith(("docs/", "ocr/pages/")):
            fail(f"{path.relative_to(root)} has an unexpected evidence image path: {image}")

    summaries_text = (root / "site-data/summaries.js").read_text(encoding="utf-8")
    prefix = "window.FD_SUMMARIES = "
    if not summaries_text.startswith(prefix):
        fail("summary data has an invalid wrapper")
    summaries = json.loads(summaries_text[len(prefix):].rstrip().rstrip(";"))
    if any(item.get("evidence_origin") != origin for item in summaries.values()):
        fail("summary evidence origins do not match deploy metadata")
    if re.search(r'"source_pdf":"(?:docs/|ocr/|disclosures\.pdf)', summaries_text):
        fail("summary data still contains relative evidence URLs")
    local_evidence_url = re.compile(r"https://www\.rokhanna\.money/(?:docs/|ocr/pages/|disclosures\.pdf)")
    for path in files:
        if path.suffix.lower() not in {".html", ".js", ".json", ".md", ".txt"}:
            continue
        if local_evidence_url.search(path.read_text(encoding="utf-8", errors="ignore")):
            fail(f"{path.relative_to(root)} still points evidence at the primary site")
    print(f"deploy tree check: PASS ({len(files):,} files, {total / 1024 / 1024:.1f} MiB, evidence {origin})")


if __name__ == "__main__":
    main()
