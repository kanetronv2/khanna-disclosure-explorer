#!/usr/bin/env python3
"""Complete scan-verified checkbox fields on selected 2020 PTR forms.

Indexes are zero-based within the transaction rows on each scan page.  The
first list contains checked ``Capital Gain over $200`` boxes and the second
contains checked ``Partial Sale``/``Partial Transaction`` boxes.  All other
boxes in those columns were visually verified as unchecked.
"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

# doc: page: (transaction count, cap-gain checked indexes, partial checked indexes)
PAGES = {
    "2020-5": {
        2: (66, [15, 16, 17, 19, 20], [15, 16, 17, 19, 20, 22]),
        3: (71, [], [67, 68, 69, 70]),
        4: (71, [0, 3, 4, 5, 7, 8, 9, 10, 13, 16, 18, 19, 20, 24, 25, 26, 27, 28, 29, 30, 32, 33, 37, 38, 40, 52, 59, 63, 65], [0, 1, 2, 3, 5, 6, 7, 8, 9, 10, 11, 13, 18, 19, 20, 22, 23, 26, 28, 29, 31, 32, 33, 34, 37, 38, 40, 45, 47, 53, 54, 58, 60, 64, 65, 66, 67]),
        5: (71, [2, 6, 8, 13, 14, 22, 23, 34, 35, 38, 39, 63, 70], [1, 2, 3, 6, 8, 9, 14, 15, 17, 22, 23, 38, 43, 45, 48, 58, 63]),
        6: (70, [3, 8, 10, 24, 27], [0, 8, 22, 27, 28]),
        7: (71, [], []),
        8: (71, [9, 21, 24, 33, 36, 37, 44, 51, 52], [0, 4, 5, 6, 12, 14, 15, 16, 18, 19, 22, 23, 25, 35, 36, 37, 38, 39, 42, 46, 48, 60, 63, 64, 70]),
        9: (1, [], []),
    },
    "2020-6": {
        2: (50, [23], [23, 25, 27]), 3: (43, [], []), 4: (2, [1], [1]),
        5: (62, [6, 7, 8, 9, 10, 11, 12], [6, 7, 8, 9, 10, 11, 12, 13]),
        6: (66, [], [59, 60, 62, 63]),
        7: (66, [1, 9, 10, 11, 17, 18, 19, 20, 21, 28, 29, 38, 39, 43, 55, 57, 64], [0, 1, 4, 5, 7, 9, 11, 12, 14, 17, 18, 19, 20, 21, 24, 28, 29, 30, 32, 34, 35, 38, 39, 43, 45, 47, 48, 52, 53, 56, 57, 59, 61, 62, 63, 65]),
        8: (65, [2, 36, 42, 48], [2, 3, 4, 10, 15, 17, 19, 23, 25, 29, 30, 32, 34, 38, 41, 42, 43, 49, 51, 52]),
        9: (66, [], [64]),
        10: (66, [16, 21], [6, 10, 12, 14, 15, 16, 18, 19, 20, 22, 24, 34, 37, 38, 39, 44, 45, 47, 51, 53, 56, 57, 60, 61, 64]),
        11: (10, [3], [1]), 12: (4, [0, 1, 2, 3], []),
    },
    "2020-8": {
        2: (3, [0, 1, 2], [0, 1, 2]), 3: (3, [0, 1, 2], [0, 1, 2]),
        4: (61, [4, 5, 6, 7, 10, 11, 12, 15, 16, 19, 20, 21], [9, 11, 23, 24, 25]),
        5: (65, [45, 46, 47, 48, 49, 50, 53, 54, 58, 59, 60, 62, 63, 64], [45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 57, 58, 60, 61, 62, 63, 64]),
        6: (64, [0, 3, 7, 9, 15, 16, 17, 30, 32], [0, 1, 2, 3, 4, 5, 6, 8, 9, 10, 13, 15, 16, 17, 18, 19, 23, 24, 25, 30, 31, 32, 33, 40, 45, 47]),
        7: (65, [38, 39, 40, 41, 42, 46, 48, 54], [46, 47, 48, 49, 51, 52, 53, 56, 57, 59, 62]),
        8: (12, [], [0, 1, 7, 9, 11]),
    },
    "2020-9": {
        2: (2, [], []), 3: (1, [], []),
        4: (60, [9, 10, 39, 42, 44, 45, 51], [9, 10, 11, 12, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51]),
        5: (19, [], [11, 12, 13, 14, 16, 17, 18]), 6: (1, [], []),
    },
    "2020-11": {
        2: (8, [1, 3, 4], [4]),
        3: (13, [2, 3, 6, 7, 8, 9], [8, 9]),
        4: (55, [44, 49, 50], [15, 16, 17, 18, 40, 41, 42]),
        5: (1, [], []),
    },
    "2020-12": {
        2: (3, [0], [0]), 3: (7, [2, 3], [0, 3]),
        4: (61, [1, 2, 3], [1, 2, 3, 4, 5, 6]),
        5: (65, [27, 28, 36, 37, 38, 41, 43, 44, 46, 47, 48, 50, 57, 61, 63, 64], [27, 28, 32, 33, 37, 39, 42, 43, 44, 45, 47, 48, 49, 50, 51, 56, 57, 60, 62]),
        6: (64, [1, 2, 56, 57, 61], [1, 2, 3, 11, 57, 58, 59, 60, 62, 63]),
        7: (22, [1, 15], [4, 5, 10, 11, 12, 16, 19, 21]), 8: (2, [], []),
    },
    "2020-13": {
        2: (2, [], []),
        3: (61, [4, 5, 6, 7, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 38, 39, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 56, 58, 59], [5, 6, 7, 8, 24, 25, 29, 30, 35, 41, 42, 46, 51, 53, 54, 55, 60]),
        4: (64, [0, 1, 6, 10, 13, 34, 35, 36, 37, 38, 39, 40, 42, 43, 44, 46, 47, 50, 52, 56, 57, 59, 62, 63], [2, 8, 14, 45, 53, 60]),
        5: (9, [0, 3, 8], [1, 4, 5, 6, 7]),
    },
}


def transaction_rows(data: dict) -> list[dict]:
    return [row for row in data.get("rows", []) if row.get("kind") == "tx"]


def main() -> None:
    for doc, pages in PAGES.items():
        expected_pages = set(pages)
        actual_pages = set()
        total = cap_total = partial_total = groups = 0
        for path in sorted((ROOT / "docs" / doc / "text").glob("page-*.json")):
            data = json.loads(path.read_text())
            txs = transaction_rows(data)
            groups += sum(row.get("kind") == "group" for row in data.get("rows", []))
            if not txs:
                continue
            page = int(path.stem.split("-")[1])
            actual_pages.add(page)
            if page not in pages:
                raise AssertionError(f"unmapped transaction page: {doc} page {page}")
            expected_count, cap_indexes, partial_indexes = pages[page]
            if len(txs) != expected_count:
                raise AssertionError(
                    f"{doc} page {page}: expected {expected_count} transactions, found {len(txs)}"
                )
            cap_set, partial_set = set(cap_indexes), set(partial_indexes)
            if not cap_set | partial_set <= set(range(expected_count)):
                raise AssertionError(f"{doc} page {page}: checkbox index out of range")
            for index, row in enumerate(txs):
                row["cap_gain_over_200"] = index in cap_set
                row["partial_sale"] = index in partial_set
                row.pop("partial", None)
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
            total += expected_count
            cap_total += len(cap_set)
            partial_total += len(partial_set)
        if actual_pages != expected_pages:
            raise AssertionError(
                f"{doc}: mapped pages {sorted(expected_pages)}, found {sorted(actual_pages)}"
            )
        print(
            f"{doc}: transactions={total} groups={groups} "
            f"cap_gain_true={cap_total} partial_sale_true={partial_total}"
        )

    # Scan-specific invariants that must not be normalized away.
    page = json.loads((ROOT / "docs/2020-8/text/page-007.json").read_text())
    txs = transaction_rows(page)
    for index in range(38, 43):
        assert txs[index]["tx_type"] == "Purchase" and txs[index]["cap_gain_over_200"]

    page = json.loads((ROOT / "docs/2020-6/text/page-009.json").read_text())
    txs = transaction_rows(page)
    assert txs[64]["tx_type"] == "Purchase" and txs[64]["partial_sale"]

    page = json.loads((ROOT / "docs/2020-11/text/page-003.json").read_text())
    txs = transaction_rows(page)
    assert txs[9]["asset_name"] == "SNAP INC. CL A"
    assert txs[9]["amount"] == "[UNKNOWN]" and txs[9]["partial_sale"]


if __name__ == "__main__":
    main()
