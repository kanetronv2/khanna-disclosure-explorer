#!/usr/bin/env python3
"""Complete scan-backed checkbox fields in seven 2021-2022 PTRs.

The older transcriptions represented a marked Partial Transaction checkbox as
either ``tx_type == "Partial Sale"`` or the legacy ``partial_transaction``
boolean.  This script preserves all explicit modern boolean values, fills
fields that are absent, and removes legacy partial keys after translating
their value.  The 2021-7 capital-gain map is transcribed directly from its four
PTR table scans; the two missing 2021-8 capital-gain values are unmarked
purchase rows on page 2.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ("2021-4", "2021-5", "2021-7", "2021-8", "2021-11", "2022-4", "2022-9")
EXPECTED = {
    "2021-4": {"tx": 123, "cap_true": 9, "partial_true": 8},
    "2021-5": {"tx": 35, "cap_true": 8, "partial_true": 7},
    "2021-7": {"tx": 178, "cap_true": 56, "partial_true": 4},
    "2021-8": {"tx": 1392, "cap_true": 223, "partial_true": 101},
    "2021-11": {"tx": 554, "cap_true": 58, "partial_true": 62},
    "2022-4": {"tx": 539, "cap_true": 62, "partial_true": 111},
    "2022-9": {"tx": 366, "cap_true": 22, "partial_true": 74},
}

# On pages 2-3, the M&R Trust sale rows have the capital-gain box marked,
# except for these three page-2 rows.  On pages 4-5, only the Pfizer partial
# sale has the capital-gain box marked; all purchases and the other nine sales
# are unmarked.
CAP_FALSE_2021_7_PAGE_2 = {
    5: "Cimpress Inc.",
    40: "Bright Horizons Family Solutions",
    46: "Cannae Holdings",
}
CAP_TRUE_2021_7_OTHER = {("page-004.json", 54): "PFIZER INC. CMN"}
EXPECTED_PAGE_TX_2021_7 = {
    "page-002.json": 53,
    "page-003.json": 5,
    "page-004.json": 62,
    "page-005.json": 58,
}


def insert_checkbox_fields(row: dict, cap: bool | None, partial: bool | None) -> dict:
    """Insert absent checkbox fields near tx_type/cap without reordering others."""
    need_cap = "cap_gain_over_200" not in row and cap is not None
    need_partial = "partial_sale" not in row and partial is not None
    if not need_cap and not need_partial:
        return row

    rebuilt: dict = {}
    for key, value in row.items():
        rebuilt[key] = value
        if key == "tx_type" and need_cap:
            rebuilt["cap_gain_over_200"] = cap
            need_cap = False
            if need_partial:
                rebuilt["partial_sale"] = partial
                need_partial = False
        elif key == "cap_gain_over_200" and need_partial:
            rebuilt["partial_sale"] = partial
            need_partial = False
    if need_cap:
        rebuilt["cap_gain_over_200"] = cap
    if need_partial:
        rebuilt["partial_sale"] = partial
    return rebuilt


def partial_value(row: dict) -> bool:
    """Translate already-transcribed old-form partial-sale evidence."""
    return bool(row.get("partial_transaction")) or row.get("tx_type") == "Partial Sale"


def serialize_page(doc: str, data: dict) -> str:
    """Retain the compact row-object style used by the original 2021-7 pages."""
    if doc != "2021-7":
        return json.dumps(data, indent=2, ensure_ascii=False) + "\n"

    lines = ["{"]
    items = list(data.items())
    for position, (key, value) in enumerate(items):
        comma = "," if position + 1 < len(items) else ""
        encoded_key = json.dumps(key, ensure_ascii=False)
        if isinstance(value, list):
            lines.append(f"  {encoded_key}: [")
            for item_position, item in enumerate(value):
                item_comma = "," if item_position + 1 < len(value) else ""
                encoded_item = json.dumps(item, ensure_ascii=False)
                lines.append(f"    {encoded_item}{item_comma}")
            lines.append(f"  ]{comma}")
        else:
            encoded_value = json.dumps(value, ensure_ascii=False)
            lines.append(f"  {encoded_key}: {encoded_value}{comma}")
    lines.append("}")
    return "\n".join(lines) + "\n"


def cap_value_2021_7(page_name: str, row_index: int, row: dict) -> bool:
    if page_name == "page-002.json":
        expected_asset = CAP_FALSE_2021_7_PAGE_2.get(row_index)
        if expected_asset is not None:
            assert row.get("asset_name") == expected_asset, (page_name, row_index, row)
            return False
        return True
    if page_name == "page-003.json":
        return True
    expected_asset = CAP_TRUE_2021_7_OTHER.get((page_name, row_index))
    if expected_asset is not None:
        assert row.get("asset_name") == expected_asset, (page_name, row_index, row)
        return True
    return False


def complete_document(doc: str) -> tuple[int, int]:
    changed_pages = 0
    changed_rows = 0
    text_dir = ROOT / "docs" / doc / "text"

    for path in sorted(text_dir.glob("page-*.json")):
        source_text = path.read_text()
        data = json.loads(source_text)
        if doc == "2021-7" and path.name in EXPECTED_PAGE_TX_2021_7:
            actual = sum(row.get("kind") == "tx" for row in data.get("rows", []))
            assert actual == EXPECTED_PAGE_TX_2021_7[path.name], (path, actual)

        page_changed = False
        rows = []
        for row_index, row in enumerate(data.get("rows", [])):
            if row.get("kind") != "tx":
                rows.append(row)
                continue

            cap: bool | None = None
            if "cap_gain_over_200" not in row:
                if doc == "2021-7":
                    cap = cap_value_2021_7(path.name, row_index, row)
                elif doc == "2021-8":
                    # The only absent values are the two unmarked purchase rows
                    # on scan page 2 (Match Group and Illumina).
                    assert path.name == "page-002.json"
                    assert row.get("asset_name") in {"Match Group Inc.", "Illumina Inc."}
                    assert row.get("tx_type") == "Purchase"
                    cap = False
                else:
                    raise AssertionError(f"unexpected missing cap field: {doc} {path.name} {row_index}")

            partial = partial_value(row) if "partial_sale" not in row else None
            original = row
            rebuilt = insert_checkbox_fields(row, cap, partial)
            if "partial" in rebuilt or "partial_transaction" in rebuilt:
                rebuilt = dict(rebuilt)
                rebuilt.pop("partial", None)
                rebuilt.pop("partial_transaction", None)
            if rebuilt != original:
                page_changed = True
                changed_rows += 1
            rows.append(rebuilt)

        # The first version of this repair script expanded the already-compact
        # 2021-7 row objects.  Normalize those pages back to their repository
        # style while preserving the added fields and any concurrent name fix.
        if doc == "2021-7" and '"rows": [\n    {\n' in source_text:
            page_changed = True
        if page_changed:
            data["rows"] = rows
            path.write_text(serialize_page(doc, data))
            changed_pages += 1

    return changed_pages, changed_rows


def validate(doc: str) -> dict[str, int]:
    rows = []
    for path in sorted((ROOT / "docs" / doc / "text").glob("page-*.json")):
        rows.extend(
            row
            for row in json.loads(path.read_text()).get("rows", [])
            if row.get("kind") == "tx"
        )

    assert all(type(row.get("cap_gain_over_200")) is bool for row in rows)
    assert all(type(row.get("partial_sale")) is bool for row in rows)
    counts = {
        "tx": len(rows),
        "cap_true": sum(row["cap_gain_over_200"] for row in rows),
        "partial_true": sum(row["partial_sale"] for row in rows),
    }
    assert counts == EXPECTED[doc], (doc, counts, EXPECTED[doc])
    return counts


def main() -> None:
    for doc in DOCS:
        changed_pages, changed_rows = complete_document(doc)
        counts = validate(doc)
        print(
            f"{doc}: {counts['tx']} tx; cap true {counts['cap_true']}; "
            f"partial true {counts['partial_true']}; changed {changed_rows} rows "
            f"on {changed_pages} pages"
        )


if __name__ == "__main__":
    main()
