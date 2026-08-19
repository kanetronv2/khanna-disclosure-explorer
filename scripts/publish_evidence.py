#!/usr/bin/env python3
"""Upload exactly the evidence manifest through an already-configured rclone remote."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import evidence_assets


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("remote", help="rclone destination, for example r2:rokhanna-evidence")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--transfers", type=int, default=16)
    args = parser.parse_args()

    rclone = shutil.which("rclone")
    if not rclone:
        raise SystemExit("rclone is required; configure an S3-compatible remote before publishing")
    manifest = json.loads(evidence_assets.MANIFEST.read_text(encoding="utf-8"))
    entries = manifest.get("files") or []
    for item in entries:
        path = evidence_assets.ROOT / item["path"]
        if not path.is_file() or path.stat().st_size != item["bytes"]:
            raise SystemExit(f"evidence file is missing or has changed: {item['path']}")
        if evidence_assets.sha256(path) != item["sha256"]:
            raise SystemExit(f"evidence checksum has changed: {item['path']}")

    with tempfile.NamedTemporaryFile("w", encoding="utf-8") as handle:
        handle.write("\n".join(item["path"] for item in entries) + "\n")
        handle.flush()
        common = ["--files-from", handle.name, "--checksum", "--transfers", str(args.transfers)]
        if args.check_only:
            command = [rclone, "check", str(evidence_assets.ROOT), args.remote, *common, "--download"]
        else:
            command = [
                rclone, "copy", str(evidence_assets.ROOT), args.remote, *common,
                "--metadata-set", f"cache-control={manifest['cache_control']}", "--progress",
            ]
            if args.dry_run:
                command.append("--dry-run")
        subprocess.run(command, check=True)
    print(f"evidence publish: {'checked' if args.check_only else 'uploaded'} {len(entries):,} manifest files")


if __name__ == "__main__":
    main()
