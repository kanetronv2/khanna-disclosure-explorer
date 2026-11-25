"""Shared helpers for compiling Khanna disclosure OCR JSON into site data files."""
import json, os, re

# ---------- bucket parsing ----------
def bucket_range(s):
    """Parse a disclosure bucket string into (min, max). max=None means unbounded."""
    if not s:
        return (None, None)
    t = s.strip().lower()
    if t == "none":
        return (0, 0)
    nums = [int(n.replace(",", "")) for n in re.findall(r"[\d,]+", s)]
    nums = [n for n in nums if n > 0]
    if not nums:
        return (None, None)
    if "over" in t or len(nums) == 1:
        return (nums[0] if "over" not in t else nums[0] + 1, None)
    return (nums[0], nums[1])

# ---------- asset classification ----------
CLASS_RULES = [
    ("Options", re.compile(r"^(CALL|PUT)[ /(]|FLEX EURO PM|\bEXP \d{2}/\d{2}/\d{4}", re.I)),
    ("Structured notes", re.compile(r"LINKED TO|BASKET OF INDICES|BUFFERED|CONTINGENT|UPSIDE LEVERED|CAPPED|BUFFER STRUCTUR|COMMLNKED|COMM LINKED|\bSER [A-Z] NOTE\b", re.I)),
    ("Preferred & hybrid securities", re.compile(r"\bPFD\b|\bHYBRID\b|PERPETUAL USD|JRSUB|JR SUB|SR LIEN|\bCPN\b|PREFERRED", re.I)),
    ("Municipal & gov bonds", re.compile(r"\d(\.\d+)?%.*\d{2}/\d{2}/\d{2}|\b(GO|REV|SCH DIST|SCHS|WTR|SWR|DEV AUTH|EXMP|VLG|BLDG CORP|TRANSN|HWY|CONVENTION|CORRECTIONAL|ISSUES DTD|DB 5%|SPL REV|CAP FACS|RECPTS|OBLIG)\b", re.I)),
    ("Common stock", re.compile(r"\bCMN\b|COMMON STOCK|\bCOM\b|\bADR\b|\bADS\b|\bISIN\b|^ABBOTT LABORATORIES$", re.I)),
    ("Hedge funds & private funds", re.compile(r"HEDGE FUND|FUND SELECT|COMMITMENT|PARTNERS\b|PARTNERSHIP|OPPORTUNITIES|CREDIT PARTNERS|\bSLP\b|SOF ILP|ONSHORE \(|ONSHORE|PE PREMIER|\bBPCP\b|OP UNITS|\bLLC\b|\bL\.?P\.?\b|CAPITAL ACCESS|ACCESS LLC|GROWTH AND EMERGING MARKETS|RIVERSIDE TECHNOLOGY CAPITAL", re.I)),
    ("Cash & deposits", re.compile(r"MONEY MARKET|CASH|DEPOSIT|CHECKING|SAVINGS|\bCD\b|TREASURY BILL|T-BILL|MSILF|TREASURY SECURITIES|U ?S DOLLAR|U\.S\. DOLLAR", re.I)),
    ("Funds & ETFs", re.compile(r"\bETF\b|INDEX FUND|MUTUAL FUND|\bFUNDS?\b|TRUST UNITS|ISHARES|VANGUARD|\bSPDR\b|JANA STRATEGIC|\bJANA\b|VERSUS CAPITAL|LARGE CAP|MID CAP|MAI MANAGED|EATON VANCE|T ROWE PRICE", re.I)),
    ("Common stock", re.compile(r"\bCMN\b|COMMON STOCK|CLASS [AB]\b|\bCL A\b|\bINC\b|INCORPORATED|\bCORP\b|CORPORATION|\bPLC\b|\bCO\b|COMPANY|\bGROUP\b|\bN\.?V\.?\b|\.COM|FLAVORS? & FRAGRANCE", re.I)),
]

def classify(name):
    for label, rx in CLASS_RULES:
        if rx.search(name or ""):
            return label
    return "Other"

# ---------- descriptors ----------
DESCR = {}
_descr_path = os.path.join(os.path.dirname(__file__), "descriptors.json")
if os.path.exists(_descr_path):
    with open(_descr_path) as fh:
        DESCR = json.load(fh)

MONTH_CODES = {"JJ": "Jan/Jul", "FA": "Feb/Aug", "MS": "Mar/Sep", "AO": "Apr/Oct", "MN": "May/Nov", "JD": "Jun/Dec"}
OPT_RX = re.compile(r"^(CALL|PUT)[ /|(]?([A-Z.]{1,6})\)?\b.*?(?:@ ?)?([\d.]+)\s*EXP\s*(\d{2}/\d{2}/\d{4})", re.I)
MUNI_RX = re.compile(r"^(.*?)\s(\d+(?:\.\d+)?)%\s*(?:.*?)(\d{2}/\d{2}/\d{2,4})?\s*(JJ|FA|MS|AO|MN|JD)?$")
TICKER_RX = re.compile(r"^(.+?)\s*\(([A-Z.]{1,6})\)\s*$")

def title(s):
    small = {"of", "and", "the", "for", "de"}
    out = []
    for w in re.split(r"(\s+)", s.strip()):
        if w.isspace() or not w:
            out.append(w); continue
        lw = w.lower()
        out.append(lw if lw in small and out else (w if (len(w) <= 3 and w.isupper() and w not in ("THE", "AND", "FOR", "NEW", "SAN", "LTD", "INC", "CO.")) else w.capitalize()))
    return "".join(out)

def rule_descriptor(name, cls):
    n = (name or "").strip()
    if not n:
        return "Reported line item with no legible asset name"
    if n.upper() == "ASSET NAME":
        return "Transcribed table header row labeled Asset Name"
    if re.search(r"\[ILLEGIBLE", n, re.I):
        return "Unidentified holding or transaction row; source text was illegible"
    m = OPT_RX.match(n)
    if m:
        kind, tick, strike, exp = m.groups()
        return f"{kind.capitalize()} option on {tick.upper()} — ${strike} strike, expires {exp}"
    m_ticker = TICKER_RX.match(n)
    if m_ticker:
        return f"Security identified on the form as {title(m_ticker.group(1))}, ticker {m_ticker.group(2).upper()}"
    if re.search(r"CAPITAL CALL", n, re.I):
        return f"Capital call for private fund / partnership investment — {title(n)}"
    if re.search(r"\b-\s*CC\b|\bCC$", n, re.I) and cls == "Hedge funds & private funds":
        return f"Capital call for private fund / partnership investment — {title(n)}"
    if cls != "Common stock" and re.search(r"COUNTRY CLUB|GOLF|CONDO|COMMERCIAL PROPERTY|LOCATION:", n, re.I):
        return f"Real estate or club/property interest — {title(n)}"
    if re.search(r"STRUCTURED NOTE|TRIGGER PLUS|PARTICIPATION SECURITIES|EURO STOXX", n, re.I):
        return f"Structured note or market-linked security — {title(n)}"
    if cls == "Municipal & gov bonds":
        m2 = MUNI_RX.match(n)
        if m2 and m2.group(2):
            issuer = title(re.sub(r"\b(GO|REV|DB|SCH DIST|SPL)\b.*$", "", m2.group(1)).strip()) or title(m2.group(1))
            cpn = m2.group(2); mat = m2.group(3); mc = MONTH_CODES.get(m2.group(4) or "")
            bits = [f"Municipal bond — {issuer}", f"{cpn}% coupon"]
            if mat: bits.append(f"due {mat}")
            if mc: bits.append(f"pays {mc}")
            return ", ".join(bits)
        return "Municipal / government bond"
    if cls == "Preferred & hybrid securities":
        issuer = title(re.split(r"\b(PFD|HYBRID|PERPETUAL|PREFERRED)\b", n, maxsplit=1, flags=re.I)[0].strip(" ,."))
        return f"Preferred / hybrid perpetual security issued by {issuer}" if issuer else "Preferred / hybrid security"
    if cls == "Structured notes":
        m3 = re.match(r"^(.*?)\s+(?:COMM ?LINKED|LINKED)\s+TO\s+(.*)$", n, re.I)
        if m3:
            return f"Structured note by {title(m3.group(1))} — return linked to {title(m3.group(2))}"
        return "Structured note (bank-issued, index-linked return)"
    if cls == "Common stock":
        base = re.sub(r"\b(CMN|COMMON STOCK|CLASS [AB]|ADR|ADS|SPONSORED|COM)\b\.?", "", n, flags=re.I).strip(" ,.")
        return f"Common stock of {title(base)}" if base else "Common stock"
    if cls == "Hedge funds & private funds":
        return f"Private fund / partnership interest — {title(n)}"
    if cls == "Cash & deposits":
        return "Cash or bank deposit"
    if cls == "Funds & ETFs":
        return f"Investment fund — {title(n)}"
    return f"Reported asset or transaction line item — {title(n)}"

def descriptor(name, cls):
    d = DESCR.get(name)
    if d and not (cls == "Common stock" and d.startswith("Real estate or club/property interest")):
        return d
    return rule_descriptor(name, cls) or ""

# ---------- group normalization ----------
GROUP_ALIASES = {"Ritu Declaration of Trust": "Ritu Ahuja Declaration of Trust"}

def norm_income_types(types):
    return [("N/A" if t.strip().upper() == "NONE" else t.strip().capitalize()) for t in (types or [])]

def norm_tx_type(t):
    return re.sub(r",\s*", ", ", (t or "").strip()) or None

def load_pages(src_dir):
    """Load page-NNN.json files from a directory, sorted, with parse problems returned."""
    import glob
    pages, problems = [], []
    for f in sorted(glob.glob(f"{src_dir}/page-*.json")):
        try:
            with open(f) as fh:
                d = json.load(fh)
        except Exception as e:
            problems.append(f"{f}: {e}")
            continue
        d["_n"] = int(re.search(r"page-(\d+)\.json", f).group(1))
        pages.append(d)
    pages.sort(key=lambda p: p["_n"])
    return pages, problems

def flatten(pages, doc=None):
    """Yield (kind, row_dict) for asset/tx rows with group tracking and normalization."""
    out_assets, out_txs = [], []
    cur_group, prev_group = None, None
    for p in pages:
        for r in p.get("rows") or []:
            if r.get("kind") == "group":
                raw = (r.get("text") or "").strip()
                g = re.sub(r"^[\s\-–—]+", "", raw).strip()
                if raw.startswith("-") and prev_group:
                    cur_group = f"{prev_group} - {g}"
                else:
                    cur_group = g or cur_group
                    prev_group = g or None
                    continue
                prev_group = None
                continue
            prev_group = None
            name = r.get("asset_name") or ""
            cls = classify(name)
            base = {
                "page": p.get("pdf_page", p["_n"]), "label": p.get("printed_label"),
                "group": GROUP_ALIASES.get(cur_group, cur_group), "owner": r.get("owner"),
                "name": name, "cls": cls, "desc": descriptor(name, cls),
            }
            if doc:
                base["doc"] = doc
            if r.get("kind") == "tx":
                lo, hi = bucket_range(r.get("amount"))
                out_txs.append({**base, "tx_type": norm_tx_type(r.get("tx_type")), "cap_gain": bool(r.get("cap_gain_over_200")),
                                "date": r.get("date"), "notification_date": r.get("notification_date"),
                                "amount": r.get("amount"), "lo": lo, "hi": hi})
            else:
                vlo, vhi = bucket_range(r.get("value"))
                amt = r.get("amount_of_income") or r.get("amount_of_income_preceding_year")
                ilo, ihi = bucket_range(amt)
                out_assets.append({**base, "value": r.get("value"), "vlo": vlo, "vhi": vhi,
                                   "income_types": norm_income_types(r.get("income_types")),
                                   "other_income": r.get("other_income_spec"),
                                   "income_amt": amt, "ilo": ilo, "ihi": ihi,
                                   "tx": r.get("transaction")})
    return out_assets, out_txs

def write_data_js(path, payload):
    with open(path, "w") as fh:
        fh.write("window.FD_DATA = ")
        json.dump(payload, fh, separators=(",", ":"))
        fh.write(";")
