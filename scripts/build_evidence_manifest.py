#!/usr/bin/env python3
"""Create the immutable upload manifest for source scans and filing PDFs."""

from __future__ import annotations

import argparse
import json
import mimetypes
from pathlib import Path

import evidence_assets


ROOT = evidence_assets.ROOT
OUTPUT = evidence_assets.MANIFEST
CACHE_CONTROL = "public, max-age=31536000, immutable"


def build() -> dict:
    files = []
    for path in evidence_assets.source_files():
        relative = path.relative_to(ROOT).as_posix()
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        files.append({
            "path": relative,
            "bytes": path.stat().st_size,
            "sha256": evidence_assets.sha256(path),
            "content_type": content_type,
            "cache_control": CACHE_CONTROL,
        })
    return {
        "schema_version": "1.0.0",
        "cache_control": CACHE_CONTROL,
        "file_count": len(files),
        "total_bytes": sum(item["bytes"] for item in files),
        "files": files,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail if the committed manifest differs")
    args = parser.parse_args()
    payload = build()
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.check:
        if not OUTPUT.is_file() or OUTPUT.read_text(encoding="utf-8") != rendered:
            raise SystemExit("evidence-manifest.json is stale; run make evidence-manifest")
    else:
        OUTPUT.write_text(rendered, encoding="utf-8")
    print(f"evidence manifest: {payload['file_count']:,} files, {payload['total_bytes'] / 1024 / 1024:.1f} MiB")


if __name__ == "__main__":
    main()
