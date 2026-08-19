#!/usr/bin/env python3
"""Render static, crawlable HTML for every filing year from templates/index.html.

The explorer is a client-rendered app: without this step the served markup contains
headings and empty containers, so search engines see no figures at all. This writes the
overview content into the HTML at build time, gives each year its own indexable URL,
and generates the matching sitemap.

The latest annual filing is served at "/" and framed as the current standing figure;
every year, including that one, also keeps a permanent "/<year>/" URL. The root year's
own directory canonicalises to "/", so no redirect has to be kept in sync by hand.
"/stock-trades/" is a cross-year hub built from the same transaction data.
"""

from __future__ import annotations

import datetime
import html
import json
import re
import subprocess
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "index.html"
TRADES_TEMPLATE = ROOT / "templates" / "stock-trades.html"
SUMMARIES = ROOT / "site-data" / "summaries.js"
MANIFEST = ROOT / "data" / "manifest.json"
ORIGIN = "https://www.rokhanna.money"
OG_IMAGE = f"{ORIGIN}/assets/og-image.jpg"
SOURCE_INDEX = "https://disclosures-clerk.house.gov/"
TRADES_PATH = "/stock-trades/"
# The normalized dump is ~196 MB and is deliberately kept out of the Vercel deploy by
# .vercelignore, so every dataset link and every schema.org distribution has to resolve
# against the repository rather than this origin.
REPO = "https://github.com/kanetronv2/khanna-disclosure-explorer"
DATA_HOME = f"{REPO}/tree/main/data"
RAW = "https://raw.githubusercontent.com/kanetronv2/khanna-disclosure-explorer/main"

# How many rows of real markup each prerendered table carries. Enough to be substantive
# content for a crawler without bloating the HTML the browser has to parse before hydrating.
RECENT_TX_ON_YEAR_PAGE = 6
RECENT_TX_ON_HUB = 100
TOP_COMPANIES_ON_HUB = 30

OWNER_NAMES = {"SP": "Spouse", "DC": "Dependent children", "JT": "Joint", "UNSPECIFIED": "Not specified"}
OWNER_PHRASE = {"SP": "the member's spouse", "DC": "dependent children", "JT": "joint interests",
                "UNSPECIFIED": "interests with no owner code"}
OWNER_SHORT = {"SP": "spouse", "DC": "dependent child", "JT": "joint", "UNSPECIFIED": "not specified"}
MONTHS = ["January", "February", "March", "April", "May", "June",
          "July", "August", "September", "October", "November", "December"]


# ---------------------------------------------------------------- formatting
# These mirror the fmt$/exact$/rng$/rngS helpers in the template so prerendered
# markup is byte-comparable with what the app renders on load.

def to_fixed(value, digits):
    quantum = Decimal(1).scaleb(-digits)
    return str(Decimal(repr(float(value))).quantize(quantum, rounding=ROUND_HALF_UP))


def fmt(n):
    if n is None:
        return "—"
    if n >= 1e6:
        return "$" + re.sub(r"\.?0+$", "", to_fixed(n / 1e6, 1 if n >= 10e6 else 2)) + "M"
    if n >= 1e3:
        return "$" + str(int(Decimal(repr(float(n / 1e3))).quantize(Decimal(1), rounding=ROUND_HALF_UP))) + "K"
    return "$" + f"{n:,}"


def exact(n):
    return "$" + f"{int(Decimal(repr(float(n))).quantize(Decimal(1), rounding=ROUND_HALF_UP)):,}"


def rng_sum(s):
    """Format a summed {lo, hiF, open, any} range block."""
    if not s.get("any") or (s["lo"] == 0 and s["hiF"] == 0):
        return "None"
    if s["lo"] == s["hiF"]:
        return fmt(s["lo"])
    return f"{fmt(s['lo'])} – {fmt(s['hiF'])}{'+' if s['open'] else ''}"


def rng_pair(lo, hi):
    if lo is None:
        return "—"
    if lo == 0 and hi == 0:
        return "None"
    if hi is None:
        return fmt(lo) + "+"
    return f"{fmt(lo)} – {fmt(hi)}"


def esc(value):
    return html.escape(str(value if value is not None else ""), quote=True)


def num(value):
    """Render a float the way JS String(x) would, for inline style widths."""
    if value == int(value):
        return str(int(value))
    return re.sub(r"0+$", "", f"{value:.6f}").rstrip(".")


# ---------------------------------------------------------------- data access

def load_summaries():
    text = SUMMARIES.read_text(encoding="utf-8")
    prefix = "window.FD_SUMMARIES = "
    if not text.startswith(prefix):
        raise ValueError("site-data/summaries.js does not contain FD_SUMMARIES")
    return json.loads(text[len(prefix):].rstrip().rstrip(";"))


def is_ptr_only(summary):
    return bool((summary.get("meta") or {}).get("ptr_only"))


def caveat(summary):
    """A filing-specific note that must travel with that year's figures, or ''."""
    return (summary.get("meta") or {}).get("caveat") or ""


def annual_years(summaries):
    """Years with an annual holdings statement, matching the timeline chart filter."""
    return [y for y in sorted(summaries) if not is_ptr_only(summaries[y]) and summaries[y]["holdings"]["hiF"] > 0]


def load_transactions(summaries, year, ceiling):
    """Every transaction row for one year, tagged with its year and an ISO sort key."""
    rel = (summaries[year].get("files") or {}).get("transactions")
    path = ROOT / rel if rel else None
    if not path or not path.exists():
        return []
    rows = json.loads(path.read_text(encoding="utf-8"))
    for row in rows:
        row["year"] = year
        row["iso"] = iso_date(row.get("date"), ceiling)
    return rows


def iso_date(value, ceiling=None):
    """A printed filing date -> YYYY-MM-DD, or "" when there is no usable date.

    The forms print both MM/DD/YYYY and MM/DD/YY, and roughly one row in five carries
    neither: some are transcribed "[UNKNOWN]", others carry an OCR-mangled year (2509,
    3210) or a bond maturity date captured in the transaction-date column. A transaction
    cannot have happened after this build, so anything that is not a real calendar date
    at or before `ceiling` is treated as no date at all — a bad read must not lead the
    "most recent" tables or overstate how current the records are. The row still displays
    the date exactly as the form printed it.
    """
    m = re.match(r"^\s*(\d{1,2})/(\d{1,2})/(\d{2}|\d{4})\s*$", str(value or ""))
    if not m:
        return ""
    month, day, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if len(m.group(3)) == 2:
        year += 2000 if year < 70 else 1900
    try:
        datetime.date(year, month, day)
    except ValueError:
        return ""
    iso = f"{year:04d}-{month:02d}-{day:02d}"
    return "" if ceiling and iso > ceiling else iso


# Rows the transcription could not read carry a bracketed placeholder instead of a
# security name. They are real reported rows, so they stay in the counts, but they are not
# securities and must never rank in a "most traded" table.
PLACEHOLDER_NAME = re.compile(r"^\[\s*(ILLEGIBLE|UNKNOWN|ASSET NAME UNCLEAR)", re.I)


def tx_bucket(tx_type):
    """Fold the nine printed transaction types into purchase / sale / other.

    The forms use Purchase, Sale, Partial Sale, Full Sale, Exchange, bare "S", "S(part)"
    and "[UNKNOWN]". Reporting only Purchase and Sale would leave a fifth of the rows
    unaccounted for, so the columns would not add up to the stated total.
    """
    t = str(tx_type or "").strip().lower()
    if "sale" in t or t in ("s", "s(part)"):
        return "sale"
    if t.startswith("purchase") or t == "p":
        return "purchase"
    return "other"


def owner_key(value):
    """Fold owner codes to one vocabulary.

    The forms and the transcription produce SP/DC/JT, lowercase variants, and "[UNKNOWN]"
    on rows that could not be attributed. Left alone, "[UNKNOWN]" leaks into prose.
    """
    code = str(value or "").strip().upper()
    return code if code in ("SP", "DC", "JT") else "UNSPECIFIED"


def pretty_month(iso):
    """2026-06-30 -> "June 2026". Used for the human-readable coverage line."""
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", iso or ""):
        return ""
    return f"{MONTHS[int(iso[5:7]) - 1]} {iso[:4]}"


def build_date():
    """Last-modified date for the schema blocks: the data's own commit date when we have
    one, so a rebuild that changes nothing does not advertise a bogus update."""
    try:
        out = subprocess.run(["git", "-C", str(ROOT), "log", "-1", "--format=%cI"],
                             capture_output=True, text=True, timeout=5)
        if out.returncode == 0 and re.match(r"^\d{4}-\d{2}-\d{2}", out.stdout.strip()):
            return out.stdout.strip()[:10]
    except (OSError, subprocess.SubprocessError):
        pass
    return datetime.date.today().isoformat()


def distributions():
    """Dataset.distribution entries for the published dump, read from the manifest."""
    if not MANIFEST.exists():
        return []
    files = (json.loads(MANIFEST.read_text(encoding="utf-8")) or {}).get("files") or []
    media = {"csv": "text/csv", "jsonl": "application/x-ndjson", "json": "application/json"}
    out = []
    for f in files:
        path, fmt = f.get("path"), (f.get("format") or "").lower()
        if not path or fmt not in media:
            continue
        out.append({"@type": "DataDownload", "encodingFormat": media[fmt],
                    "contentUrl": f"{RAW}/{path}", "name": Path(path).name,
                    "contentSize": str(f.get("bytes", ""))})
    return out


# ---------------------------------------------------------------- cross-year context

class Context:
    """Everything a page needs that is derived from the corpus rather than one year.

    Built once per run so the root framing, the hub and every year page agree, and so
    nothing has to hardcode a year that the next compile will move.
    """

    def __init__(self, summaries):
        self.summaries = summaries
        self.years = sorted(summaries)
        self.annual = annual_years(summaries)
        self.root_year = self.annual[-1]
        # The newest year present in the corpus, not the wall clock: it keeps the "as of"
        # framing honest and keeps the build reproducible.
        self.site_year = self.years[-1]
        self.modified = build_date()
        self.tx = {y: load_transactions(summaries, y, self.modified) for y in self.years}
        self.all_tx = [r for y in self.years for r in self.tx[y]]
        self.tx_total = sum(summaries[y]["counts"]["transactions"] for y in self.years)
        dates = [r["iso"] for r in self.all_tx if r["iso"]]
        self.data_through = max(dates) if dates else ""
        self.undated = sum(1 for r in self.all_tx if not r["iso"])
        self.distributions = distributions()

    def url_for(self, year):
        return "/" if year == self.root_year else f"/{year}/"

    def recent_tx(self, rows, limit):
        return sorted(rows, key=lambda r: (r["iso"], r.get("page") or 0), reverse=True)[:limit]

    def through(self, year):
        """Latest readable transaction date within one filing year."""
        dates = [r["iso"] for r in self.tx[year] if r["iso"]]
        return max(dates) if dates else ""

    def tx_span(self):
        years = [y for y in self.years if self.summaries[y]["counts"]["transactions"]]
        return (years[0], years[-1]) if years else (self.years[0], self.years[-1])


# ---------------------------------------------------------------- components

def story_lead(summary, year):
    tot, tx = summary["holdings"], summary["transaction_total"]
    src = summary.get("source_pdf") or SOURCE_INDEX
    if is_ptr_only(summary):
        eyebrow = "Reported transaction activity"
        headline = f"{summary['counts']['transactions']:,} reported transactions"
        detail = f"Periodic transaction reports for {year}; an annual holdings statement is not yet included."
        caveat_html = ""
    else:
        eyebrow = "Reported household holdings"
        headline = rng_sum(tot)
        detail = (f"Statutory value ranges across {summary['counts']['assets']:,} asset entries — "
                  "not an exact personal net worth.")
        open_note = (f" {tot['open']} open-ended holdings make the upper figure a floor."
                     if tot["open"] else "")
        comparison_note = (" This filing uses a different value-bracket basis and is not directly "
                           "comparable with earlier years." if caveat(summary) else "")
        caveat_html = (f'<p class="story-caveat"><b>Read with care:</b>{esc(open_note + comparison_note)}</p>'
                       if open_note or comparison_note else "")
    return (f'<div class="story-primary"><span class="eyebrow">{esc(eyebrow)}</span>'
            f'<h2>{esc(headline)}</h2><p>{esc(detail)}</p>'
            f'<div class="source-line"><span>Source-linked transcription</span>'
            f'<a href="{esc(src)}" target="_blank" rel="noopener">Official House filing ↗</a></div>'
            f'{caveat_html}</div>')


def stat_cards(summary, year):
    tx = summary["transaction_total"]
    all_docs, annual = summary["all_docs"], summary.get("annual_doc")
    pages = annual["total"] if annual else all_docs["total"]
    tx_card = ("Transaction value", rng_sum(tx), "sum of reported statutory bands", "")
    if is_ptr_only(summary):
        cards = [tx_card,
                 ("Source pages", f"{pages:,}", "transcribed from official scans", ""),
                 ("Filing type", "Periodic reports", "annual holdings are filed later", "")]
    else:
        cards = [("Asset entries", f"{summary['counts']['assets']:,}", "source-linked holdings", ""),
                 tx_card,
                 ("Reported transactions", f"{summary['counts']['transactions']:,}",
                  f"{summary['counts'].get('active_trading_days', 0):,} active trading days", "")]
    return "".join(
        f'<div class="card"{f" title={chr(34)}{esc(tip)}{chr(34)}" if tip else ""}>'
        f'<div class="k">{esc(k)}</div><div class="v">{esc(v)}</div><div class="d">{esc(d)}</div></div>'
        for k, v, d, tip in cards)


def key_findings(summary, year):
    tx = summary["transaction_total"]
    total = summary["counts"]["transactions"]
    dated = summary["counts"].get("dated_transactions", 0)
    days = summary["counts"].get("active_trading_days", 0)
    average = f"{dated / days:,.1f}" if days else "—"
    rows = [
        (f"{days:,}" if days else "—", "active trading days",
         "Distinct calendar dates with at least one reported transaction."
         if days else "No usable transaction dates in this filing year.", "#txs"),
        (average, "average trades per day",
         f"{dated:,} dated transactions across {days:,} active trading days; undated rows are excluded."
         if days else "No usable transaction dates in this filing year.", "#txs"),
        (rng_sum(tx), "combined transaction range",
         "A sum of the statutory transaction buckets, not exact trade values.", "#txs"),
        (f"{total:,}", "reported transactions",
         f"Across all loaded {year} filings; household-wide, not a record of personal trading.", "#txs"),
    ]
    return "".join(f'<article class="finding"><span class="section-kicker">{esc(k)}</span>'
                   f'<strong class="finding-num">{esc(n)}</strong><p>{esc(d)}</p>'
                   f'<a href="{esc(h)}">Inspect evidence →</a></article>' for n, k, d, h in rows)


def ownership(summary):
    rows = summary["owners"]
    if not rows:
        return '<p class="note">No annual holdings are included in this transaction-only year.</p>'
    peak = max([r["lo"] for r in rows] + [1])
    return "".join(
        f'<div class="owner-card"><div class="owner-name">{esc(OWNER_NAMES.get(r["name"], r["name"]))}</div>'
        f'<div class="owner-value">{esc(rng_sum(r))}</div>'
        f'<div class="owner-meta">{r["n"]:,} line-items · minimum {exact(r["lo"])}'
        f'{f" · {r['open']} open-ended" if r["open"] else ""}</div>'
        f'<div class="owner-bar" aria-hidden="true"><span style="width:{num((r["lo"] / peak) * 100)}%"></span></div>'
        f'</div>' for r in rows)


# ---------------------------------------------------------------- prerendered depth
# These mirror the innerHTML the app writes on load, so a crawler sees the same tables a
# reader does. The script replaces each container on hydration, so drift is cosmetic only.

def class_bars(summary, limit=None):
    rows = summary["classes"][:limit] if limit else summary["classes"]
    if not rows:
        return ""
    peak = max([r["hiF"] or r["lo"] for r in rows] + [1])
    out = []
    for r in rows:
        tip = f"min {exact(r['lo'])} · max {exact(r['hiF'])}"
        if r["open"]:
            tip += f" (+{r['open']} holdings with no upper bound)"
        marker = (f'<span class="open-marker" style="left:{num(min(98, max(1, (r["hiF"] / peak) * 100)))}%">→</span>'
                  if r["open"] else "")
        out.append(
            f'<div class="clsrow" title="{esc(tip)}">'
            f'<button class="nm" type="button" data-cls="{esc(r["name"])}">{esc(r["name"])} '
            f'<span class="ct">· {r["n"]}</span></button>'
            f'<div class="barbox" aria-hidden="true">'
            f'<div class="bar max" style="width:{num(max(0.4, (r["hiF"] / peak) * 100))}%"></div>'
            f'<div class="bar" style="width:{num(max(0.4, (r["lo"] / peak) * 100))}%"></div>{marker}</div>'
            f'<span class="rng">{esc(rng_sum(r))}</span></div>')
    return "".join(out)


def class_note(summary):
    rows = summary["classes"]
    if not rows:
        return "No annual holdings are included in this filing year."
    return "Top five categories by reported minimum; select one to filter the Assets tab."


def top_holdings(summary):
    out = []
    for a in summary.get("top_holdings") or []:
        owner = f" · {OWNER_SHORT[owner_key(a['owner'])]}" if a.get("owner") else ""
        page_label = re.sub(r"Page (\d+) of \d+", r"\1", a["label"]) if a.get("label") else str(a.get("page", ""))
        out.append(
            f'<li><span>{esc(a["name"])}<br>'
            f'<span style="color:var(--muted);font-size:11.5px">{esc(a.get("group") or "")}{esc(owner)}</span></span>'
            f'<span class="r">{esc(rng_pair(a.get("vlo"), a.get("vhi")))}<br>'
            f'<a href="#p{esc(a.get("page"))}" data-goto="{esc(a.get("page"))}" style="font-size:11.5px" '
            f'title="View this line on the original disclosure page">View filing p.{esc(page_label)}</a>'
            f'</span></li>')
    return "".join(out)


def groups(summary):
    out = []
    for r in summary.get("groups") or []:
        tip = f"min {exact(r['lo'])} · max {exact(r['hiF'])}" + (f" (+{r['open']} open-ended)" if r["open"] else "")
        out.append(f'<li title="{esc(tip)}"><span>{esc(r["name"])} '
                   f'<span style="color:var(--muted)">· {r["n"]} assets</span></span>'
                   f'<span class="r">{esc(rng_sum(r))}</span></li>')
    return "".join(out)


def tx_summary(summary):
    rows = sorted(summary.get("transaction_types") or [], key=lambda r: r["n"], reverse=True)
    return "".join(f'<li><span>{esc(r["name"])} <span style="color:var(--muted)">· {r["n"]}</span></span>'
                   f'<span class="r">{esc(rng_sum(r))}</span></li>' for r in rows)


def undated_note(rows):
    """State how many rows a "most recent" table cannot place in time.

    Ordering by date quietly hides rows whose printed date is "[UNKNOWN]" or unreadable,
    and staying silent about that would overstate what the table covers.
    """
    n = sum(1 for r in rows if not r["iso"])
    if not n:
        return ""
    return (f" {n:,} of these rows carry no readable transaction date on the filing and cannot be "
            "ordered here; they remain in the full searchable table and the open dataset.")


def tx_table(rows, show_year=False):
    """A real HTML table of transactions — the content that otherwise only exists in JS."""
    if not rows:
        return '<p class="note">No transactions are reported for this filing year.</p>'
    year_head = "<th>Year</th>" if show_year else ""
    body = []
    for r in rows:
        owner = OWNER_SHORT[owner_key(r.get("owner"))]
        # Plain text, not a link: the recent rows skew heavily to the newest year, so
        # linking each one buried the other years under ~100 identical hrefs. The per-year
        # table and the footer already link every year exactly once.
        year_cell = f'<td>{esc(r["year"])}</td>' if show_year else ""
        body.append(
            f"<tr>{year_cell}<td>{esc(r.get('date') or '—')}</td>"
            f"<td>{esc(r.get('name') or '—')}"
            f"<span class=\"tx-desc\">{esc(r.get('desc') or '')}</span></td>"
            f"<td>{esc(r.get('tx_type') or '—')}</td>"
            f"<td class=\"num\">{esc(r.get('amount') or '—')}</td>"
            f"<td>{esc(r.get('cls') or '—')}</td><td>{esc(owner)}</td></tr>")
    return ('<div class="table-scroll"><table class="year-table tx-table">'
            f"<thead><tr>{year_head}<th>Date</th><th>Security</th><th>Type</th>"
            "<th>Reported amount</th><th>Asset class</th><th>Owner</th></tr></thead>"
            f'<tbody>{"".join(body)}</tbody></table></div>')


def tx_preview(rows):
    """A short overview list; the Transactions tab carries the full table and prose."""
    if not rows:
        return '<p class="note">No transactions are reported for this filing year.</p>'
    items = []
    for row in rows:
        page = row.get("page")
        source = (f'<a href="#p{esc(page)}" data-goto="{esc(page)}">View p.{esc(page)}</a>'
                  if page is not None else "")
        meta = " · ".join(value for value in (row.get("date"), row.get("tx_type")) if value)
        items.append(
            f'<li><span><span class="recent-name">{esc(row.get("name") or "—")}</span>'
            f'<span class="recent-meta">{esc(meta)}</span></span>'
            f'<span class="r">{esc(row.get("amount") or "—")}<br>{source}</span></li>')
    return f'<ul class="plain recent-list">{"".join(items)}</ul>'


def position_fact(summary):
    if summary["counts"]["transactions"]:
        return (f"The loaded filing data contains {summary['counts']['transactions']:,} reported transactions "
                f"across reportable family interests, with a combined statutory range of "
                f"{rng_sum(summary['transaction_total'])}.")
    return "The loaded annual filing contains no Schedule B transaction rows for this reporting year."


# ---------------------------------------------------------------- answer block

def material_owners(summary):
    """Owners worth naming in prose: anything that rounds above 0.0% of the reported minimum."""
    tot = summary["holdings"]
    if not tot["lo"]:
        return []
    return [o for o in summary["owners"] if round((o["lo"] / tot["lo"]) * 100, 1) > 0]


def owner_share_sentence(summary):
    tot, owners = summary["holdings"], material_owners(summary)
    if not owners:
        return ""
    parts = [f"{(o['lo'] / tot['lo']) * 100:.1f}% to {OWNER_PHRASE.get(o['name'], o['name'])}" for o in owners[:3]]
    return (" At the reported minimum, owner codes assign "
            + ", ".join(parts[:-1]) + (" and " if len(parts) > 1 else "") + parts[-1] + ".")


def answer_lede(summary, year):
    tot, tx = summary["holdings"], summary["transaction_total"]
    if is_ptr_only(summary):
        return (f"No annual holdings statement for {year} is on file yet, so there is no {year} net-worth range. "
                f"The available transaction reports list <b>{summary['counts']['transactions']:,} trades</b> in "
                f"reported value bands totalling <b>{rng_sum(tx)}</b>.")
    lede = (f"The {year} House filing lists <b>{fmt(tot['lo'])} to {fmt(tot['hiF'])}</b> in household assets "
            f"across {summary['counts']['assets']:,} entries. ")
    if tot["open"]:
        lede += f"{tot['open']} open-ended holdings make the upper figure a floor, not a ceiling. "
    lede += ("The form covers Khanna, his spouse and dependent children, using value bands rather than exact "
             "personal net worth.")
    return lede + owner_share_sentence(summary)


def year_table(summaries, current, url_for):
    rows = []
    for y in annual_years(summaries):
        h = summaries[y]["holdings"]
        cls = ' class="current"' if y == current else ""
        rows.append(
            f'<tr{cls}><td><a href="{url_for(y)}">{y}</a></td>'
            f'<td>{esc(fmt(h["lo"]))}</td>'
            f'<td>{esc(fmt(h["hiF"]))}{"+" if h["open"] else ""}</td>'
            f'<td class="narrow">{h["open"]}</td></tr>')
    return ('<div class="table-scroll"><table class="year-table">'
            '<thead><tr><th>Filing year</th><th>Reported minimum</th><th>Reported maximum</th>'
            '<th>Open-ended holdings</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>'
            + caveat_years_note(summaries, current, url_for)
            + ptr_year_note(summaries, current, url_for))


def caveat_years_note(summaries, current, url_for):
    """Warn, under the cross-year table, about years that are not comparable."""
    years = [y for y in annual_years(summaries) if caveat(summaries[y])]
    if not years:
        return ""
    # On an affected year the explanation sits directly above the table; elsewhere, link to it.
    listed = ", ".join(
        f"<b>{y}</b>" if y == current else f'<a href="{url_for(y)}">{y}</a>' for y in years)
    where = ("see the note above on how that filing reports value brackets"
             if current in years else
             "that filing reports value brackets differently, so the change against other "
             "years is not a change in wealth")
    return f'<p class="note"><b>Not directly comparable:</b> {listed} — {where}.</p>'


def ptr_year_note(summaries, current, url_for):
    """Link the transaction-only years, which have no row in the holdings table."""
    years = [y for y in sorted(summaries) if is_ptr_only(summaries[y])]
    if not years:
        return ""
    links = ", ".join(
        f"<b>{y}</b>" if y == current else f'<a href="{url_for(y)}">{y}</a>' for y in years)
    return (f'<p class="note">Transaction-only years, reported through periodic transaction reports '
            f'rather than an annual holdings statement: {links}.</p>')


def faq_items(summary, year, summaries):
    tot, tx = summary["holdings"], summary["transaction_total"]
    items = []
    if is_ptr_only(summary):
        items.append((f"What is Ro Khanna's net worth in {year}?",
                      f"No annual holdings statement for {year} is on file, so there is no {year} range yet. "
                      f"The latest annual filing ({annual_years(summaries)[-1]}) lists "
                      f"{rng_sum(summaries[annual_years(summaries)[-1]]['holdings'])} in assets."))
    else:
        answer = (f"The {year} filing lists {fmt(tot['lo'])} to {fmt(tot['hiF'])} in household assets. ")
        if tot["open"]:
            answer += f"Its {tot['open']} open-ended holdings mean the upper figure is a floor. "
        answer += "It is a household disclosure using value bands, not a certified personal net-worth figure."
        if caveat(summary):
            answer += " " + caveat(summary)
        items.append((f"What is Ro Khanna's net worth in {year}?", answer))
    if caveat(summary):
        items.append((f"Why do the {year} totals differ so much from earlier years?", caveat(summary)))
    items.append((f"How much stock trading did Ro Khanna report in {year}?",
                  f"The {year} filings list {summary['counts']['transactions']:,} transactions in reported value "
                  f"bands totalling {rng_sum(tx)}. They cover the household and do not identify who made each trade."))
    owners = material_owners(summary)
    if owners:
        breakdown = "; ".join(
            f"{OWNER_NAMES.get(o['name'], o['name'])}: {rng_sum(o)} ({(o['lo'] / tot['lo']) * 100:.1f}% of the "
            f"reported minimum)" for o in owners)
        items.append(("Whose assets are counted in Ro Khanna's disclosure?",
                      f"The filing covers Khanna, his spouse and dependent children. In {year}, owner codes show: "
                      f"{breakdown}. They reflect the form's labels, not a finding on beneficial ownership."))
    items.append(("Where does this data come from?",
                  "We transcribe the official House Clerk scans, check them against OCR, and flag unclear readings. "
                  "This is an independent, unofficial transcription."))
    return items


def answer_panel(summary, year, summaries, url_for):
    # The filing-specific comparison caveat now travels inside the primary summary,
    # where it is seen once instead of being repeated in a separate answer section.
    return ""


def overview_methodology(ctx, summary, year):
    """Keep trust-sensitive guidance and FAQs available without dominating Overview."""
    faqs = "".join(f"<dt>{esc(q)}</dt><dd>{esc(a)}</dd>"
                   for q, a in faq_items(summary, year, ctx.summaries))
    return (
        '<details class="panel reading-panel" id="method">'
        '<summary><span><b>How to read this filing</b>'
        '<small>Ranges, household scope, sourcing, and common questions</small></span></summary>'
        '<div class="reading-body">'
        '<p>House filings are published as paper scans. This independent transcription makes them searchable '
        'while retaining links to the official filing, page scans, and flagged uncertainties.</p>'
        '<ul class="method-list">'
        '<li><b>Ranges, not exact values.</b> Totals sum statutory value bands and are not a certified net worth.</li>'
        '<li><b>Open-ended holdings.</b> A displayed upper total is a floor when a holding has no stated ceiling.</li>'
        '<li><b>Household scope.</b> The filing covers the member, spouse, and dependent children.</li>'
        '<li><b>Independent and unofficial.</b> Verify consequential findings against the linked scans.</li>'
        '</ul>'
        '<div class="faq-heading"><span>FAQ</span><h3>Common questions</h3></div>'
        f'<dl class="faq">{faqs}</dl>'
        f'<p class="note">Dataset through {esc(pretty_month(ctx.data_through) or "the latest loaded filing")}; '
        f'updated <time datetime="{esc(ctx.modified)}">{esc(ctx.modified)}</time>. '
        f'<a href="{DATA_HOME}" target="_blank" rel="noopener">Download CSV and JSONL</a>.</p>'
        '</div></details>')


# ---------------------------------------------------------------- shared sections

def methodology(ctx):
    """Sourcing and method, stated on the page rather than only in the repo README.

    Net-worth queries are trust-sensitive, and provenance is the one thing this site has
    that the aggregators do not.
    """
    return (
        '<section class="panel method-panel" id="method">'
        '<div class="section-heading"><div><h2>How these figures were produced</h2></div></div>'
        '<p>Every number on this site is transcribed from the financial disclosure filings published by the '
        f'<a href="{SOURCE_INDEX}" target="_blank" rel="noopener">Clerk of the U.S. House of Representatives</a>. '
        'Those filings are paper scans with no machine-readable text, so each page was transcribed from '
        'full-page images and high-resolution crops, cross-checked against Tesseract OCR, and annotated where a '
        'reading is uncertain. Every normalized record links back to the page and scan it came from.</p>'
        '<ul class="method-list">'
        '<li><b>Ranges, not exact values.</b> House forms report statutory value bands. Totals here are sums of '
        'those bands and are not a certified net worth.</li>'
        '<li><b>Open-ended holdings.</b> Buckets with no stated ceiling keep a null upper bound and an explicit '
        'flag, so an upper total is a floor, never a maximum.</li>'
        '<li><b>Household scope.</b> Filings cover the member, spouse, and dependent children together. Owner '
        'codes are reproduced as printed and are not a finding about beneficial ownership.</li>'
        '<li><b>Independent and unofficial.</b> This is a best-effort transcription and can contain errors. '
        'Verify consequential findings against the linked scans and the official filings.</li>'
        '</ul>'
        f'<p class="note">Across every filing year, the dataset runs through '
        f'{esc(pretty_month(ctx.data_through) or "the latest loaded filing")}. '
        f'Transcription last updated <time datetime="{esc(ctx.modified)}">{esc(ctx.modified)}</time>. '
        f'The full normalized dump — assets, transactions, pages and flagged uncertainties — is published as '
        f'<a href="{DATA_HOME}" target="_blank" rel="noopener">CSV and JSONL</a> under CC0, alongside the '
        'source PDFs and page scans.</p></section>')


def crosslinks(ctx, year):
    """Hub-and-spoke internal linking: every page reaches the root, the trades hub, and
    its immediate neighbours, so crawl paths do not depend on the JS year selector."""
    years = ctx.years
    i = years.index(year)
    nav = []
    if i > 0:
        nav.append(f'<a class="crosslink prev" href="{ctx.url_for(years[i - 1])}">← {esc(years[i - 1])} filing</a>')
    if i < len(years) - 1:
        nav.append(f'<a class="crosslink next" href="{ctx.url_for(years[i + 1])}">{esc(years[i + 1])} filing →</a>')
    year_links = " ".join(
        f'<b>{esc(y)}</b>' if y == year else f'<a href="{ctx.url_for(y)}">{esc(y)}</a>' for y in years)
    return (
        '<nav class="panel crosslinks" aria-label="Related pages">'
        f'<div class="crosslink-row">{"".join(nav)}</div>'
        '<div class="crosslink-hub">'
        f'<a href="/">Ro Khanna net worth — latest filing</a>'
        f'<a href="{TRADES_PATH}">All reported stock trades, {ctx.tx_span()[0]}–{ctx.tx_span()[1]}</a>'
        '<a href="/api/v1">Machine-readable API</a>'
        f'<a href="{DATA_HOME}" target="_blank" rel="noopener">Download the open dataset</a>'
        '</div>'
        f'<div class="crosslink-years"><span>Every filing year:</span> {year_links}</div></nav>')


def year_options(ctx, year):
    return "".join(f'<option{" selected" if y == year else ""}>{esc(y)}</option>' for y in ctx.years)


# ---------------------------------------------------------------- head + h1

def titles(summary, year, is_root, ctx):
    """Page title, H1 and meta description.

    The root is framed as the standing answer rather than one year's archive: it carries
    the newest year in the corpus so it matches how people search, and says "latest
    filing" in the same breath so it never implies a filing that does not exist.
    """
    tot, tx = summary["holdings"], summary["transaction_total"]
    if is_root:
        span = f"{fmt(tot['lo'])}–{fmt(tot['hiF'])}"
        title = f"Ro Khanna Net Worth {ctx.site_year}: {span} (Latest Filing)"
        h1 = "Ro Khanna Financial Disclosures"
        desc = (f"Ro Khanna's latest House disclosure — the {year} annual filing — reports {span} in assets, "
                f"plus {ctx.tx_total:,} reported stock trades, with source scans.")
    elif is_ptr_only(summary):
        title = f"Ro Khanna Stock Trades {year}: {summary['counts']['transactions']:,} Reported Trades"
        h1 = f"Ro Khanna’s {year} Stock Trades"
        desc = (f"Ro Khanna's {year} periodic transaction reports: {summary['counts']['transactions']:,} trades "
                f"worth {rng_sum(tx)}, transcribed from official U.S. House filings with source scans.")
    else:
        span = f"{fmt(tot['lo'])}–{fmt(tot['hiF'])}"
        title = f"Ro Khanna Net Worth {year}: {span} Reported"
        h1 = f"Ro Khanna’s {year} Financial Disclosure"
        desc = (f"Ro Khanna's {year} House financial disclosure reports {span} in assets across "
                f"{summary['counts']['assets']:,} line-items, plus {summary['counts']['transactions']:,} stock "
                "trades. Searchable, with source scans.")
    return title, h1, desc


def masthead(summary, year, h1):
    kicker = (summary.get("meta") or {}).get("kicker") or f"{year} Financial Disclosure · U.S. House · California 17th"
    return (f'<div class="kicker">{esc(kicker)}</div><h1>{esc(h1)}</h1>'
            '<p class="deck">Source-linked House filings, holdings, and transactions.</p>')


def freshness(ctx, lead, through=None):
    """The provenance line under the H1: what the figures cover, how current the
    underlying records are, and when this transcription last changed.

    A year page reports its own latest record rather than the corpus-wide one, so
    "records through" never describes a year the reader is not looking at.
    """
    bits = [lead]
    through = ctx.data_through if through is None else through
    if through:
        bits.append(f"Records through <b>{esc(pretty_month(through))}</b>")
    bits.append(f'Updated <time datetime="{esc(ctx.modified)}">{esc(ctx.modified)}</time>')
    return f'<p class="freshline">{" · ".join(bits)}</p>'


PUBLISHER = {"@type": "Organization", "name": "Khanna Disclosure Explorer", "url": f"{ORIGIN}/"}
KHANNA = {"@type": "Person", "name": "Ro Khanna", "alternateName": "Rohit Khanna",
          "jobTitle": "U.S. Representative",
          "sameAs": ["https://en.wikipedia.org/wiki/Ro_Khanna", "https://khanna.house.gov/"]}


def json_ld(summary, year, url, title, desc, ctx, is_root):
    api = f"{ORIGIN}/api/v1/years/{year}"
    source_urls = [item.get("url") for item in summary.get("source_documents") or [] if item.get("url")]
    year_distributions = [
        {"@type": "DataDownload", "encodingFormat": "application/json",
         "contentUrl": f"{api}/summary.json", "name": f"{year} calculated facts and provenance"},
        {"@type": "DataDownload", "encodingFormat": "application/json",
         "contentUrl": f"{api}/assets.json", "name": f"{year} source-linked asset entries"},
        {"@type": "DataDownload", "encodingFormat": "application/json",
         "contentUrl": f"{api}/transactions.json", "name": f"{year} source-linked transactions"},
    ]
    dataset = {
        "@context": "https://schema.org",
        "@type": "Dataset",
        "name": f"Ro Khanna {year} Financial Disclosure",
        "description": desc,
        "url": url,
        "creator": PUBLISHER,
        "publisher": PUBLISHER,
        "identifier": f"kde:financial-disclosure:{year}",
        "version": ctx.modified,
        "about": KHANNA,
        "spatialCoverage": "California 17th congressional district",
        "temporalCoverage": year,
        "isBasedOn": source_urls or [summary.get("source_pdf") or SOURCE_INDEX],
        "license": "https://creativecommons.org/publicdomain/zero/1.0/",
        "isAccessibleForFree": True,
        "dateModified": ctx.modified,
        "measurementTechnique": [
            "Transcription of official House financial-disclosure scans",
            "OCR cross-checking with unresolved readings retained as uncertainties",
            "Sum of statutory disclosure-range minimums and maximums",
        ],
        "includedInDataCatalog": {"@type": "DataCatalog",
                                   "name": "Khanna Disclosure Explorer open data",
                                   "url": f"{ORIGIN}/api/v1"},
        "keywords": ["Ro Khanna", "net worth", "stock trades", "financial disclosure",
                     "congressional trading", "U.S. House"],
        "variableMeasured": [
            {"@type": "PropertyValue", "name": "Reported asset value (minimum)",
             "value": summary["holdings"]["lo"], "unitCode": "USD"},
            {"@type": "PropertyValue", "name": "Reported asset value (maximum)",
             "value": summary["holdings"]["hiF"], "unitCode": "USD"},
            {"@type": "PropertyValue", "name": "Reported transactions",
             "value": summary["counts"]["transactions"]},
        ],
        "distribution": year_distributions + ctx.distributions,
    }
    faq = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [{"@type": "Question", "name": q,
                        "acceptedAnswer": {"@type": "Answer", "text": a}}
                       for q, a in faq_items(summary, year, ctx.summaries)],
    }
    crumbs = [{"@type": "ListItem", "position": 1, "name": "Ro Khanna Financial Disclosures", "item": f"{ORIGIN}/"}]
    if not is_root:
        crumbs.append({"@type": "ListItem", "position": 2, "name": f"{year} filing", "item": url})
    breadcrumb = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": crumbs}
    blocks = [dataset, faq, breadcrumb]
    if is_root:
        blocks.append({"@context": "https://schema.org", "@type": "WebSite",
                       "name": "Ro Khanna Financial Disclosure Explorer", "url": f"{ORIGIN}/",
                       "publisher": PUBLISHER, "license":
                       "https://creativecommons.org/publicdomain/zero/1.0/"})
    return "\n".join(
        f'<script type="application/ld+json">\n{json.dumps(block, ensure_ascii=False, indent=2)}\n</script>'
        for block in blocks)


def social_head(url, title, desc):
    """og/twitter tags, identical for every page type."""
    return [
        '<meta property="og:type" content="website">',
        '<meta property="og:site_name" content="Ro Khanna Financial Disclosure Explorer">',
        f'<meta property="og:url" content="{esc(url)}">',
        f'<meta property="og:title" content="{esc(title)}">',
        f'<meta property="og:description" content="{esc(desc)}">',
        f'<meta property="og:image" content="{OG_IMAGE}">',
        '<meta property="og:image:width" content="1200">',
        '<meta property="og:image:height" content="630">',
        '<meta property="og:image:alt" content="Rep. Ro Khanna speaking at a House hearing">',
        '<meta name="twitter:card" content="summary_large_image">',
        f'<meta name="twitter:title" content="{esc(title)}">',
        f'<meta name="twitter:description" content="{esc(desc)}">',
        f'<meta name="twitter:image" content="{OG_IMAGE}">',
        '<meta name="twitter:image:alt" content="Rep. Ro Khanna speaking at a House hearing">',
    ]


def head(summary, year, url, canonical, title, desc, ctx, is_root):
    year_machine_url = f"{ORIGIN}/{year}"
    return "\n".join([
        f"<title>{esc(title)}</title>",
        f'<link rel="canonical" href="{esc(canonical)}">',
        f'<link rel="alternate" type="text/markdown" href="{year_machine_url}/index.md">',
        f'<link rel="alternate" type="application/json" href="{year_machine_url}/facts.json">',
        f'<link rel="describedby" type="application/json" href="{ORIGIN}/api/v1/openapi.json">',
        f'<meta name="description" content="{esc(desc)}">',
        '<meta name="robots" content="index,follow,max-image-preview:large">',
        '<meta name="author" content="Khanna Disclosure Explorer">',
        f'<meta name="last-modified" content="{esc(ctx.modified)}">',
        *social_head(url, title, desc),
        json_ld(summary, year, canonical, title, desc, ctx, is_root),
    ])


# ---------------------------------------------------------------- rendering

def render(template, ctx, year, at_root):
    """Render one year page.

    `at_root` is about the file being written, not the year: the root year is emitted both
    at "/" and at "/<year>/", and the copy in the directory canonicalises to "/" so the two
    never compete. That replaces the hand-maintained redirect, which silently broke every
    time a new annual filing moved the root year.
    """
    summary = ctx.summaries[year]
    is_root = year == ctx.root_year
    url = f"{ORIGIN}/" if at_root else f"{ORIGIN}/{year}/"
    canonical = f"{ORIGIN}/" if is_root else url
    title, h1, desc = titles(summary, year, at_root, ctx)
    recent = ctx.recent_tx(ctx.tx[year], RECENT_TX_ON_YEAR_PAGE)
    replacements = {
        "<!--SEO_HEAD-->": head(summary, year, url, canonical, title, desc, ctx, at_root),
        "<!--SEO_MASTHEAD-->": masthead(summary, year, h1),
        "<!--SEO_FRESHNESS-->": freshness(
            ctx,
            f'Latest annual filing: <a href="/{ctx.root_year}/"><b>{esc(ctx.root_year)}</b></a>' if at_root
            else f"Filing year: <b>{esc(year)}</b>",
            through=None if at_root else ctx.through(year)),
        "<!--SEO_ANSWER-->": answer_panel(summary, year, ctx.summaries, ctx.url_for),
        "<!--SEO_METHOD-->": overview_methodology(ctx, summary, year),
        "<!--SEO_CROSSLINKS-->": crosslinks(ctx, year),
        "<!--PR_STORYLEAD-->": story_lead(summary, year),
        "<!--PR_STATCARDS-->": stat_cards(summary, year),
        "<!--PR_KEYFINDINGS-->": key_findings(summary, year),
        "<!--PR_OWNERSHIP-->": ownership(summary),
        "<!--PR_CLSBARS-->": class_bars(summary, limit=5),
        "<!--PR_CLASSNOTE-->": esc(class_note(summary)),
        "<!--PR_TOPHOLD-->": top_holdings(summary),
        "<!--PR_GROUPS-->": groups(summary),
        "<!--PR_TXSUM-->": tx_summary(summary),
        "<!--PR_RECENT_TX-->": tx_preview(recent),
        "<!--PR_YEAR_TABLE-->": year_table(ctx.summaries, year, ctx.url_for),
        "<!--PR_RECENT_TX_COUNT-->": esc(f"{len(recent):,}"),
        "<!--PR_UNDATED_NOTE-->": esc(undated_note(ctx.tx[year])),
        "<!--PR_YEAR_OPTIONS-->": year_options(ctx, year),
        "<!--PR_TRADES_PATH-->": TRADES_PATH,
        "<!--PR_POSITION_YEAR-->": esc(year),
        "<!--PR_POSITION_FACT-->": esc(position_fact(summary)),
        "@@ROOT_YEAR@@": ctx.root_year,
    }
    out = template
    for token, value in replacements.items():
        if token not in out:
            raise ValueError(f"template is missing placeholder {token}")
        out = out.replace(token, value)
    return out


# ---------------------------------------------------------------- stock trades hub

def hub_year_rows(ctx):
    rows = []
    for y in ctx.years:
        s = ctx.summaries[y]
        if not s["counts"]["transactions"]:
            continue
        buckets = defaultdict(int)
        for r in ctx.tx[y]:
            buckets[tx_bucket(r.get("tx_type"))] += 1
        rows.append(
            f'<tr><td><a href="{ctx.url_for(y)}">{esc(y)}</a></td>'
            f'<td class="num">{s["counts"]["transactions"]:,}</td>'
            f'<td class="num">{buckets["purchase"]:,}</td>'
            f'<td class="num">{buckets["sale"]:,}</td>'
            f'<td class="num">{buckets["other"]:,}</td>'
            f'<td>{esc(rng_sum(s["transaction_total"]))}</td></tr>')
    return ('<div class="table-scroll"><table class="year-table">'
            "<thead><tr><th>Filing year</th><th>Reported trades</th><th>Purchases</th><th>Sales</th>"
            "<th>Other or unread</th><th>Combined reported value</th></tr></thead>"
            f'<tbody>{"".join(rows)}</tbody></table></div>')


def hub_companies(ctx):
    """Most frequently traded securities across every year, by row count."""
    agg = defaultdict(lambda: {"n": 0, "lo": 0, "hi": 0, "years": set(), "cls": ""})
    for r in ctx.all_tx:
        name = (r.get("name") or "").strip()
        if not name or PLACEHOLDER_NAME.match(name):
            continue
        a = agg[name]
        a["n"] += 1
        a["lo"] += r.get("lo") or 0
        a["hi"] += r.get("hi") or 0
        a["years"].add(r["year"])
        a["cls"] = a["cls"] or (r.get("cls") or "")
    top = sorted(agg.items(), key=lambda kv: kv[1]["n"], reverse=True)[:TOP_COMPANIES_ON_HUB]
    rows = "".join(
        f"<tr><td>{esc(name)}</td><td>{esc(a['cls'] or '—')}</td>"
        f'<td class="num">{a["n"]:,}</td>'
        f'<td class="num">{esc(rng_pair(a["lo"], a["hi"]))}</td>'
        f'<td>{esc(min(a["years"]))}–{esc(max(a["years"]))}</td></tr>' for name, a in top)
    return ('<div class="table-scroll"><table class="year-table">'
            "<thead><tr><th>Security</th><th>Asset class</th><th>Trades</th>"
            "<th>Summed reported value</th><th>Years</th></tr></thead>"
            f"<tbody>{rows}</tbody></table></div>")


def unreadable_note(ctx):
    """Say how many rows were left out of the ranking because the security name could not
    be read. Dropping them silently would make the transcription look cleaner than it is."""
    n = sum(1 for r in ctx.all_tx if PLACEHOLDER_NAME.match((r.get("name") or "").strip()))
    if not n:
        return ""
    return (f" {n:,} rows whose security name could not be read from the scan are excluded from this "
            "ranking; they are still counted in every total above and flagged in the dataset.")


def hub_classes(ctx):
    agg = defaultdict(lambda: {"n": 0, "lo": 0, "hi": 0})
    for r in ctx.all_tx:
        a = agg[(r.get("cls") or "Unclassified").strip() or "Unclassified"]
        a["n"] += 1
        a["lo"] += r.get("lo") or 0
        a["hi"] += r.get("hi") or 0
    rows = sorted(agg.items(), key=lambda kv: kv[1]["n"], reverse=True)
    peak = max([a["n"] for _, a in rows] + [1])
    return "".join(
        f'<div class="clsrow"><span class="nm">{esc(name)} <span class="ct">· {a["n"]:,}</span></span>'
        f'<div class="barbox" aria-hidden="true">'
        f'<div class="bar" style="width:{num(max(0.4, (a["n"] / peak) * 100))}%"></div></div>'
        f'<span class="rng">{esc(rng_pair(a["lo"], a["hi"]))}</span></div>' for name, a in rows)


def hub_owner_split(ctx):
    agg = defaultdict(int)
    for r in ctx.all_tx:
        agg[owner_key(r.get("owner"))] += 1
    rows = sorted(agg.items(), key=lambda kv: kv[1], reverse=True)
    total = sum(n for _, n in rows) or 1
    return "".join(
        f'<li><span>{esc(OWNER_NAMES.get(k, k))}</span>'
        f'<span class="r">{n:,} · {(n / total) * 100:.1f}%</span></li>' for k, n in rows)


def hub_faq(ctx):
    first, last = ctx.tx_span()
    latest = ctx.summaries[ctx.years[-1]]
    owners = defaultdict(int)
    for r in ctx.all_tx:
        owners[owner_key(r.get("owner"))] += 1
    top_owner = max(owners.items(), key=lambda kv: kv[1]) if owners else ("UNSPECIFIED", 0)
    share = (top_owner[1] / max(len(ctx.all_tx), 1)) * 100
    return [
        ("Does Ro Khanna trade stocks?",
         f"The disclosures list {ctx.tx_total:,} transactions from {first} to {last}. They cover Khanna, his "
         "spouse and dependent children, so a listed trade does not show who directed it."),
        ("How many stock trades has Ro Khanna reported?",
         f"{ctx.tx_total:,} across {first}–{last}. The latest year ({ctx.years[-1]}) has "
         f"{latest['counts']['transactions']:,}, in reported value bands totalling "
         f"{rng_sum(latest['transaction_total'])}."),
        ("Whose trades appear in Ro Khanna's disclosures?",
         f"The forms label interests by owner code. Across loaded filings, "
         f"{OWNER_NAMES.get(top_owner[0], top_owner[0]).lower()} account for {share:.1f}% of rows. "
         "Those labels do not establish beneficial ownership or who placed an order."),
        ("Has Ro Khanna supported a congressional stock trading ban?",
         "Yes. A December 2023 Khanna proposal would bar members of Congress from holding or trading individual "
         "stocks. This site presents that position with the filings; it does not allege wrongdoing."),
        ("Where does this trade data come from?",
         "We transcribe official House Clerk scans, cross-check them with OCR, and link each row to its source. "
         "Amounts are the form's value bands, not exact trade values."),
    ]


def render_hub(template, ctx):
    first, last = ctx.tx_span()
    url = f"{ORIGIN}{TRADES_PATH}"
    title = f"Ro Khanna Stock Trades: {ctx.tx_total:,} Reported, {first}–{last}"
    h1 = f"Ro Khanna’s Reported Stock Trades: {ctx.tx_total:,} Transactions, {first}–{last}"
    desc = (f"Every stock trade in Ro Khanna's House disclosures: {ctx.tx_total:,} reported transactions, "
            f"{first}–{last}, with dates, amounts and owner codes from the official filings.")
    faqs = hub_faq(ctx)
    crumbs = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "Ro Khanna Financial Disclosures", "item": f"{ORIGIN}/"},
        {"@type": "ListItem", "position": 2, "name": "Stock trades", "item": url}]}
    dataset = {
        "@context": "https://schema.org", "@type": "Dataset",
        "name": f"Ro Khanna reported stock trades, {first}–{last}",
        "description": desc, "url": url, "creator": PUBLISHER, "publisher": PUBLISHER, "about": KHANNA,
        "temporalCoverage": f"{first}/{last}", "isBasedOn": SOURCE_INDEX,
        "license": "https://creativecommons.org/publicdomain/zero/1.0/",
        "isAccessibleForFree": True, "dateModified": ctx.modified,
        "identifier": "kde:reported-stock-trades", "version": ctx.modified,
        "measurementTechnique": ["Transcription of official House disclosure scans",
                                   "OCR cross-checking with explicit uncertainty flags"],
        "keywords": ["Ro Khanna", "stock trades", "congressional trading", "periodic transaction report"],
        "variableMeasured": [{"@type": "PropertyValue", "name": "Reported transactions",
                              "value": ctx.tx_total}],
        "distribution": ctx.distributions,
    }
    faq_ld = {"@context": "https://schema.org", "@type": "FAQPage",
              "mainEntity": [{"@type": "Question", "name": q,
                              "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faqs]}
    head_html = "\n".join([
        f"<title>{esc(title)}</title>",
        f'<link rel="canonical" href="{esc(url)}">',
        f'<link rel="alternate" type="text/markdown" href="{ORIGIN}/stock-trades/index.md">',
        f'<link rel="describedby" type="application/json" href="{ORIGIN}/api/v1/openapi.json">',
        f'<meta name="description" content="{esc(desc)}">',
        '<meta name="robots" content="index,follow,max-image-preview:large">',
        '<meta name="author" content="Khanna Disclosure Explorer">',
        f'<meta name="last-modified" content="{esc(ctx.modified)}">',
        *social_head(url, title, desc),
        *(f'<script type="application/ld+json">\n{json.dumps(b, ensure_ascii=False, indent=2)}\n</script>'
          for b in (dataset, faq_ld, crumbs)),
    ])
    year_links = " ".join(f'<a href="{ctx.url_for(y)}">{esc(y)}</a>' for y in ctx.years)
    replacements = {
        "<!--HUB_HEAD-->": head_html,
        "<!--HUB_H1-->": esc(h1),
        "<!--HUB_KICKER-->": esc(f"Reported transactions · U.S. House · California 17th · {first}–{last}"),
        "<!--HUB_FRESHNESS-->": freshness(ctx, f"Filing years: <b>{esc(first)}–{esc(last)}</b>"),
        "<!--HUB_LEDE-->": hub_lede(ctx),
        "<!--HUB_YEAR_TABLE-->": hub_year_rows(ctx),
        "<!--HUB_RECENT_TX-->": tx_table(ctx.recent_tx(ctx.all_tx, RECENT_TX_ON_HUB), show_year=True),
        "<!--HUB_RECENT_COUNT-->": esc(f"{min(RECENT_TX_ON_HUB, len(ctx.all_tx)):,}"),
        "<!--HUB_UNDATED_NOTE-->": esc(undated_note(ctx.all_tx)),
        "<!--HUB_COMPANIES-->": hub_companies(ctx),
        "<!--HUB_COMPANY_COUNT-->": esc(f"{TOP_COMPANIES_ON_HUB:,}"),
        "<!--HUB_UNREAD_NOTE-->": esc(unreadable_note(ctx)),
        "<!--HUB_CLASSES-->": hub_classes(ctx),
        "<!--HUB_OWNERS-->": hub_owner_split(ctx),
        "<!--HUB_FAQ-->": "".join(f"<dt>{esc(q)}</dt><dd>{esc(a)}</dd>" for q, a in faqs),
        "<!--HUB_METHOD-->": methodology(ctx),
        "<!--HUB_YEAR_LINKS-->": year_links,
        "<!--HUB_TOTAL-->": esc(f"{ctx.tx_total:,}"),
        "<!--HUB_DATA_HOME-->": DATA_HOME,
    }
    out = template
    for token, value in replacements.items():
        if token not in out:
            raise ValueError(f"stock-trades template is missing placeholder {token}")
        out = out.replace(token, value)
    return out


def hub_lede(ctx):
    first, last = ctx.tx_span()
    owners = defaultdict(int)
    for r in ctx.all_tx:
        owners[owner_key(r.get("owner"))] += 1
    total = max(len(ctx.all_tx), 1)
    parts = sorted(owners.items(), key=lambda kv: kv[1], reverse=True)[:3]
    split = ", ".join(f"{(n / total) * 100:.1f}% to {OWNER_PHRASE[k]}" for k, n in parts)
    return (f"The House filings list <b>{ctx.tx_total:,} transactions</b> from {first} to {last}. They cover "
            "Khanna, his spouse and dependent children—reported activity, not a record of individual decisions. "
            f"By owner code: {split}. Amounts are value bands, not exact trade values.")


# ---------------------------------------------------------------- site files

def write_sitemap(ctx):
    """Every canonical URL with a lastmod. changefreq/priority are omitted: Google ignores
    both, and a stale priority is worse than none."""
    paths = ["/", TRADES_PATH, "/stock-trades/index.md", "/llms.txt", "/llms-full.txt",
             "/api/v1", "/api/v1/openapi.json", "/api/v1/years.json", "/api/v1/issuers.json"]
    issuer_registry = json.loads((ROOT / "lib" / "issuer-registry.json").read_text(encoding="utf-8"))
    for issuer in issuer_registry:
        slug = issuer["slug"]
        paths.extend((f"/api/v1/issuers/{slug}.json", f"/api/v1/issuers/{slug}.txt"))
        featured = issuer.get("featured_comparison") or []
        if len(featured) == 2:
            stem = f"/api/v1/issuers/{slug}/comparisons/{featured[0]}-{featured[1]}"
            paths.extend((f"{stem}.json", f"{stem}.txt"))
    paths += [f"/{y}/" for y in sorted(ctx.years, reverse=True) if y != ctx.root_year]
    paths += [path for y in sorted(ctx.years, reverse=True)
              for path in (f"/{y}/index.md", f"/{y}/facts.json")]
    body = "\n".join(
        f"  <url>\n    <loc>{ORIGIN}{p}</loc>\n    <lastmod>{ctx.modified}</lastmod>\n  </url>" for p in paths)
    (ROOT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{body}\n</urlset>\n", encoding="utf-8")
    return len(paths)


def write_404(ctx):
    links = "".join(f'<li><a href="{ctx.url_for(y)}">{esc(y)} filing</a></li>' for y in reversed(ctx.years))
    (ROOT / "404.html").write_text(
        '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "<title>Page not found — Ro Khanna Financial Disclosure Explorer</title>\n"
        '<meta name="robots" content="noindex,follow">\n'
        '<link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 '
        'viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>💸</text></svg>">\n'
        "<style>body{margin:0;padding:64px 24px;font:15px/1.6 -apple-system,BlinkMacSystemFont,"
        '"Segoe UI",Roboto,Helvetica,Arial,sans-serif;color:#16181d;background:#fafafa}'
        "main{max-width:640px;margin:0 auto}h1{font-size:26px;letter-spacing:-.015em;margin:0 0 8px}"
        "p{color:#667085}a{color:#1e40af}ul{padding-left:20px}li{margin:4px 0}</style>\n</head>\n<body>\n"
        "<main>\n<h1>Page not found</h1>\n"
        "<p>That URL is not part of this site. The explorer publishes one page per filing year, "
        "plus a cross-year view of every reported transaction.</p>\n"
        f'<p><a href="/">Ro Khanna net worth — latest filing</a><br>\n'
        f'<a href="{TRADES_PATH}">All reported stock trades</a></p>\n'
        f"<h2>Filing years</h2>\n<ul>{links}</ul>\n</main>\n</body>\n</html>\n", encoding="utf-8")


def main():
    ctx = Context(load_summaries())
    template = TEMPLATE.read_text(encoding="utf-8")

    (ROOT / "index.html").write_text(render(template, ctx, ctx.root_year, True), encoding="utf-8")
    pages = 1
    for year in ctx.years:
        directory = ROOT / year
        directory.mkdir(exist_ok=True)
        (directory / "index.html").write_text(render(template, ctx, year, False), encoding="utf-8")
        pages += 1

    hub_dir = ROOT / TRADES_PATH.strip("/")
    hub_dir.mkdir(exist_ok=True)
    (hub_dir / "index.html").write_text(
        render_hub(TRADES_TEMPLATE.read_text(encoding="utf-8"), ctx), encoding="utf-8")
    pages += 1

    urls = write_sitemap(ctx)
    write_404(ctx)
    print(f"pages: {pages} rendered (root = {ctx.root_year}, as of {ctx.site_year}); "
          f"transactions: {ctx.tx_total:,}; sitemap: {urls} urls; modified: {ctx.modified}")


if __name__ == "__main__":
    main()
