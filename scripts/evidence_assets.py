#!/usr/bin/env python3
"""Shared evidence-asset paths and public URL configuration."""

from __future__ import annotations

import hashlib
import json
import os
from functools import lru_cache
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SITE_ORIGIN = "https://www.rokhanna.money"
CONFIG = ROOT / "lib" / "evidence-config.json"
MANIFEST = ROOT / "evidence-manifest.json"


def evidence_origin() -> str:
    configured = os.environ.get("EVIDENCE_ORIGIN")
    if not configured and CONFIG.is_file():
        configured = json.loads(CONFIG.read_text(encoding="utf-8")).get("evidence_origin")
    return str(configured or SITE_ORIGIN).rstrip("/")


def public_url(path: str) -> str:
    value = str(path or "")
    if value.startswith(("http://", "https://")):
        return value
    return f"{evidence_origin()}/{value.lstrip('/')}"


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
