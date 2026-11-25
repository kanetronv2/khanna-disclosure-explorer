#!/usr/bin/env python3
"""Shared evidence-asset paths and public URL configuration."""

from __future__ import annotations

import hashlib
import json
import os
import re
from functools import lru_cache
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SITE_ORIGIN = "https://www.rokhanna.money"
CONFIG = ROOT / "lib" / "evidence-config.json"
SOURCE_REGISTRY = ROOT / "lib" / "source-registry.json"
MANIFEST = ROOT / "evidence-manifest.json"


def evidence_origin(configured: str | None = None) -> str:
    if configured is None:
        configured = os.environ.get("EVIDENCE_ORIGIN")
    if not configured and CONFIG.is_file():
        configured = json.loads(CONFIG.read_text(encoding="utf-8")).get("evidence_origin")
    origin = str(configured or SITE_ORIGIN).rstrip("/")
    repository = os.environ.get("GITHUB_REPOSITORY")
    source_commit = os.environ.get("GITHUB_SHA", "")
    # Query strings do not reliably invalidate jsDelivr's cached Git branch paths.
    if repository and re.fullmatch(r"[0-9a-f]{40}", source_commit):
        branch_origin = f"https://cdn.jsdelivr.net/gh/{repository}@main"
        if origin == branch_origin:
            return f"https://cdn.jsdelivr.net/gh/{repository}@{source_commit}"
    return origin


def public_url(path: str) -> str:
    value = str(path or "")
    if value.startswith(("http://", "https://")):
        return value
    return f"{evidence_origin()}/{value.lstrip('/')}"


@lru_cache(maxsize=1)
def source_registry() -> dict[str, dict]:
    if not SOURCE_REGISTRY.is_file():
        return {}
    return json.loads(SOURCE_REGISTRY.read_text(encoding="utf-8"))


def official_source(doc: str, primary_url: str | None = None) -> dict:
    registered = dict(source_registry().get(str(doc)) or {})
    if not registered and str(primary_url or "").startswith("https://disclosures-clerk.house.gov/"):
        registered["official_url"] = str(primary_url)
        filing_id = Path(str(primary_url)).stem
        if filing_id.isdigit():
            registered["filing_id"] = filing_id
    return registered


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@lru_cache(maxsize=1)
def manifest_files() -> dict[str, dict]:
    if not MANIFEST.is_file():
        return {}
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {item["path"]: item for item in payload.get("files") or []}


def version_token(relative_path: str) -> str | None:
    relative = str(relative_path).lstrip("/")
    local = ROOT / relative
    if local.is_file():
        return sha256(local)[:12]
    item = manifest_files().get(relative)
    return str(item.get("sha256") or "")[:12] or None if item else None


def source_files() -> list[Path]:
    paths = [ROOT / "disclosures.pdf"]
    paths.extend(ROOT.glob("docs/src/*.pdf"))
    paths.extend(ROOT.glob("docs/*/pages/*"))
    paths.extend(ROOT.glob("ocr/pages/*"))
    return sorted({path for path in paths if path.is_file()})
