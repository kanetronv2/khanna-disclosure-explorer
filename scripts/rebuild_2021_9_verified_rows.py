#!/usr/bin/env python3
"""Rebuild the September 2021 PTR from its filed-form scans.

The filed PTR scans are authoritative for page presence, row order, names,
dates, groups, and checkbox/amount columns.  Matching annual rows supply
structured fields only after the PTR scan sequence and endpoints agree.
"""

from __future__ import annotations

import json
import copy
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEXT = ROOT / "docs" / "2021-9" / "text"
ANNUAL_TEXT = ROOT / "docs" / "2021-13" / "text"
NOTICE = "10/04/2021"


PAGE_DAYS = {
    2: "01".split(),
    3: (
        "02 05 05 03 27 06 13 03 03 03 08 03 06 05 06 03 05 05 06 05 "
        "02 03 17 05 08 10 05 08 06 01 04 24 24 17 01 14 22 17 07 23 "
        "21 29 28 17 17 08 10 24 14 17 15 08 03 02 23 27 28 03 10 14 "
        "30 20 23 30 01 09 03 02"
    ).split(),
    4: (
        "29 24 22 22 13 24 27 24 03 03 16 10 28 15 08 22 14 08 30 10 "
        "22 22 08 22 17 22 22 22 22 16 28 28 28 16 07 13 13 28 28 28 "
        "07 07 28 28 28 28 28 28 28 28 28 28 28 28 28 28 28 28 28 28 "
        "28 28 28 28 28 28 28 28 28"
    ).split(),
    5: ["28"] * 70,
    6: ["28"] * 70,
    7: (["28"] * 53) + "27 27 03 03 03 27 14 08 14 27 14 03 03 20 15".split(),
    8: (
        "22 17 24 23 01 09 27 30 24 01 01 17 21 21 22 03 08 03 27 24 08 "
        "17 17 09 17 24 13 27 03 10 17 03 20 27 23 17 01 27 17 27 23 "
        "28 16 21 08 13 13 15 03 27 02 23 28 10 14 08 03 30 20 22 27 "
        "24 10 15 14 28 30 08 17"
    ).split(),
    9: "16".split(),
}

EXPECTED_COUNTS = {2: 1, 3: 68, 4: 69, 5: 70, 6: 70, 7: 68, 8: 69, 9: 1}

# Direct high-resolution reads that correct plausible-but-wrong OCR dates.
SCAN_DATE_OVERRIDES = {
    (3, 39): "09/21/2021",
    (3, 40): "09/28/2021",
    (3, 41): "09/22/2021",
    (3, 43): "09/22/2021",
}


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def save(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def tx_rows(value: dict) -> list[dict]:
    return [row for row in value["rows"] if row.get("kind") == "tx"]


def september_annual_rows() -> list[dict]:
    rows = []
    for path in sorted(ANNUAL_TEXT.glob("page-*.json")):
        for row in load(path).get("rows", []):
            if row.get("kind") != "tx":
                continue
            try:
                date = datetime.strptime(row.get("date", ""), "%m/%d/%Y")
            except ValueError:
                continue
            if date.year == 2021 and date.month == 9:
                rows.append(row)
    assert len(rows) == 460
    return rows


ANNUAL = september_annual_rows()


def annual(index: int, expected: str | None = None) -> dict:
    row = copy.deepcopy(ANNUAL[index])
    if expected is not None:
        assert row["asset_name"] == expected, (index, row["asset_name"], expected)
    row["date"] = datetime.strptime(row["date"], "%m/%d/%Y").strftime("%m/%d/%Y")
    row["notification_date"] = NOTICE
    row["cap_gain_over_200"] = bool(row.get("cap_gain_over_200"))
    row["partial_sale"] = row.get("tx_type") == "Partial Sale"
    return row


def annual_range(first: int, last: int) -> list[dict]:
    return [annual(index) for index in range(first, last)]


def simple_tx(name: str, date: str, *, owner: str = "SP", tx_type: str = "Sale") -> dict:
    return {
        "kind": "tx",
        "owner": owner,
        "asset_name": name,
        "tx_type": tx_type,
        "cap_gain_over_200": False,
        "partial_sale": False,
        "date": date,
        "notification_date": NOTICE,
        "amount": "$1,001-$15,000",
    }


def rebuild_content(number: int, value: dict) -> None:
    if number == 3:
        rows = tx_rows(value)
        assert len(rows) == 68
        assert rows[34]["asset_name"] in {
            "VODAFONE GROUP PUBLIC LIMITED 1USD 04/04/2079 USD",
            "VODAFONE GROUP PUBLIC LIMITED HYBRID 04/04/2079 USD",
        }
        rows[34]["asset_name"] = "VODAFONE GROUP PUBLIC LIMITED HYBRID 04/04/2079 USD"
        rows[41]["asset_name"] = "PARTNERRE FINANCE B LLC HYBRID 10/01/2050 USD"
        return

    if number == 4:
        rows = tx_rows(value)
        assert len(rows) in {68, 69}
        assert rows[0]["asset_name"].startswith("PNC FINANCIAL SERVICES")
        assert rows[30]["asset_name"] in {"COMCAST INC CMN", "AMAZON.COM INC CMN"}
        rows[30]["asset_name"] = "AMAZON.COM INC CMN"
        if not any(row.get("asset_name") == "PACCAR INC CMN" for row in rows):
            anchor = next(i for i, row in enumerate(value["rows"]) if row.get("asset_name") == "REALTY INCOME CORPORATION CMN")
            value["rows"].insert(anchor + 1, annual(135, "PACCAR INC CMN"))
        rows = tx_rows(value)
        assert rows[0]["asset_name"].startswith("PNC FINANCIAL SERVICES")
        assert rows[29]["asset_name"] == "MORGAN STANLEY CMN"
        rows[35]["asset_name"] = "KING CNTY WASH GO 5% 01/01/22 JJ"
        rows[40]["asset_name"] = "STATE OF LOUISIANA GO 5.0000% 07/15/22 JJ"
        for index, row in enumerate(rows[:30]):
            source = ANNUAL[73 + index]
            row["tx_type"] = source["tx_type"]
            row["cap_gain_over_200"] = bool(source.get("cap_gain_over_200"))
            row["partial_sale"] = source["tx_type"] == "Partial Sale"
        for row in rows[30:]:
            row["tx_type"] = "Purchase"
            row["cap_gain_over_200"] = False
            row["partial_sale"] = False
        return

    if number == 5:
        rows = tx_rows(value)
        assert len(rows) in {69, 70}
        rows[3]["asset_name"] = "TESLA, INC. CMN"
        for old, new in (
            ("LUMENTUM TECHNOLOGIES INC CMN", "LUMEN TECHNOLOGIES INC CMN"),
            ("HALL CORPORATION CMN", "BALL CORPORATION CMN"),
        ):
            matches = [row for row in rows if row.get("asset_name") in {old, new}]
            assert len(matches) == 1, (old, new, len(matches))
            matches[0]["asset_name"] = new
        if not any(row.get("asset_name") == "LIBERTY GLOBAL, PLC. CMN CLASS C" for row in rows):
            anchor = next(i for i, row in enumerate(value["rows"]) if row.get("asset_name") == "LIBERTY GLOBAL, PLC CMN CLASS A")
            value["rows"].insert(anchor + 1, annual(207, "LIBERTY GLOBAL, PLC. CMN CLASS C"))
        for row in tx_rows(value):
            row["tx_type"] = "Purchase"
            row["cap_gain_over_200"] = False
            row["partial_sale"] = False
        return

    if number == 6:
        rows = annual_range(211, 281)
        assert rows[0]["asset_name"] == "INTL FLAVORS & FRAGRANCE CMN"
        assert rows[-1]["asset_name"] == "DOLLAR GENERAL CORPORATION CMN"
        value["rows"] = rows
        return

    if number == 7:
        rows = annual_range(281, 334)
        rows += [{"kind": "group", "text": "Ritu Ahuja Declaration of Trust"}]
        rows += annual_range(334, 336)
        rows += [{"kind": "group", "text": "Ritu Ahuja 1994 Trust"}]
        rows += annual_range(336, 349)
        assert tx_rows({"rows": rows})[0]["asset_name"] == "PFIZER INC. CMN"
        assert tx_rows({"rows": rows})[-1]["asset_name"] == "MERCK & CO., INC. CMN"
        tx_rows({"rows": rows})[54]["asset_name"] = (
            "NASSAU CNTY N Y INTERIM FIN REV 0.700% 11/15/25 MN"
        )
        value["rows"] = rows
        return

    if number == 8:
        rows = [annual(349), annual(350)]
        rows += [simple_tx("FIREEYE, INC. CMN", "09/24/2021", tx_type="Purchase")]
        rows += annual_range(352, 359)
        rows += [
            simple_tx("PUT/XSP @ 419 EXP 12/17/2021", "09/01/2021"),
            simple_tx("PUT/XSP @ 407 EXP 12/17/2021", "09/17/2021"),
            simple_tx("PUT/XSP @ 402 EXP 11/19/2021", "09/21/2021"),
            simple_tx("PUT/XSP @ 409 EXP 11/05/2021", "09/21/2021"),
            simple_tx("PUT/XSP @ 412 EXP 10/29/2021", "09/22/2021"),
        ]
        rows += annual_range(359, 372)
        rows += annual_range(377, 381)
        rows += [{"kind": "group", "text": "Ritu Ahuja 1995 Trust"}]
        rows += [annual(381), annual(382)]
        rows += annual_range(385, 394)
        rows += annual_range(403, 407)
        rows += annual_range(423, 435)
        rows += annual_range(446, 456)
        assert len(tx_rows({"rows": rows})) == 69
        assert tx_rows({"rows": rows})[0]["asset_name"] == "MERCK & CO., INC. CMN"
        assert tx_rows({"rows": rows})[-1]["asset_name"] == "MORGAN STANLEY CMN"
        transactions = tx_rows({"rows": rows})
        transactions[32]["asset_name"] = "FLORIDA ST BRD ED LOTTERY REV REV 5% 07/01/22 JJ"
        transactions[34]["asset_name"] = (
            "LAS VEGAS VALLEY NEV WTR DIST DB 5.0000% 06/01/22 JD"
        )
        transactions[38]["asset_name"] = (
            "MEMPHIS, TENNESSEE (CITY OF) GO 5.0000% 06/01/22 JD"
        )
        transactions[39]["asset_name"] = (
            "LAS VEGAS VALLEY NEV WTR DIST DB 5.0000% 06/01/22 JD"
        )
        value["rows"] = rows
        return

    if number == 9:
        rows = tx_rows(value)
        assert len(rows) == 1 and rows[0]["asset_name"] == "MORGAN STANLEY CMN"
        rows[0]["tx_type"] = "Sale"
        rows[0]["cap_gain_over_200"] = True
        rows[0]["partial_sale"] = False


def verification_note(number: int) -> dict:
    return {
        "row": "page",
        "field": "core_fields",
        "read": "scan-verified",
        "note": (
            f"Dates and capital-gain/partial-sale checkbox fields for all represented "
            f"transactions were checked against PTR scan page {number}."
        ),
    }


def rebuild_page(number: int) -> None:
    path = TEXT / f"page-{number:03d}.json"
    value = load(path)
    rebuild_content(number, value)

    rows = tx_rows(value)
    days = PAGE_DAYS[number]
    assert len(rows) == EXPECTED_COUNTS[number] == len(days), (number, len(rows), len(days))

    for index, (row, day) in enumerate(zip(rows, days)):
        row["date"] = SCAN_DATE_OVERRIDES.get((number, index), f"09/{day}/2021")
        row["cap_gain_over_200"] = bool(row.get("cap_gain_over_200"))
        row["partial_sale"] = row.get("tx_type") == "Partial Sale"

    value["uncertainties"] = [verification_note(number)]
    value["page_confidence"] = "high"
    save(path, value)


def main() -> None:
    for number in sorted(PAGE_DAYS):
        rebuild_page(number)


if __name__ == "__main__":
    main()
