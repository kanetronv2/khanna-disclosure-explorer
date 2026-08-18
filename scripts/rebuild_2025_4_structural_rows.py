#!/usr/bin/env python3
"""Rebuild the 2025-4 PTR pages with scan-verified row structure.

These pages were not date-only OCR errors: several names were merged, omitted,
or duplicated.  Values below are transcribed from the filed page scans.
"""

import json
from pathlib import Path


PTR = Path("docs/2025-4/text")
A = "$1,001-$15,000"
B = "$15,001-$50,000"
C = "$50,001-$100,000"
D = "$100,001-$250,000"


def tx(asset_name, owner, tx_type, date, notification_date, amount=A, cap=False, partial=False):
    return {
        "kind": "tx",
        "owner": owner,
        "asset_name": asset_name,
        "tx_type": tx_type,
        "cap_gain_over_200": cap,
        "partial_sale": partial,
        "date": date,
        "notification_date": notification_date,
        "amount": amount,
    }


def group(text):
    return {"kind": "group", "text": text}


def rewrite(page, rows):
    path = PTR / f"page-{page:03}.json"
    data = json.loads(path.read_text())
    data["rows"] = rows
    data["uncertainties"] = [{
        "field": "rows",
        "note": "All printed rows re-verified against the filed PTR scan; restored omitted rows and separated merged/duplicated asset names.",
    }]
    data["page_confidence"] = "high"
    path.write_text(json.dumps(data, indent=2) + "\n")


# DC purchases, notified 05/08/2025.
rewrite(6, [
    group("Ahuja Grandchildren's Education Trust"),
    tx("BERKSHIRE HATHAWAY INC. CLASS B", "DC", "Purchase", "04/15/2025", "05/08/2025", B),
    tx("MORGAN STANLEY CMN", "DC", "Purchase", "04/15/2025", "05/08/2025", B),
    tx("MERCK & CO., INC. CMN", "DC", "Purchase", "04/15/2025", "05/08/2025", B),
    tx("LOWES COMPANIES INC CMN", "DC", "Purchase", "04/15/2025", "05/08/2025", B),
    tx("SALESFORCE INC CMN", "DC", "Purchase", "04/15/2025", "05/08/2025"),
    tx("DANAHER CORPORATION CMN", "DC", "Purchase", "04/15/2025", "05/08/2025"),
    tx("OHIO ST GO 5% 08/01/28 FA", "DC", "Purchase", "04/30/2025", "05/08/2025", B),
    tx("TEXAS INSTRUMENTS INC. CMN", "DC", "Purchase", "04/15/2025", "05/08/2025"),
    tx("DOVER CORPORATION CMN", "DC", "Purchase", "04/15/2025", "05/08/2025"),
    tx("INTUIT INC CMN", "DC", "Purchase", "04/15/2025", "05/08/2025"),
    tx("CITIGROUP INC. CMN", "DC", "Purchase", "04/15/2025", "05/08/2025", B),
    tx("JOHNSON CONTROLS INTERNATIONAL CMN", "DC", "Purchase", "04/15/2025", "05/08/2025", B),
    tx("THERMO FISHER SCIENTIFIC INC CMN", "DC", "Purchase", "04/15/2025", "05/08/2025"),
    tx("AUTOMATIC DATA PROCESSING INC CMN", "DC", "Purchase", "04/15/2025", "05/08/2025", B),
    tx("UBER TECHNOLOGIES, INC. CMN", "DC", "Purchase", "04/15/2025", "05/08/2025"),
    tx("MICRON TECHNOLOGY, INC. CMN", "DC", "Purchase", "04/15/2025", "05/08/2025"),
    tx("ADVANCED MICRO DEVICES, INC. CMN", "DC", "Purchase", "04/15/2025", "05/08/2025"),
])


def sales_page(page, assets, owner="DC", date="04/15/2025", notified="05/08/2025", flags=None):
    flags = flags or {}
    rows = [group("Ahuja Grandchildren's Education Trust")]
    for i, asset in enumerate(assets):
        spec = flags.get(i, {})
        rows.append(tx(asset, owner, spec.get("type", "Sale"), spec.get("date", date), spec.get("notified", notified), spec.get("amount", A), spec.get("cap", False), spec.get("partial", False)))
    rewrite(page, rows)


sales_page(10, [
    "MEDTRONIC PUBLIC LIMITED COMPANY CMN", "REGENERON PHARMACEUTICAL INC CMN", "XYLEM INC. CMN",
    "AIR PRODUCTS & CHEMICALS INC CMN", "KKR & CO. INC. CMN", "APOLLO GLOBAL MANAGEMENT INC CMN",
    "TRUIST FINANCIAL CORPORATION CMN", "NVR INC CMN", "ON SEMICONDUCTOR CORPORATION CMN",
    "REVVITY INC CMN", "AMERIPRISE FINANCIAL, INC. CMN", "S&P GLOBAL INC. CMN",
    "FOX CORPORATION 4.709% 01/25/2029 USD", "SHERWIN-WILLIAMS CO CMN", "NORFOLK SOUTHERN CORP CMN",
    "AMETEK INC (NEW) CMN", "HILTON WORLDWIDE HOLDINGS INC CMN",
], flags={
    3: {"cap": True}, 4: {"partial": True}, 8: {"cap": True}, 10: {"partial": True}, 11: {"partial": True},
    12: {"date": "04/10/2025"},
})

sales_page(11, [
    "BECTON, DICKINSON AND COMPANY CMN", "HENRY SCHEIN INC COMMON STOCK", "KEYSIGHT TECHNOLOGIES, INC. CMN",
    "J B HUNT TRANS SVCS INC CMN", "WEYERHAEUSER COMPANY CMN", "AMAZON.COM INC CMN",
    "BLACKSTONE GROUP INC/THE CMN", "WESTINGHOUSE AIR BRAKE TECHNOL CMN", "GEN DIGITAL INC CMN",
    "GLOBAL PAYMENTS INC. CMN", "METLIFE, INC. CMN", "W.W. GRAINGER INC CMN",
    "REGIONS FINANCIAL CORPORATION CMN", "M&T BANK CORPORATION CMN", "ROCKWELL AUTOMATION INC CMN",
    "ZEBRA TECHNOLOGIES INC CMN CLASS A", "CHARLES RIVER LABORATORIES INT CMN",
], flags={
    2: {"partial": True}, 5: {"cap": True, "partial": True}, 6: {"partial": True},
    9: {"partial": True}, 10: {"partial": True}, 11: {"partial": True},
})

# Two DC sales lead into the Ritu Ahuja trust's SP purchases.
rewrite(12, [
    group("Ahuja Grandchildren's Education Trust"),
    tx("FOX CORP 3.5% 04/08/2030 USD", "DC", "Sale", "04/10/2025", "05/08/2025"),
    tx("REALTY INCOME CORP 2.85% 12/15/2032 USD", "DC", "Sale", "04/10/2025", "05/08/2025"),
    group("Ritu Ahuja Declaration of Trust"),
    tx("BANK OF MONTREAL LINKED TO S&P 500 INDEX", "SP", "Purchase", "04/24/2025", "05/08/2025", C),
    tx("TARGET CORPORATION CMN", "SP", "Purchase", "04/04/2025", "05/08/2025", B),
    tx("MKS INSTRUMENTS INC CMN", "SP", "Purchase", "04/03/2025", "05/08/2025", B),
    tx("HOLOGIC INCORPORATED CMN", "SP", "Purchase", "04/09/2025", "05/08/2025"),
    tx("GLOBAL PAYMENTS INC. CMN", "SP", "Purchase", "04/07/2025", "05/08/2025"),
    tx("MKS INSTRUMENTS INC CMN", "SP", "Purchase", "04/04/2025", "05/08/2025"),
    tx("TARGET CORPORATION CMN", "SP", "Purchase", "04/09/2025", "05/08/2025"),
    tx("TARGET CORPORATION CMN", "SP", "Purchase", "04/07/2025", "05/08/2025"),
    tx("GLOBAL PAYMENTS INC. CMN", "SP", "Purchase", "04/09/2025", "05/08/2025"),
    tx("TRUIST FINANCIAL CORPORATION CMN", "SP", "Purchase", "04/23/2025", "05/08/2025"),
    tx("TRUIST FINANCIAL CORPORATION CMN", "SP", "Purchase", "04/16/2025", "05/08/2025"),
    tx("BANK OF AMERICA CORP CMN", "SP", "Purchase", "04/04/2025", "05/08/2025"),
    tx("MICRON TECHNOLOGY, INC. CMN", "SP", "Purchase", "04/04/2025", "05/08/2025"),
    tx("GLOBAL PAYMENTS INC. CMN", "SP", "Purchase", "04/08/2025", "05/08/2025"),
    tx("ALPHABET INC. CMN CLASS C", "SP", "Purchase", "04/03/2025", "05/08/2025"),
])


sales_page(14, [
    "OKTA, INC. CMN CLASS A", "OKTA, INC. CMN CLASS A", "SENSATA TECHNOLOGIES HOLDING PLC CMN",
    "ZIMMER BIOMET HOLDINGS INC", "DUN & BRADSTREET HOLDINGS, INC CMN", "SS&C TECHNOLOGIES HOLDINGS, INC CMN",
    "DUN & BRADSTREET HOLDINGS, INC CMN", "BAXTER INTERNATIONAL INC CMN", "DUN & BRADSTREET HOLDINGS, INC CMN",
    "BAXTER INTERNATIONAL INC CMN", "GRAPHIC PACKAGING HLDGCO CMN", "GRAPHIC PACKAGING HLDGCO CMN",
    "MKS INSTRUMENTS INC CMN", "SENSATA TECHNOLOGIES HOLDING PLC CMN", "SENSATA TECHNOLOGIES HOLDING PLC CMN",
    "GRAPHIC PACKAGING HLDGCO CMN", "GRAPHIC PACKAGING HLDGCO CMN",
], owner="SP", flags={
    0: {"cap": True, "partial": True, "date": "04/08/2025"}, 1: {"cap": True, "date": "04/04/2025"},
    2: {"partial": True, "date": "04/04/2025"}, 3: {"partial": True, "date": "04/04/2025"},
    4: {"partial": True, "date": "04/03/2025"}, 5: {"cap": True, "partial": True, "date": "04/10/2025"},
    6: {"partial": True, "date": "04/04/2025"}, 7: {"partial": True, "date": "04/03/2025"},
    8: {"date": "04/09/2025"}, 9: {"partial": True, "date": "04/08/2025"},
    10: {"cap": True, "partial": True, "date": "04/28/2025"}, 11: {"cap": True, "partial": True, "date": "04/23/2025"},
    12: {"type": "Sale", "cap": True, "date": "04/17/2025"}, 13: {"partial": True, "date": "04/30/2025"},
    14: {"partial": True, "date": "04/11/2025"}, 15: {"cap": True, "partial": True, "date": "04/02/2025"},
    16: {"cap": True, "partial": True, "date": "04/24/2025"},
})


def purchases_sp(page, assets, dates):
    rewrite(page, [group("Ahuja Grandchildren's Education Trust")] + [
        tx(asset, "SP", "Purchase", date, "05/08/2025") for asset, date in zip(assets, dates)
    ])


purchases_sp(17, [
    "CHUBB LIMITED CMN", "PRINCIPAL FINANCIAL GROUP, INC CMN", "DELTA AIR LINES, INC. CMN", "APPLIED MATERIALS INC CMN",
    "REGENERON PHARMACEUTICAL INC CMN", "MKS INSTRUMENTS INC CMN", "ALPHABET INC. CMN CLASS C", "DOW INC CMN",
    "FAIR ISAAC INC CMN", "COPART, INC. CMN", "FISERV, INC. CMN", "CISCO SYSTEMS, INC. CMN",
    "CAPITAL ONE FINANCIAL CORP CMN", "TARGET CORPORATION CMN", "CROWN CASTLE INTL CORP CMN",
    "UNITEDHEALTH GROUP INCORPORATED CMN", "TARGET CORPORATION CMN",
], ["04/09/2025", "04/09/2025", "04/09/2025", "04/23/2025", "04/09/2025", "04/04/2025", "04/09/2025", "04/23/2025", "04/23/2025", "04/23/2025", "04/09/2025", "04/23/2025", "04/08/2025", "04/09/2025", "04/09/2025", "04/09/2025", "04/07/2025"])

purchases_sp(24, [
    "CAESARS ENTERTAINMENT INC CMN", "INTERPUBLIC GROUP COS CMN", "ARCHER-DANIELS-MIDLAND COMPANY CMN",
    "ZEBRA TECHNOLOGIES INC CMN CLASS A", "BIOGEN INC. CMN", "DOLLAR GENERAL CORPORATION CMN",
    "SKYWORKS SOLUTIONS, INC. CMN", "BUILDERS FIRSTSOURCE, INC. CMN", "ALTRIA GROUP, INC. CMN",
    "ARCH CAPITAL GROUP LTD. CMN", "WESTERN DIGITAL CORPORATION CMN", "DIGITAL REALTY TRUST, INC. CMN",
    "WEST PHARMACEUTICAL SERVICES INC", "GLOBAL PAYMENTS INC. CMN", "KKR & CO. INC. CMN",
    "FEDEX CORPORATION CMN", "AVALONBAY COMMUNITIES INC CMN",
], ["04/23/2025"] * 13 + ["04/14/2025"] + ["04/23/2025"] * 3)


rewrite(43, [
    tx("UNITEDHEALTH GROUP INC", "SP", "Sale", "04/04/2025", "04/07/2025", cap=True),
    tx("VISA INC", "SP", "Sale", "04/04/2025", "04/07/2025", cap=True),
    tx("WALMART INC COM", "SP", "Purchase", "04/04/2025", "04/07/2025"),
    tx("WASTE MANAGEMENT INC", "SP", "Sale", "04/04/2025", "04/07/2025"),
    tx("WELLS FARGO CO NEW COM", "SP", "Purchase", "04/04/2025", "04/07/2025"),
    tx("ZOETIS INC", "SP", "Sale", "04/04/2025", "04/07/2025"),
    tx("MERCK & CO. INC COM", "SP", "Purchase", "04/04/2025", "04/07/2025"),
    group("MURA Holdings"),
    group("Monte and Usha Ahuja 2010 Irrev Trust FBO Grandchildren"),
] + [
    tx(asset, "DC", "Sale", "04/08/2025", "04/09/2025") for asset in [
        "PUT (JPM) JPMORGAN CHASE & CO. JUL 18 25 $170 (100 SHS)",
        "PUT (AAPL) APPLE INC JUL 18 25 $155 (100 SHS)",
        "PUT (SPY) SPDR S&P500 ETF JUL 18 25 $410 (100 SHS)",
        "PUT (NVDA) NVIDIA CORPORATION JUL 18 25 $75 (100 SHS)",
        "PUT (GS) GOLDMAN SACHS GROUP JUL 18 25 $380 (100 SHS)",
        "PUT (GOOGL) ALPHABET INC CAP STK JUL 18 25 $120 (200 SHS)",
        "PUT (TSLA) TESLA INC COM JUL 18 25 $195 (100 SHS)",
        "PUT (IWM) ISHARES RUSSELL 2000 JUL 18 25 $145 (100 SHS)",
        "PUT (V) VISA INC JUL 18 25 $255 (100 SHS)",
    ]
])

rewrite(45, [
    tx("BROADCOM INC COM", "DC", "Sale", "04/04/2025", "04/07/2025", cap=True),
    tx("BROADCOM INC COM", "DC", "Sale", "04/04/2025", "04/07/2025", cap=True),
    tx("CHEVRON CORP NEW COM", "DC", "Purchase", "04/04/2025", "04/07/2025"),
    tx("CISCO SYSTEMS INC", "DC", "Sale", "04/04/2025", "04/07/2025"),
    tx("CISCO SYSTEMS INC", "DC", "Sale", "04/04/2025", "04/07/2025"),
    tx("CISCO SYSTEMS INC", "DC", "Sale", "04/04/2025", "04/07/2025"),
    tx("CONOCOPHILLIPS COM", "DC", "Sale", "04/04/2025", "04/07/2025"),
    tx("DISNEY WALT CO COM", "DC", "Sale", "04/04/2025", "04/07/2025"),
    tx("EXXON MOBIL CORP COM", "DC", "Purchase", "04/04/2025", "04/07/2025"),
    tx("META PLATFORMS INC CLASS A COMMON STOCK", "DC", "Sale", "04/04/2025", "04/07/2025"),
    tx("GE AEROSPACE COM NEW", "DC", "Sale", "04/04/2025", "04/07/2025", cap=True),
    tx("HOME DEPOT INC", "DC", "Sale", "04/04/2025", "04/07/2025", B),
    tx("HONEYWELL INTERNATIONAL INC COM USD1", "DC", "Sale", "04/04/2025", "04/07/2025"),
    tx("HONEYWELL INTERNATIONAL INC COM USD1", "DC", "Sale", "04/04/2025", "04/07/2025"),
    tx("HONEYWELL INTERNATIONAL INC COM USD1", "DC", "Sale", "04/04/2025", "04/07/2025"),
    tx("INTERNATIONAL BUS MACH CORP COM USD0.20", "DC", "Purchase", "04/04/2025", "04/07/2025"),
    tx("ISHARES TR 0-3 MNTH TREASRY", "DC", "Sale", "04/04/2025", "04/07/2025", B),
    tx("JPMORGAN CHASE & CO. COM", "DC", "Purchase", "04/04/2025", "04/07/2025"),
])

rewrite(46, [
    tx("JOHNSON & JOHNSON COM", "DC", "Purchase", "04/04/2025", "04/07/2025"),
    tx("LVMH MOET HENNESSY LOUIS VUITTON ADR", "DC", "Sale", "04/04/2025", "04/07/2025"),
    tx("ELI LILLY & CO COM", "DC", "Purchase", "04/04/2025", "04/07/2025"),
    tx("MASTERCARD INCORPORATED CL A", "DC", "Purchase", "04/04/2025", "04/07/2025"),
    tx("MCDONALD'S CORP", "DC", "Sale", "04/04/2025", "04/07/2025", cap=True),
    tx("MICROSOFT CORP", "DC", "Sale", "04/04/2025", "04/07/2025"),
    tx("MONDELEZ INTL INC COM NPV", "DC", "Sale", "04/04/2025", "04/07/2025"),
    tx("MONDELEZ INTL INC COM NPV", "DC", "Sale", "04/04/2025", "04/07/2025"),
    tx("NETFLIX INC", "DC", "Purchase", "04/04/2025", "04/07/2025"),
    tx("NVIDIA CORPORATION COM", "DC", "Purchase", "04/04/2025", "04/07/2025", B),
    tx("ORACLE CORP", "DC", "Purchase", "04/04/2025", "04/07/2025"),
    tx("PALANTIR TECHNOLOGIES INC CL A", "DC", "Purchase", "04/04/2025", "04/07/2025"),
    tx("PEPSICO INC", "DC", "Sale", "04/04/2025", "04/07/2025"),
    tx("PROCTER AND GAMBLE CO COM", "DC", "Sale", "04/04/2025", "04/07/2025"),
    tx("QUALCOMM INC", "DC", "Sale", "04/04/2025", "04/07/2025"),
    tx("RTX CORPORATION COM USD1.00", "DC", "Sale", "04/04/2025", "04/07/2025", cap=True),
    tx("RTX CORPORATION COM USD1.00", "DC", "Sale", "04/04/2025", "04/07/2025", cap=True),
    tx("RTX CORPORATION COM USD1.00", "DC", "Sale", "04/04/2025", "04/07/2025", cap=True),
])

rewrite(48, [
    *[tx(asset, "DC", "Sale", "04/08/2025", "04/09/2025") for asset in [
        "PUT (AAPL) APPLE INC JUL 18 25 $155 (100 SHS)",
        "PUT (SPY) SPDR S&P500 ETF JUL 18 25 $410 (100 SHS)",
        "PUT (GS) GOLDMAN SACHS GROUP JUL 18 25 $380 (100 SHS)",
        "PUT (NVDA) NVIDIA CORPORATION JUL 18 25 $75 (100 SHS)",
        "PUT (GOOGL) ALPHABET INC CAP STK JUL 18 25 $120 (100 SHS)",
        "PUT (TSLA) TESLA INC COM JUL 18 25 $195 (100 SHS)",
        "PUT (IWM) ISHARES RUSSELL 2000 JUL 18 25 $145 (100 SHS)",
        "PUT (V) VISA INC JUL 18 25 $255 (100 SHS)",
    ]],
    tx("BANK MONTREAL MEDIUM SER K MTN ZERO CPN 0.00000% 10/21/2027", "DC", "Purchase", "04/16/2025", "04/22/2025", D),
    tx("ACCENTURE PLC", "DC", "Sale", "04/04/2025", "04/07/2025"),
    tx("ACCENTURE PLC", "DC", "Sale", "04/04/2025", "04/07/2025"),
    tx("ACCENTURE PLC", "DC", "Sale", "04/04/2025", "04/07/2025"),
    tx("ABBOTT LABORATORIES", "DC", "Sale", "04/04/2025", "04/07/2025"),
    tx("ABBOTT LABORATORIES", "DC", "Sale", "04/04/2025", "04/07/2025"),
    tx("ABBOTT LABORATORIES", "DC", "Sale", "04/04/2025", "04/07/2025"),
    tx("ABBVIE INC COM USD0.01", "DC", "Sale", "04/04/2025", "04/07/2025", cap=True),
    tx("ALPHABET INC CAP STK CL A", "DC", "Purchase", "04/04/2025", "04/07/2025"),
])


def complete_checkbox_fields():
    """Canonicalize every scan-encoded Partial Sale mark in this PTR."""
    transactions = partial_true = cap_true = 0
    for path in sorted(PTR.glob("page-*.json")):
        data = json.loads(path.read_text())
        changed = False
        for row in data.get("rows", []):
            if row.get("kind") != "tx":
                continue
            transactions += 1
            assert isinstance(row.get("cap_gain_over_200"), bool), path
            marked_partial = (
                row.get("partial_sale") is True
                or row.get("tx_type") == "Partial Sale"
            )
            if row.get("tx_type") == "Partial Sale":
                row["tx_type"] = "Sale"
                changed = True
            if row.get("partial_sale") is not marked_partial:
                row["partial_sale"] = marked_partial
                changed = True
            cap_true += row["cap_gain_over_200"]
            partial_true += marked_partial
        if changed:
            path.write_text(json.dumps(data, indent=2) + "\n")
    assert transactions == 840
    print(
        f"2025-4: transactions={transactions} "
        f"cap_gain_true={cap_true} partial_sale_true={partial_true}"
    )


complete_checkbox_fields()
