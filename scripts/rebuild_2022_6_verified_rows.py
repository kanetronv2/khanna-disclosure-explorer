#!/usr/bin/env python3
"""Rebuild docs/2022-6 from its scan-verified transaction sequence.

The filed PTR scan controls row presence, page boundaries, order, trust
separators, owners, dates, notification dates, checkbox marks, and amounts.
Matching May 2022 Schedule B rows from docs/2022-15 supply clean asset names
and corroborate the structured fields after the scan sequence was aligned.
"""

from __future__ import annotations

import copy
import json
from collections import Counter
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PTR_TEXT = ROOT / "docs" / "2022-6" / "text"
ANNUAL_TEXT = ROOT / "docs" / "2022-15" / "text"
MAIN_NOTIFICATION = "06/02/2022"
ARECO_NOTIFICATION = "06/06/2022"

PAGE_TX_COUNTS = {
    **{page: 18 for page in range(2, 68)},
    2: 16,
    6: 17,
    7: 17,
    28: 17,
    62: 17,
    64: 17,
    65: 12,
    66: 17,
    67: 10,
}

GROUP_LABELS = {
    "mandr": "M&R Trust Partnership",
    "2010": "Monte and Usha Ahuja 2010 Irrev Trust FBO Grandchildren",
    "education": "Ahuja Grandchildren's Education Trust",
    "children": "Ahuja Khanna Children Irrevocable Trust",
    "ritu1994": "Ritu Ahuja 1994 Trust",
    "ritu1995": "Ritu Ahuja 1995 Trust",
    "areco_grandchildren": "ARECO Grandchildren Trust",
    "areco_children": "ARECO 2020 Trust FBO Khanna Children",
}

GROUP_TX_COUNTS = {
    GROUP_LABELS["mandr"]: 7,
    GROUP_LABELS["2010"]: 74,
    GROUP_LABELS["education"]: 9,
    GROUP_LABELS["children"]: 383,
    GROUP_LABELS["ritu1994"]: 612,
    GROUP_LABELS["ritu1995"]: 37,
    GROUP_LABELS["areco_grandchildren"]: 22,
    GROUP_LABELS["areco_children"]: 22,
}

GROUP_OWNERS = {
    GROUP_LABELS["mandr"]: "SP",
    GROUP_LABELS["2010"]: "DC",
    GROUP_LABELS["education"]: "DC",
    GROUP_LABELS["children"]: "DC",
    GROUP_LABELS["ritu1994"]: "SP",
    GROUP_LABELS["ritu1995"]: "SP",
    GROUP_LABELS["areco_grandchildren"]: "DC",
    GROUP_LABELS["areco_children"]: "DC",
}

AMOUNTS = {
    "$1,001-$15,000",
    "$15,001-$50,000",
    "$50,001-$100,000",
    "$100,001-$250,000",
}


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def normalized_date(value: str) -> str:
    return datetime.strptime(value, "%m/%d/%Y").strftime("%m/%d/%Y")


def normalized_tx(
    row: dict,
    *,
    notification: str = MAIN_NOTIFICATION,
    owner: str | None = None,
    force_date: str | None = None,
    force_cap_gain: bool | None = None,
) -> dict:
    result = copy.deepcopy(row)
    partial = result.get("tx_type") == "Partial Sale" or bool(
        result.get("partial_sale", False)
    )
    if result.get("tx_type") == "Partial Sale":
        result["tx_type"] = "Sale"
    result["partial_sale"] = partial
    result["date"] = force_date or normalized_date(result["date"])
    result["notification_date"] = notification
    if owner is not None:
        result["owner"] = owner
    if force_cap_gain is not None:
        result["cap_gain_over_200"] = force_cap_gain
    return result


def annual_group_rows(label: str, *, may_only: bool = True) -> list[tuple[tuple[int, int], dict]]:
    current_group: str | None = None
    result: list[tuple[tuple[int, int], dict]] = []
    for path in sorted(ANNUAL_TEXT.glob("page-*.json")):
        page = int(path.stem[-3:])
        for index, row in enumerate(load(path).get("rows", [])):
            if row.get("kind") == "group":
                current_group = row["text"]
                continue
            if row.get("kind") != "tx" or current_group != label:
                continue
            if may_only and int(row["date"].split("/")[0]) != 5:
                continue
            result.append(((page, index), row))
    return result


def mandr_rows() -> list[dict]:
    def tx(
        asset: str,
        tx_type: str,
        amount: str,
        *,
        cap: bool = False,
        partial: bool = False,
    ) -> dict:
        return {
            "kind": "tx",
            "owner": "SP",
            "asset_name": asset,
            "tx_type": tx_type,
            "cap_gain_over_200": cap,
            "partial_sale": partial,
            "date": "05/26/2022",
            "notification_date": "06/03/2022",
            "amount": amount,
        }

    return [
        tx("Visa Inc", "Sale", "$1,001-$15,000", cap=True, partial=True),
        tx("Estee Lauder Co", "Purchase", "$1,001-$15,000"),
        tx("ServiceNow Inc", "Purchase", "$1,001-$15,000"),
        tx("Amazon Inc", "Purchase", "$1,001-$15,000"),
        tx("CME Group", "Sale", "$1,001-$15,000", cap=True, partial=True),
        tx(
            "American Tower Corp",
            "Sale",
            "$15,001-$50,000",
            cap=True,
            partial=True,
        ),
        tx("ASML Holdings", "Purchase", "$1,001-$15,000"),
    ]


def main_group_sequences() -> tuple[list[dict], list[dict], list[dict], list[dict], list[dict]]:
    rows_2010 = annual_group_rows("2010 Grandchildren Trust")
    assert len(rows_2010) == 75
    # The capital call and Old Dominion row do not appear on this PTR. The
    # Fidelity sale is visibly printed twice on page 5, although the annual
    # Schedule B contains it once.
    selected_2010 = [item for index, item in enumerate(rows_2010) if index not in {0, 5}]
    fidelity = next(item for item in selected_2010 if item[0] == (140, 9))
    insert_at = next(
        index
        for index, (_, row) in enumerate(selected_2010)
        if row["asset_name"] == "SCHLUMBERGER LTD CMN"
    )
    selected_2010.insert(insert_at, fidelity)
    seq_2010 = [normalized_tx(row, owner="DC") for _, row in selected_2010]
    assert len(seq_2010) == 74

    education = annual_group_rows("Ahuja Grandchildren's Education Trust")
    children = annual_group_rows("2020 Trust FBO Khanna Children")
    ritu_1995 = annual_group_rows("Ritu Ahuja 1995 Trust")
    assert (len(education), len(children), len(ritu_1995)) == (9, 383, 37)

    seq_education = [normalized_tx(row, owner="DC") for _, row in education]
    seq_children = [normalized_tx(row, owner="DC") for _, row in children]
    seq_ritu_1995 = [normalized_tx(row, owner="SP") for _, row in ritu_1995]

    ritu = annual_group_rows("Ritu Ahuja 1994 Trust")
    assert len(ritu) == 606

    # The PTR moves Citigroup from the later option block to page 32.
    citigroup = ritu.pop(338)
    assert citigroup[1]["asset_name"] == "CITIGROUP INC. CMN"
    ritu.insert(75, citigroup)

    # Five XSP sales appear immediately after the three XSP purchases on the
    # PTR, rather than in their later annual Schedule B position.
    moved_options: list[tuple[tuple[int, int], dict]] = []
    for source in [(326, 1), (326, 2), (326, 3), (326, 4), (326, 5)]:
        index = next(index for index, item in enumerate(ritu) if item[0] == source)
        moved_options.append(ritu.pop(index))
    option_insert = next(index for index, item in enumerate(ritu) if item[0] == (279, 0)) + 1
    ritu[option_insert:option_insert] = moved_options

    # These six scan rows were later represented in the annual filing with
    # June dates. Their May dates and checkbox/amount marks below are read
    # directly from the PTR scan.
    extras = [
        ((278, 11), (278, 12), "PEGASYSTEMS INC. CMN", "Purchase", False, "05/05/2022", "$1,001-$15,000"),
        ((306, 10), (306, 11), "TRANSUNION CMN", "Sale", False, "05/23/2022", "$15,001-$50,000"),
        ((306, 17), (306, 18), "PACCAR INC CMN", "Sale", True, "05/23/2022", "$15,001-$50,000"),
        ((306, 21), (306, 22), "FORTINET, INC. CMN", "Sale", False, "05/05/2022", "$15,001-$50,000"),
        ((307, 6), (307, 7), "MATCH GROUP, INC. CMN", "Sale", False, "05/05/2022", "$15,001-$50,000"),
        ((307, 18), (326, 6), "AUTODESK, INC. CMN", "Sale", False, "05/05/2022", "$15,001-$50,000"),
    ]
    annual_all = dict(annual_group_rows("Ritu Ahuja 1994 Trust", may_only=False))
    for sequence, (source, anchor, name, tx_type, cap, tx_date, amount) in enumerate(extras):
        annual_row = annual_all[source]
        assert annual_row["asset_name"] == name
        manual = {
            "kind": "tx",
            "owner": "SP",
            "asset_name": name,
            "tx_type": tx_type,
            "cap_gain_over_200": cap,
            "partial_sale": False,
            "date": tx_date,
            "notification_date": MAIN_NOTIFICATION,
            "amount": amount,
        }
        # Insert immediately before the next May row seen on the scan.
        index = next(index for index, item in enumerate(ritu) if item[0] == anchor)
        ritu.insert(index, ((-1, sequence), manual))

    seq_ritu = [
        row if source[0] == -1 else normalized_tx(row, owner="SP")
        for source, row in ritu
    ]
    assert len(seq_ritu) == 612
    return seq_2010, seq_education, seq_children, seq_ritu, seq_ritu_1995


def areco_sequences() -> tuple[list[dict], list[dict]]:
    first_sources = [(108, index) for index in range(19, 26)] + [
        (109, index) for index in range(0, 15)
    ]
    second_sources = [(110, index) for index in range(1, 23)]

    def source_rows(sources: list[tuple[int, int]]) -> list[dict]:
        result = []
        for page, index in sources:
            row = load(ANNUAL_TEXT / f"page-{page:03d}.json")["rows"][index]
            assert row["kind"] == "tx"
            result.append(
                normalized_tx(
                    row,
                    notification=ARECO_NOTIFICATION,
                    owner="DC",
                    force_date="05/05/2022",
                    force_cap_gain=True,
                )
            )
        return list(reversed(result))

    first = source_rows(first_sources)
    second = source_rows(second_sources)
    assert len(first) == len(second) == 22
    return first, second


def group(label: str) -> dict:
    return {"kind": "group", "text": GROUP_LABELS[label]}


def rebuilt_pages() -> dict[int, list[dict]]:
    seq_2010, education, children, ritu, ritu_1995 = main_group_sequences()
    areco_grandchildren, areco_children = areco_sequences()
    mandr = mandr_rows()

    pages: dict[int, list[dict]] = {
        2: [group("mandr"), *mandr, group("2010"), *seq_2010[:9]],
        3: seq_2010[9:27],
        4: seq_2010[27:45],
        5: seq_2010[45:63],
        6: [*seq_2010[63:], group("education"), *education[:6]],
        7: [*education[6:], group("children"), *children[:14]],
        28: [*children[374:], group("ritu1994"), *ritu[:8]],
        62: [*ritu[602:], group("ritu1995"), *ritu_1995[:7]],
        63: ritu_1995[7:25],
        64: [
            *ritu_1995[25:],
            group("areco_grandchildren"),
            *areco_grandchildren[:5],
        ],
        65: areco_grandchildren[5:17],
        66: [
            *areco_grandchildren[17:],
            group("areco_children"),
            *areco_children[:12],
        ],
        67: areco_children[12:],
    }

    offset = 14
    for page in range(8, 28):
        pages[page] = children[offset : offset + 18]
        offset += 18
    assert offset == 374

    offset = 8
    for page in range(29, 62):
        pages[page] = ritu[offset : offset + 18]
        offset += 18
    assert offset == 602

    assert set(pages) == set(range(2, 68))
    for page, rows in pages.items():
        tx_count = sum(row["kind"] == "tx" for row in rows)
        assert tx_count == PAGE_TX_COUNTS[page], (page, tx_count)
        expected_objects = 18 if page not in {65, 67} else PAGE_TX_COUNTS[page]
        assert len(rows) == expected_objects, (page, len(rows))
    return pages


def write_page(page: int, rows: list[dict]) -> None:
    path = PTR_TEXT / f"page-{page:03d}.json"
    data = load(path)
    tx_count = sum(row["kind"] == "tx" for row in rows)
    data["rows"] = rows
    data["free_text"] = None
    data["uncertainties"] = [
        f"All {tx_count} printed transaction rows and any trust separator on this page "
        "were re-verified against the filed PTR scan. Matching 2022 annual Schedule B "
        "rows corroborate clean asset names and structured fields; the PTR controls "
        "presence, order, owner, dates, notification dates, checkbox marks, and amounts."
    ]
    data["page_confidence"] = "high"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def validate_pages(pages: dict[int, list[dict]]) -> None:
    group_counts: Counter[str] = Counter()
    group_order: list[str] = []
    current_group: str | None = None
    required = ("owner", "asset_name", "tx_type", "date", "notification_date", "amount")

    for page in range(2, 68):
        for index, row in enumerate(pages[page]):
            if row.get("kind") == "group":
                current_group = row["text"]
                group_order.append(current_group)
                continue
            assert row.get("kind") == "tx", (page, index, row.get("kind"))
            assert current_group is not None, (page, index, "transaction before group")
            assert all(row.get(field) for field in required), (page, index, row)
            assert all("[" not in str(row[field]) for field in required), (page, index, row)
            assert row["owner"] == GROUP_OWNERS[current_group], (page, index, row)
            assert row["tx_type"] in {"Purchase", "Sale"}, (page, index, row)
            assert type(row.get("cap_gain_over_200")) is bool, (page, index, row)
            assert type(row.get("partial_sale")) is bool, (page, index, row)
            assert row["amount"] in AMOUNTS, (page, index, row)
            if row["partial_sale"] or row["cap_gain_over_200"]:
                assert row["tx_type"] == "Sale", (page, index, row)
            tx_date = datetime.strptime(row["date"], "%m/%d/%Y")
            notification = datetime.strptime(row["notification_date"], "%m/%d/%Y")
            assert tx_date <= notification, (page, index, row)
            group_counts[current_group] += 1

    assert group_order == list(GROUP_TX_COUNTS), group_order
    assert group_counts == Counter(GROUP_TX_COUNTS), group_counts


def main() -> None:
    pages = rebuilt_pages()
    validate_pages(pages)
    for page in range(2, 68):
        write_page(page, pages[page])

    tx_count = sum(
        row["kind"] == "tx" for rows in pages.values() for row in rows
    )
    group_count = sum(
        row["kind"] == "group" for rows in pages.values() for row in rows
    )
    assert (tx_count, group_count) == (1166, 8)
    print(f"rebuilt docs/2022-6: {tx_count} transactions, {group_count} groups")


if __name__ == "__main__":
    main()
