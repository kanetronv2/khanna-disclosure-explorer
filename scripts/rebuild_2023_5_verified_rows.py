#!/usr/bin/env python3
"""Rebuild scan-verified rows in the May 2023 PTR (docs/2023-5).

The PTR scans are authoritative for row presence, order, names, and dates.
Matching 2023 annual Schedule B rows supply structured checkbox/amount fields
only where the scan sequence and endpoints agree.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PTR_TEXT = ROOT / "docs" / "2023-5" / "text"
ANNUAL_TEXT = ROOT / "docs" / "2023-14" / "text"
NOTIFICATION_DATE = "6/2/2023"


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def save(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def annual_row(page: int, row: int, expected: str | None = None) -> dict:
    value = load(ANNUAL_TEXT / f"page-{page:03d}.json")["rows"][row - 1]
    assert value["kind"] == "tx", (page, row, value)
    if expected is not None:
        assert value["asset_name"] == expected, (page, row, value["asset_name"], expected)
    result = copy.deepcopy(value)
    result["notification_date"] = NOTIFICATION_DATE
    result["partial_sale"] = result.get("tx_type") == "Partial Sale"
    return result


def annual_range(page: int, first: int, last: int) -> list[dict]:
    return [annual_row(page, row) for row in range(first, last + 1)]


def page(number: int) -> tuple[Path, dict]:
    path = PTR_TEXT / f"page-{number:03d}.json"
    return path, load(path)


def verified(value: dict, note: str) -> None:
    value["uncertainties"] = [
        {
            "row": "page",
            "field": "verification",
            "read": "scan-verified",
            "note": note,
        }
    ]
    value["page_confidence"] = "high"


def tx_rows(value: dict) -> list[dict]:
    return [row for row in value["rows"] if row.get("kind") == "tx"]


def set_asset(rows: list[dict], old: str, new: str, occurrence: int = 1) -> None:
    matches = [row for row in rows if row.get("asset_name") == old]
    assert len(matches) >= occurrence, (old, occurrence, len(matches))
    matches[occurrence - 1]["asset_name"] = new


def rebuild_page_3() -> None:
    path, value = page(3)
    rows = tx_rows(value)
    assert len(rows) == 25
    assert rows[0]["asset_name"] == "SOCIETE GENERALE LINKED TO S&P 500 INDEX"
    assert rows[-1]["asset_name"] == "PROCTER & GAMBLE COMPANY (THE) CMN"
    rows[2]["asset_name"] = "CAPPED BUFFERED ENHANCED PARTICIPATION LINKED TO S&P 500 INDEX"
    rows[12]["asset_name"] = "CAPPED BUFFERED ENHANCED PARTICIPATION LINKED TO BASKET OF INDICES"
    rows[15]["amount"] = "$1,001-$15,000"
    rows[20]["asset_name"] = "CAPPED BUFFERED ENHANCED PARTICIPATION LINKED TO S&P 500 INDEX"
    assert rows[11]["date"] == "5/2/2023"  # Printed PTR date; annual has 5/22.
    verified(
        value,
        "All 25 transactions and amount/type columns checked against PTR scan page 3; scan date 05/02/23 retained for row 12.",
    )
    save(path, value)


def rebuild_page_6() -> None:
    path, value = page(6)
    before_group = tx_rows(value)[:5]
    assert [row["asset_name"] for row in before_group] == [
        "ALPHABET INC. CMN CLASS C",
        "AMAZON.COM INC CMN",
        "URBAN OUTFITTERS INC CMN",
        "ABBOTT LABORATORIES CMN",
        "URBAN OUTFITTERS INC CMN",
    ]
    after_group = annual_range(189, 10, 26) + annual_range(190, 1, 4)
    assert len(after_group) == 21
    assert after_group[0]["asset_name"] == "CITIGROUP INC. LINKED TO S&P 500 INDEX"
    assert after_group[-1]["asset_name"] == "CHARLES SCHWAB CORPORATION CMN"
    for row in after_group:
        if row["asset_name"] == "CAPPED BUFFERED ENHANCED PARTICIPATION LIN":
            row["asset_name"] = "CAPPED BUFFERED ENHANCED PARTICIPATION LINKED TO S&P 500 INDEX"
    value["rows"] = before_group + [
        {"kind": "group", "text": "Ahuja Khanna Children Irrevocable Trust"}
    ] + after_group
    assert len(tx_rows(value)) == 26
    verified(
        value,
        "All 26 transactions and the trust separator checked against PTR scan page 6; matching annual Schedule B pp. 189-190 supplies checkbox fields.",
    )
    save(path, value)


def insert_page_10_citigroup() -> None:
    path, value = page(10)
    rows = tx_rows(value)
    if len(rows) == 26:
        assert rows[6]["asset_name"] == "PAYCOM SOFTWARE, INC. CMN"
        assert rows[7]["asset_name"] == "FOX CORP 3.5% 04/08/2030 USD"
        missing = annual_row(193, 15, "CITIGROUP INC. HYBRID 03/20/2030 USD")
        value["rows"].insert(7, missing)
    else:
        assert len(rows) == 27
        assert rows[7]["asset_name"] == "CITIGROUP INC. HYBRID 03/20/2030 USD"
    assert len(tx_rows(value)) == 27
    verified(
        value,
        "All 27 transactions checked against PTR scan page 10; omitted Citigroup hybrid row restored between Paycom and Fox Corp.",
    )
    save(path, value)


def repair_flagged_pages() -> None:
    # Pages 8 and 9 were structurally correct; high-resolution scans establish
    # the previously uncertain names, dates, checkboxes, and amount column A.
    for number, count, first, last in (
        (8, 27, "METTLER-TOLEDO INTL CMN", "EQUIFAX INC. CMN"),
        (9, 27, "INTL. FLAVORS & FRAGRANCE CMN", "DISCOVER FINANCIAL SERVICES CMN"),
    ):
        path, value = page(number)
        rows = tx_rows(value)
        assert len(rows) == count and rows[0]["asset_name"] == first and rows[-1]["asset_name"] == last
        verified(value, f"All {count} transactions and visible checkbox/amount columns checked against PTR scan page {number}.")
        save(path, value)

    path, value = page(11)
    rows = tx_rows(value)
    assert len(rows) == 27 and rows[-1]["asset_name"] in {
        "CITIGROUP INC. HYBRID 11/05/2030 USD",
        "CITIGROUP INC. HYBRID 04/23/2029 USD",
    }
    replacement = annual_row(195, 9, "CITIGROUP INC. HYBRID 04/23/2029 USD")
    rows[-1].clear()
    rows[-1].update(replacement)
    verified(value, "All 27 transactions checked against PTR scan page 11; final Citigroup issue corrected to the printed 04/23/2029 hybrid.")
    save(path, value)

    path, value = page(17)
    rows = tx_rows(value)
    assert len(rows) == 27
    assert rows[7]["asset_name"] == "BERKSHIRE HATHAWAY INC. CLASS B"
    rows[7]["notification_date"] = NOTIFICATION_DATE
    assert rows[18]["asset_name"] in {"IQVIA HOLDINGS INC CMN", "CF INDUSTRIES HOLDINGS, INC. CMN"}
    rows[18]["asset_name"] = "CF INDUSTRIES HOLDINGS, INC. CMN"
    rows[18]["date"] = "5/19/2023"
    assert rows[21]["asset_name"] == "WHIRLPOOL CORP. CMN"
    rows[21]["date"] = "5/19/2023"
    verified(value, "All 27 transactions checked against PTR scan page 17; CF Industries and the printed Whirlpool date restored.")
    save(path, value)

    path, value = page(18)
    rows = tx_rows(value)
    assert len(rows) == 27
    assert rows[1]["asset_name"] in {"KEYCORP CMN", "VF CORP CMN"}
    rows[1]["asset_name"] = "VF CORP CMN"
    rows[1]["date"] = "5/19/2023"
    rows[12]["asset_name"] = "CALL/NVO FLEX EURO PM @ 157.5 EXP 05/12/2023"
    rows[14]["asset_name"] = "CALL/NVS FLEX EURO PM @ 92 EXP 05/12/2023"
    verified(value, "All 27 transactions checked against PTR scan page 18; VF Corp and printed option identifiers restored.")
    save(path, value)


def repair_missing_notifications() -> None:
    path, value = page(13)
    rows = tx_rows(value)
    assert len(rows) == 26
    assert rows[22]["asset_name"] == "SNAP-ON INC CMN"
    rows[22]["notification_date"] = NOTIFICATION_DATE
    save(path, value)


def rebuild_page_19() -> None:
    path, value = page(19)
    rows = annual_range(262, 4, 26) + annual_range(263, 1, 4)
    assert len(rows) == 27
    assert rows[0]["asset_name"] == "ALPHABET INC. CMN CLASS C"
    assert rows[-1]["asset_name"] == "ABBOTT LABORATORIES CMN"
    paypal = next(row for row in rows if row["asset_name"] == "PAYPAL HOLDINGS, INC. CMN")
    paypal["date"] = "5/19/2023"  # PTR scan; annual Schedule B says 5/9.
    value["rows"] = rows
    verified(
        value,
        "All 27 transactions checked against PTR scan page 19; omitted Alphabet Class C restored and printed PayPal row/date retained. COMMON STOCK is printed verbatim.",
    )
    save(path, value)


def insert_page_22_liberty_global() -> None:
    path, value = page(22)
    rows = tx_rows(value)
    if len(rows) == 26:
        assert rows[-4]["asset_name"] == "VIATRIS INC CMN"
        assert rows[-3]["asset_name"] == "MASTERCARD INCORPORATED CMN CLASS A"
        missing = annual_row(266, 4, "LIBERTY GLOBAL, PLC. CMN CLASS C")
        value["rows"].insert(len(value["rows"]) - 3, missing)
    else:
        assert len(rows) == 27
        assert rows[-4]["asset_name"] == "LIBERTY GLOBAL, PLC. CMN CLASS C"
    assert len(tx_rows(value)) == 27
    verified(value, "All 27 transactions checked against PTR scan page 22; omitted Liberty Global row restored before Mastercard.")
    save(path, value)


def rebuild_page_24() -> None:
    path, value = page(24)
    rows = annual_range(267, 9, 26) + annual_range(268, 1, 9)
    assert len(rows) == 27
    assert rows[0]["asset_name"] == "EBAY INC. CMN"
    assert rows[-1]["asset_name"] == "COLGATE-PALMOLIVE CO CMN"
    for name in ("REALTY INCOME CORPORATION CMN", "MODERNA INC. CMN"):
        row = next(row for row in rows if row["asset_name"] == name)
        row["date"] = "5/19/2023"  # PTR scan; annual lists these as June 19.
    value["rows"] = rows
    verified(
        value,
        "All 27 transactions checked against PTR scan page 24; Realty Income, Moderna, and omitted Freeport-McMoRan restored in printed order.",
    )
    save(path, value)


def rebuild_page_25() -> None:
    path, value = page(25)
    first_block = annual_range(268, 10, 25)
    assert len(first_block) == 16
    dow = next(row for row in first_block if row["asset_name"] == "DOW INC CMN")
    dow["date"] = "5/23/2023"  # PTR scan; annual lists 5/22.
    trust_block = annual_range(309, 11, 20)
    assert len(trust_block) == 10
    scan_names = {
        "OLENTANGY LOC SCH DIST OHIO GO 4% 12/01/26": "OLENTANGY LOC SCH DIST OHIO GO 4% 12/01/26-CA JD",
        "PHILIP MORRIS INTERNATIONAL IN 1.75% 11/01/2031": "PHILIP MORRIS INTERNATIONAL IN 1.75% 11/01/2030 USD",
        "BANK OF AMERICA CORPORATION HYBRID PERPETUAL": "BANK OF AMERICA CORPORATION HYBRID PERPETUAL USD",
        "TRUIST FINANCIAL CORPORATION HYBRID PERPETUAL": "TRUIST FINANCIAL CORPORATION HYBRID PERPETUAL USD",
        "BANK OF NEW YORK MELLON CORPOR HYBRID PERPETUAL": "BANK OF NEW YORK MELLON CORPOR HYBRID PERPETUAL USD",
        "CENTERPOINT ENERGY, INC HYBRID PERPETUAL USD": "CENTERPOINT ENERGY, INC HYBRID PERPETUAL USD",
        "DUKE ENERGY CORPORATION HYBRID PERPETUAL": "DUKE ENERGY CORPORATION HYBRID PERPETUAL USD",
    }
    for row in trust_block:
        row["asset_name"] = scan_names.get(row["asset_name"], row["asset_name"])
    value["rows"] = first_block + [{"kind": "group", "text": "Ritu Ahuja 1995 Trust"}] + trust_block
    assert len(tx_rows(value)) == 26
    verified(
        value,
        "All 26 transactions and trust separator checked against PTR scan page 25; omitted Micron and Alcoa restored and printed trust block order retained.",
    )
    save(path, value)


def rebuild_page_26() -> None:
    path, value = page(26)
    rows = annual_range(309, 21, 26) + annual_range(310, 1, 21)
    assert len(rows) == 27
    assert rows[0]["asset_name"] == "EDISON INTERNATIONAL HYBRID PERPETUAL USD"
    assert rows[-1]["asset_name"] == "ENERGY TRANSFER OPERATING LP FRN 11/01/2066"
    scan_names = {
        "BANK OF NEW YORK MELLON CORPOR HYBRID PERPETUAL": "BANK OF NEW YORK MELLON CORPOR HYBRID PERPETUAL USD",
        "CHARLES SCHWAB CORPORATION (TH) HYBRID PERPETUAL": "CHARLES SCHWAB CORPORATION (TH) HYBRID PERPETUAL USD",
        "HUNTINGTON BANCSHARES INCORPOR HYBRID PERPETUAL": "HUNTINGTON BANCSHARES INCORPOR HYBRID PERPETUAL USD",
        "ALLSTATE CORPORATION (THE) PFD 7.3750 SERIES": "ALLSTATE CORPORATION (THE) PFD 7.3750 SERIES J BEQ",
        "ENERGY TRANSFER OPERATING LP FRN 11/01/2066": "ENERGY TRANSFER OPERATING LP FRN 11/01/2066 USD SER B",
    }
    for row in rows:
        row["asset_name"] = scan_names.get(row["asset_name"], row["asset_name"])
    value["rows"] = rows
    verified(
        value,
        "All 27 transactions checked against PTR scan page 26; omitted Edison International and Humana rows restored in printed order.",
    )
    save(path, value)


def normalize_other_verified_pages() -> None:
    # The scans spell out these linked-note names; the annual source truncates
    # them. Preserve what the PTR actually prints.
    for number in (14, 15):
        path, value = page(number)
        rows = tx_rows(value)
        for row in rows:
            if row["asset_name"] == "CAPPED BUFFERED ENHANCED PARTICIPATION LIN":
                row["asset_name"] = "CAPPED BUFFERED ENHANCED PARTICIPATION LINKED TO S&P 500 INDEX"
        verified(value, f"All transaction rows and noted linked-note names checked against PTR scan page {number}.")
        save(path, value)

    for number in (23, 27):
        path, value = page(number)
        verified(value, f"All transaction rows and noted names checked against PTR scan page {number}.")
        save(path, value)

    path, value = page(28)
    groups = [row for row in value["rows"] if row.get("kind") == "group"]
    assert len(groups) == 3
    groups[1]["text"] = "MURA Holdings - Grandchildren Trust (Khanna Portion)"
    verified(value, "All six transactions and three printed MURA account separators checked against PTR scan page 28.")
    save(path, value)


def mark_printed_fragments() -> None:
    for number in (5, 19):
        path, value = page(number)
        assert any(row.get("asset_name") == "COMMON STOCK" for row in value["rows"])
        value["uncertainties"] = [
            {
                "row": next(
                    index
                    for index, row in enumerate(tx_rows(value), 1)
                    if row.get("asset_name") == "COMMON STOCK"
                ),
                "field": "asset_name",
                "read": "COMMON STOCK",
                "note": "The filed PTR itself prints only COMMON STOCK on this row; retained verbatim rather than inventing an issuer.",
            }
        ]
        value["page_confidence"] = "high"
        save(path, value)


def validate() -> None:
    expected = {
        2: 5, 3: 25, 4: 27, 5: 26, 6: 26, 7: 27, 8: 27, 9: 27,
        10: 27, 11: 27, 12: 27, 13: 26, 14: 27, 15: 26, 16: 26,
        17: 27, 18: 27, 19: 27, 20: 27, 21: 27, 22: 27, 23: 26,
        24: 27, 25: 26, 26: 27, 27: 14, 28: 6,
    }
    total = 0
    for number, count in expected.items():
        value = load(PTR_TEXT / f"page-{number:03d}.json")
        actual = len(tx_rows(value))
        assert actual == count, (number, actual, count)
        total += actual
    assert total == 664, total

    assertions = {
        (6, 15): "THE BANK OF NOVA SCOTIA LINKED TO S&P 500 INDEX",
        (10, 8): "CITIGROUP INC. HYBRID 03/20/2030 USD",
        (11, 27): "CITIGROUP INC. HYBRID 04/23/2029 USD",
        (17, 19): "CF INDUSTRIES HOLDINGS, INC. CMN",
        (18, 2): "VF CORP CMN",
        (19, 1): "ALPHABET INC. CMN CLASS C",
        (19, 17): "PAYPAL HOLDINGS, INC. CMN",
        (22, 24): "LIBERTY GLOBAL, PLC. CMN CLASS C",
        (24, 24): "FREEPORT-MCMORAN INC CMN",
        (25, 3): "MICRON TECHNOLOGY, INC. CMN",
        (25, 10): "ALCOA CORPORATION CMN",
        (26, 1): "EDISON INTERNATIONAL HYBRID PERPETUAL USD",
        (26, 15): "HUMANA INC. CMN",
    }
    for (number, row_number), expected_name in assertions.items():
        value = load(PTR_TEXT / f"page-{number:03d}.json")
        actual = tx_rows(value)[row_number - 1]["asset_name"]
        assert actual == expected_name, (number, row_number, actual, expected_name)

    for number, row_number in ((13, 23), (17, 8)):
        value = load(PTR_TEXT / f"page-{number:03d}.json")
        actual = tx_rows(value)[row_number - 1]["notification_date"]
        assert actual == NOTIFICATION_DATE, (number, row_number, actual)


def main() -> None:
    rebuild_page_3()
    rebuild_page_6()
    insert_page_10_citigroup()
    repair_flagged_pages()
    repair_missing_notifications()
    rebuild_page_19()
    insert_page_22_liberty_global()
    rebuild_page_24()
    rebuild_page_25()
    rebuild_page_26()
    normalize_other_verified_pages()
    mark_printed_fragments()
    validate()
    print("docs/2023-5: rebuilt 664 scan-verified transaction rows")


if __name__ == "__main__":
    main()
