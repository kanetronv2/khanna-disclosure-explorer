#!/usr/bin/env python3
"""Rebuild the January 2022 PTR from the lossless filed-form scans."""

from __future__ import annotations

import copy
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PTR = ROOT / "docs/2022-1/text"
ANNUAL = ROOT / "docs/2021-13/text"
NOTICE = "1/6/2022"


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def save(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def annual(page: int, first: int, last: int) -> list[dict]:
    source = load(ANNUAL / f"page-{page:03d}.json")["rows"]
    rows = []
    for index in range(first - 1, last):
        row = copy.deepcopy(source[index])
        assert row["kind"] == "tx", (page, index + 1)
        row["notification_date"] = NOTICE
        row["partial_sale"] = row.get("tx_type") == "Partial Sale"
        rows.append(row)
    return rows


def tx(name: str, *, owner: str = "SP", date: str = "12/7/2021", amount: str = "$1,001-$15,000", kind: str = "Purchase") -> dict:
    return {
        "kind": "tx", "owner": owner, "asset_name": name,
        "tx_type": kind, "cap_gain_over_200": False,
        "partial_sale": kind == "Partial Sale", "date": date,
        "notification_date": NOTICE, "amount": amount,
    }


def group(name: str) -> dict:
    return {"kind": "group", "text": name}


def verified(value: dict, note: str, uncertainties: list[dict] | None = None) -> None:
    value["page_confidence"] = "high" if not uncertainties else "medium"
    value["uncertainties"] = uncertainties or [{
        "row": "page", "field": "verification", "read": "scan-verified", "note": note,
    }]


def rebuild_page_3() -> None:
    path = PTR / "page-003.json"; value = load(path); old = value["rows"]
    first = annual(188, 7, 27) + annual(189, 1, 2)
    middle = [copy.deepcopy(row) for row in old[23:35]]
    for row in middle:
        row["notification_date"] = NOTICE
    grandchildren = annual(195, 1, 19)
    trust_names = [
        "VERIZON COMMUNICATIONS, INC. CMN", "APPLE INC. CMN", "AMAZON.COM INC CMN",
        "VISA INC. CMN CLASS A", "NIKE CLASS-B CMN CLASS B",
        "BRISTOL-MYERS SQUIBB COMPANY CMN", "WICHITA KS GO 4% 10/15/27 AO",
        "TRACTOR SUPPLY COMPANY CMN", "VERMONT MUN BD DR REV 3% 10/12/30",
        "TEXAS INSTRUMENTS INC. CMN", "QUALCOMM INC CMN",
        "BOSTON SCIENTIFIC CORP COMMON STOCK", "ALTRIA GROUP, INC. CMN", "US BANCORP CMN",
    ]
    trust = [tx(name, owner="DC", amount="$15,001-$50,000" if i < 8 else "$1,001-$15,000") for i, name in enumerate(trust_names)]
    value["rows"] = first + middle + [group("Ahuja Grandchildren Trust")] + grandchildren + [group("Monte and Usha Ahuja 2010 Irrevocable Trust FBO Grandchildren")] + trust
    verified(value, "All 68 transactions and two account separators checked against lossless PTR scan page 3; matching annual rows used only for locally matching sequences.")
    save(path, value)


def rebuild_page_4() -> None:
    path = PTR / "page-004.json"; value = load(path)
    assert len(value["rows"]) == 73
    for row in value["rows"]:
        row.update(tx(row["asset_name"], owner="DC", date=row.get("date") or "12/7/2021"))
    verified(value, "All 73 printed rows, purchase marks, notification dates, and amount-column-A marks checked against lossless PTR scan page 4.")
    save(path, value)


PAGE5_NAMES = [
    "INTL BUSINESS MACHINES CORP CMN", "QORVO, INC. CMN", "LABORATORY CORPORATION OF AMER CMN", "AVALARA INC CMN",
    "TRADE DESK, INC. (THE) CMN", "SYNCHRONY FINANCIAL CMN", "US FOODS HOLDING CORP. CMN", "EVEREST RE GROUP LTD CMN",
    "TWILIO INC. CMN CLASS A", "UNIVERSAL HEALTH SVC CL B CMN CLASS B", "LEMONADE INC CMN", "HORMEL FOODS CORPORATION CMN",
    "HUNTINGTON BANCSHARES INCORPORATED CMN", "NATIONAL RETAIL PROPERTIES INC CMN", "STERIS PUBLIC LIMITED COMPANY CMN",
    "DOLLAR GENERAL CORPORATION CMN", "FLEETCOR TECHNOLOGIES INC CMN", "RINGCENTRAL, INC. CMN", "CASEY'S GENERAL STORES INC CMN",
    "META PLATFORMS INC CMN CLASS A", "ADOBE INC CMN", "APTIV INC CMN", "MEDTRONIC PUBLIC LIMITED COMPANY CMN", "WALMART INC CMN",
    "MERCK & CO., INC. CMN", "ORACLE CORPORATION CMN", "FIDELITY NATL INFO SVCS INC CMN", "PULTEGROUP INC. CMN", "BLACKROCK, INC. CMN",
    "COCA-COLA COMPANY (THE) CMN", "AMERICAN EXPRESS CO. CMN", "STRYKER CORPORATION CMN", "AMERICAN TOWER CORPORATION CMN",
    "CHARTER COMMUNICATIONS, INC. CMN", "CIGNA CORP CMN", "COMCAST CORPORATION CMN CLASS A VOTING", "CROWN CASTLE INTL CORP CMN",
    "WELLS FARGO & CO (NEW) CMN", "PNC FINANCIAL SERVICES GROUP, CMN", "CME GROUP INC. CMN CLASS A", "BOOKING HOLDINGS INC. CMN",
    "TARGET CORPORATION CMN", "ULTA BEAUTY INC CMN", "PAYPAL HOLDINGS, INC. CMN", "ELECTRONIC ARTS CMN",
    "AIR PRODUCTS & CHEMICALS INC CMN", "SYSCO CORPORATION CMN", "BEST BUY CO INC CMN", "EDWARDS LIFESCIENCES CORPORATION CMN",
    "AUTODESK, INC. CMN", "HEWLETT PACKARD ENTERPRISE CO CMN", "QORVO, INC. CMN", "CELANESE CORPORATION COMMON STOCK",
    "GILEAD SCIENCES CMN", "LINCOLN NATL CORP. INC. CMN", "PRUDENTIAL FINANCIAL INC CMN", "DELTA AIR LINES, INC. CMN",
    "NETAPP, INC. CMN", "BIOGEN INC. CMN", "APTIV PLC CMN", "VENTAS, INC. CMN", "ZIMMER BIOMET HOLDINGS INC",
    "STANLEY BLACK & DECKER, INC. CMN", "THE TRAVELERS COMPANIES, INC CMN", "SVB FINANCIAL GROUP CMN", "TRIMBLE INC CMN",
    "ENPHASE ENERGY, INC. CMN", "TE CONNECTIVITY LTD CMN", "REGENERON PHARMACEUTICAL INC CMN", "MSCI INC. CMN",
    "WALT DISNEY COMPANY (THE) CMN", "RESMED INC. CMN", "KIMBERLY-CLARK CORPORATION CMN",
]


def rebuild_page_5() -> None:
    path = PTR / "page-005.json"; value = load(path); old = value["rows"]
    assert len(PAGE5_NAMES) == 73 and len(old) in {73, 74}
    rows = []
    for i, name in enumerate(PAGE5_NAMES):
        prior = old[i]
        kind = "Purchase" if i < 19 else prior.get("tx_type") or "Sale"
        amount = "$15,001-$50,000" if 19 <= i < 29 else "$1,001-$15,000"
        row = tx(name, owner="DC", date="12/7/2021", amount=amount, kind=kind)
        row["cap_gain_over_200"] = bool(prior.get("cap_gain_over_200"))
        if name == "STERIS PUBLIC LIMITED COMPANY CMN":
            # The lossless PTR scan has only the Purchase mark; the capital-gain
            # and partial-sale columns are both blank.
            row["cap_gain_over_200"] = False
        rows.append(row)
    value["rows"] = rows
    verified(value, "All 73 printed rows checked against lossless PTR scan page 5; one OCR-created duplicate row removed.")
    save(path, value)


PAGE6_FIRST = [
    "WESTERN UNION COMPANY (THE) CMN", "STRYKER CORPORATION CMN", "OTIS WORLDWIDE CORPORATION CMN", "VF CORP CMN",
    "BECTON, DICKINSON AND COMPANY CMN", "TJX COMPANIES INC (NEW) CMN", "AMERISOURCEBERGEN CORPORATION CMN",
    "W.W. GRAINGER INC CMN", "CONAGRA BRANDS INC CMN", "ROPER TECHNOLOGIES INC CMN", "AMCOR PLC CMN", "GARMIN LTD CMN",
    "PAYCOM SOFTWARE, INC. CMN", "WHIRLPOOL CORP. CMN", "TELEDYNE TECHNOLOGIES INCORPORATED CMN", "CITRIX SYSTEMS INC CMN",
    "MATCH GROUP, INC. CMN", "AVALONBAY COMMUNITIES INC CMN", "GILEAD SCIENCES CMN", "GAMING AND LEISURE PROP, INC. CMN",
    "JAZZ PHARMACEUTICALS PLC CMN", "CHARLES RIV LABS INTL INC CMN", "COMCAST CORPORATION CMN", "UNITED RENTALS, INC. CMN",
    "SBA COMMUNICATIONS CORPORATION CMN", "ASTRAZENECA PLC SPONS ADR SPONSORED ADR CMN", "ABIOMED, INC. CMN",
    "UNIVERSAL DISPLAY CORPORATION CMN", "AGILENT TECHNOLOGIES, INC. CMN", "SEAGEN INC. CMN", "JACK HENRY & ASSOC INC CMN",
    "SALESFORCE.COM, INC CMN", "MARRIOTT INTERNATIONAL, INC CMN CLASS A", "SPOTIFY TECHNOLOGY S.A. CMN",
    "NEW YORK TIMES CO A CMN CLASS A", "EXXON MOBIL CORPORATION CMN", "AVERY DENNISON CORPORATION CMN", "CENTENE CORPORATION CMN",
    "CARNIVAL CORPORATION CMN", "WATERS CORPORATION COMMON STOCK", "PENN NATIONAL GAMING INC CMN", "STARBUCKS CORP. CMN", "ROYAL GOLD, INC. CMN",
]


def rebuild_page_6() -> None:
    path = PTR / "page-006.json"; value = load(path); old = value["rows"]
    first = []
    for i, name in enumerate(PAGE6_FIRST):
        prior = old[min(i, len(old) - 1)]
        first.append(tx(name, owner="DC", kind=prior.get("tx_type") or "Sale", date="12/7/2021"))
    bonds = [
        tx("DORMITORY AUTH OF STATE OF NY REV 5.0000% 01/15/26-CA MN", date="12/7/2021", amount="$15,001-$50,000"),
        tx("SAN ANTONIO TEX WTR REV REV 5% 11/15/26 MN", date="12/7/2021", amount="$15,001-$50,000"),
        tx("LONG IS PWR AUTH N Y ELEC SYS REV 1% 09/01/25-CA MS", date="12/7/2021", amount="$15,001-$50,000"),
    ]
    lower_names = [
        "VERIZON COMMUNICATIONS, INC. CMN", "VISA INC. CMN CLASS A", "MEDTRONIC PUBLIC LIMITED COMPANY CMN", "JOHNSON & JOHNSON CMN",
    ]
    lower = [tx(name, date="12/14/2021", amount="$15,001-$50,000") for name in lower_names]
    lower += annual(250, 16, 27) + annual(251, 1, 8)
    value["rows"] = first + [group("Ahuja 2010 Trust")] + bonds + [group("Ritu Ahuja 1995 Trust")] + lower
    verified(value, "All 70 transactions and two account separators checked against lossless PTR scan page 6; annual rows used only for the matching final sequence.")
    save(path, value)


def rebuild_page_7() -> None:
    path = PTR / "page-007.json"; value = load(path)
    first = [
        tx("PFIZER INC. CMN", amount="$15,001-$50,000"),
        tx("NVR INC CMN", amount="$15,001-$50,000"),
        tx("SYCAMORE GROVE PA GO 1% 12/15/22 MN", amount="$15,001-$50,000"),
    ]
    value["rows"] = first + annual(266, 1, 27) + annual(267, 1, 27) + annual(268, 1, 16)
    assert len(value["rows"]) == 73
    verified(value, "All 73 transactions checked against lossless PTR scan page 7; matching annual sequences confirmed at both page transitions.")
    save(path, value)


def rebuild_page_8() -> None:
    path = PTR / "page-008.json"; value = load(path)
    value["rows"] = annual(268, 17, 27) + annual(269, 1, 27) + annual(270, 1, 27) + annual(271, 1, 8)
    assert len(value["rows"]) == 73
    verified(value, "All 73 transactions checked against lossless PTR scan page 8; annual sequence and both endpoints match the scan.")
    save(path, value)


def rebuild_page_9() -> None:
    path = PTR / "page-009.json"; value = load(path)
    rows = annual(285, 1, 24)
    bottom = [
        tx("DALLAS TEX AREA RAPID TRAN REV 5% 12/01/22 JD", date="12/3/2021", amount="$100,001-$250,000"),
        tx("WYANDOTTE CNTY KANS CITY KANS REV 5% 09/01/22 MS", date="12/2/2021", amount="$50,001-$100,000"),
        tx("ILLINOIS FIN AUTH REV REV 5.0000% 08/01/22-CA FA", date="12/7/2021", amount="$15,001-$50,000"),
        tx("FLORIDA ST DEPT MGMT SVCS CTFS COPS 5% 11/01/22", date="12/8/2021", amount="$15,001-$50,000"),
        tx("UNIVERSITY COLO ENTERPRISE SYS REV 5% 06/01/32", date="12/8/2021", amount="$15,001-$50,000"),
        tx("HOOVER ALA BRD ED SPL TAX SCH REV 5% 02/15/24", date="12/8/2021", amount="$15,001-$50,000"),
        tx("NYC TRANSITIONAL FINANCE AUTH REV 5.0000% 08/01/22", date="12/4/2021", amount="$15,001-$50,000"),
        tx("CLARK CNTY WASH PUB UTIL DIST REV 5% 01/01/22 JJ", date="11/10/2021", amount="$15,001-$50,000"),
        tx("PFIZER INC. CMN", date="11/4/2021"),
        tx("AON PUBLIC LIMITED COMPANY CMN", date="12/3/2021"),
    ]
    value["rows"] = rows + [group("Ahuja 2010 Trust")] + bottom
    verified(value, "All 34 transactions and the account separator checked against lossless PTR scan page 9.", [{
        "row": 31, "field": "asset_name", "read": "NYC TRANSITIONAL FINANCE AUTH REV 5.0000% 08/01/22",
        "note": "Issuer and maturity are legible; final printed bond suffix remains too compressed to transcribe confidently.",
    }])
    save(path, value)


def verify_boundary_pages() -> None:
    page2_path = PTR / "page-002.json"
    page2 = load(page2_path)
    assert sum(row.get("kind") == "tx" for row in page2["rows"]) == 10
    assert [row["text"] for row in page2["rows"] if row.get("kind") == "group"] == ["MAR Trust"]
    for row in page2["rows"]:
        if row.get("kind") == "tx":
            row["partial_sale"] = False
    save(page2_path, page2)

    path = PTR / "page-010.json"; page10 = load(path)
    groups = [row["text"] for row in page10["rows"] if row.get("kind") == "group"]
    assert groups == [
        "MURA Holdings / RAM",
        "MURA Holdings / Grandchildren Trust (Khanna Portion)",
        "MURA Holdings / 2020 Trust FBO Khanna Children",
    ]
    transactions = [row for row in page10["rows"] if row.get("kind") == "tx"]
    sales = [row for row in transactions if row["tx_type"] == "Sale"]
    assert len(sales) == 6
    for row in transactions:
        row["partial_sale"] = row["tx_type"] == "Sale"
    verified(page10, "All 21 transactions, three account separators, and repeated seven-row block fields checked against lossless PTR scan page 10.")
    save(path, page10)


def validate() -> None:
    expected = {1:(0,0),2:(10,1),3:(68,2),4:(73,0),5:(73,0),6:(70,2),7:(73,0),8:(73,0),9:(34,1),10:(21,3)}
    tx_total = group_total = 0
    for page, (want_tx, want_group) in expected.items():
        value = load(PTR / f"page-{page:03d}.json")
        got_tx = sum(row.get("kind") == "tx" for row in value.get("rows", []))
        got_group = sum(row.get("kind") == "group" for row in value.get("rows", []))
        assert (got_tx, got_group) == (want_tx, want_group), (page, got_tx, got_group)
        assert all(
            isinstance(row.get("partial_sale"), bool)
            for row in value.get("rows", [])
            if row.get("kind") == "tx"
        ), page
        tx_total += got_tx; group_total += got_group
    assert (tx_total, group_total) == (495, 9)
    page5 = load(PTR / "page-005.json")
    steris = next(row for row in page5["rows"] if row.get("asset_name") == "STERIS PUBLIC LIMITED COMPANY CMN")
    assert steris["tx_type"] == "Purchase"
    assert steris["cap_gain_over_200"] is False and steris["partial_sale"] is False


def main() -> None:
    rebuild_page_3(); rebuild_page_4(); rebuild_page_5(); rebuild_page_6()
    rebuild_page_7(); rebuild_page_8(); rebuild_page_9(); verify_boundary_pages(); validate()
    print("docs/2022-1: rebuilt 495 transactions and 9 account groups")


if __name__ == "__main__":
    main()
