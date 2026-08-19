#!/usr/bin/env python3
"""Assemble the small, generated tree consumed by the Vercel deploy branch."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import evidence_assets


ROOT = evidence_assets.ROOT
DIRECTORIES = [
    "api", "assets", "lib", "machine", "site-data", "stock-trades", "viewer",
    *[str(year) for year in range(2016, 2027)],
]
ROOT_FILES = [
    "264f47e7ac6f754571619ef2cfe0c4af.txt",
    "404.html",
    "DATA_LICENSE.md",
    "LICENSE",
    "index.html",
    "llms-full.txt",
    "llms.txt",
    "robots.txt",
    "sitemap.xml",
    "timeline-data.js",
    "vercel.json",
]


def source_commit(value: str | None) -> str:
    if value:
        return value
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def safe_output(path: Path) -> Path:
    resolved = path.resolve()
    allowed_roots = [(ROOT / "build").resolve(), Path(tempfile.gettempdir()).resolve()]
    if not any(resolved != allowed and resolved.is_relative_to(allowed) for allowed in allowed_roots):
        raise SystemExit(f"deploy output must be below {allowed_roots[0]} or {allowed_roots[1]}: {resolved}")
    return resolved


def copy_tree(output: Path) -> None:
    for name in DIRECTORIES:
        source = ROOT / name
        if not source.is_dir():
            raise SystemExit(f"required deploy directory is missing: {name}")
        shutil.copytree(source, output / name)
    for name in ROOT_FILES:
        source = ROOT / name
        if not source.is_file():
            raise SystemExit(f"required deploy file is missing: {name}")
        shutil.copy2(source, output / name)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--source-commit")
    parser.add_argument("--evidence-origin", default=evidence_assets.evidence_origin())
    args = parser.parse_args()

    output = safe_output(args.output)
    origin = args.evidence_origin.rstrip("/")
    if not origin.startswith("https://"):
        raise SystemExit("the slim deploy requires an HTTPS evidence origin")
    if origin == evidence_assets.SITE_ORIGIN:
        raise SystemExit("the slim deploy requires an external evidence origin; the primary site cannot host omitted scans")

    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    copy_tree(output)

    runtime_config = output / "lib" / "evidence-config.json"
    runtime_config.write_text(json.dumps({"evidence_origin": origin}, indent=2) + "\n", encoding="utf-8")
    vercel_path = output / "vercel.json"
    vercel_config = json.loads(vercel_path.read_text(encoding="utf-8"))
    vercel_config["git"] = {"deploymentEnabled": {"main": False}}
    vercel_path.write_text(json.dumps(vercel_config, indent=2) + "\n", encoding="utf-8")
    commit = source_commit(args.source_commit)
    metadata = {
        "schema_version": "1.0.0",
        "source_commit": commit,
        "evidence_origin": origin,
    }
    (output / "deploy-metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    total = sum(path.stat().st_size for path in output.rglob("*") if path.is_file())
    count = sum(1 for path in output.rglob("*") if path.is_file())
    print(f"deploy tree: {count:,} files, {total / 1024 / 1024:.1f} MiB, source {commit[:12]}")


if __name__ == "__main__":
    main()
