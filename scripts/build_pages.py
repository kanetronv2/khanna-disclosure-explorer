#!/usr/bin/env python3
"""Render static, crawlable HTML for every filing year from templates/index.html.

The explorer is a client-rendered app: without this step the served markup contains
headings and empty containers, so search engines see no figures at all. This writes the
overview content into the HTML at build time, gives each year its own indexable URL,
and generates the matching sitemap.

The newest annual filing is served at "/"; every other year lives at "/<year>/".
"""

from __future__ import annotations

import html
import json
import re
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "index.html"
SUMMARIES = ROOT / "site-data" / "summaries.js"
ORIGIN = "https://www.rokhanna.money"
OG_IMAGE = f"{ORIGIN}/assets/og-image.jpg"
SOURCE_INDEX = "https://disclosures-clerk.house.gov/"

OWNER_NAMES = {"SP": "Spouse", "DC": "Dependent children", "JT": "Joint", "UNSPECIFIED": "Not specified"}
OWNER_PHRASE = {"SP": "the member's spouse", "DC": "dependent children", "JT": "joint interests",
                "UNSPECIFIED": "interests with no owner code"}


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


def annual_years(summaries):
    """Years with an annual holdings statement, matching the timeline chart filter."""
    return [y for y in sorted(summaries) if not is_ptr_only(summaries[y]) and summaries[y]["holdings"]["hiF"] > 0]


# ---------------------------------------------------------------- components

def story_lead(summary, year):
    tot, tx = summary["holdings"], summary["transaction_total"]
    src = summary.get("source_pdf") or SOURCE_INDEX
    if is_ptr_only(summary):
        eyebrow = f"{year} periodic transaction reports"
        headline = f"{summary['counts']['transactions']:,} reported transactions"
        detail = ("This year currently contains periodic transaction reports rather than an annual "
                  f"holdings statement. The combined reported transaction range is {rng_sum(tx)}.")
        facts = [("Combined transaction range", rng_sum(tx)),
                 ("Reportable transactions", f"{summary['counts']['transactions']:,}"),
                 ("Source pages", f"{summary['all_docs']['done']} / {summary['all_docs']['total']} transcribed")]
    else:
        eyebrow = f"{year} disclosed holdings"
        headline = f"Up to {fmt(tot['hiF'])} reported"
        detail = (f"The filing’s statutory ranges sum to {fmt(tot['lo'])} at the low end and "
                  f"{fmt(tot['hiF'])} at the calculated upper end across "
                  f"{summary['counts']['assets']:,} line-items. ")
        if tot["open"]:
            detail += (f"Because {tot['open']} holdings have no stated ceiling, this dashboard figure "
                       "is not a hard upper limit and the reported value may be higher. ")
        detail += "These are disclosure-range sums, not an exact personal net worth."
        facts = [("Calculated upper floor", f"{fmt(tot['hiF'])}{'+' if tot['open'] else ''}"),
                 ("Open-ended holdings", f"{tot['open']:,}"),
                 ("Reported transactions", f"{summary['counts']['transactions']:,}")]
    aside = "".join(f'<div class="aside-fact"><span>{esc(k)}</span><strong>{esc(v)}</strong></div>' for k, v in facts)
    return (f'<div class="story-primary"><span class="eyebrow">{esc(eyebrow)}</span>'
            f'<h2>{esc(headline)}</h2><p>{esc(detail)}</p>'
            f'<div class="source-line"><span>Source-linked transcription</span>'
            f'<a href="{esc(src)}" target="_blank" rel="noopener">Official House filing ↗</a></div></div>'
            f'<div class="story-aside">{aside}</div>')


def stat_cards(summary, year):
    tot, inc, tx = summary["holdings"], summary["income"], summary["transaction_total"]
    all_docs, annual = summary["all_docs"], summary.get("annual_doc")
    if annual:
        doc_card = ("Document status", f"{annual['done']} / {annual['total']} annual pages",
                    f"all loaded filings: {all_docs['done']} / {all_docs['total']} pages", "")
    else:
        doc_card = ("Document status", f"{all_docs['done']} / {all_docs['total']} pages",
                    "all loaded filings transcribed from official scans", "")
    tx_card = (f"Transaction value ({year})", rng_sum(tx),
               f"{summary['counts']['transactions']:,} reported transactions", "")
    if is_ptr_only(summary):
        cards = [tx_card, ("Filing type", "Periodic reports",
                           "annual holdings are filed the following spring", ""), doc_card]
    else:
        cards = [(f"Unearned income ({year})", rng_sum(inc),
                  f"dividends, interest, gains, rent · min {exact(inc['lo'])}", ""), tx_card, doc_card]
    return "".join(
        f'<div class="card"{f" title={chr(34)}{esc(tip)}{chr(34)}" if tip else ""}>'
        f'<div class="k">{esc(k)}</div><div class="v">{esc(v)}</div><div class="d">{esc(d)}</div></div>'
        for k, v, d, tip in cards)


def key_findings(summary, year):
    tot, tx = summary["holdings"], summary["transaction_total"]
    owners = summary["owners"]
    if is_ptr_only(summary):
        rows = [
            (f"{summary['counts']['transactions']:,}", "reported transactions",
             f"Across all loaded {year} periodic reports.", "#txs"),
            (rng_sum(tx), "combined transaction range",
             "A sum of the statutory transaction buckets, not exact trade values.", "#txs"),
            (f"{summary['all_docs']['total']:,}", "source pages",
             f"{summary['all_docs']['done']:,} pages transcribed and linked to the structured data.", "#doc"),
        ]
    else:
        top = (summary.get("top_holdings") or [None])[0]
        lead = owners[0] if owners else None
        share = f"{(lead['lo'] / tot['lo']) * 100:.1f}%" if lead and tot["lo"] else "—"
        share_label = (f"of the minimum assigned to {OWNER_NAMES.get(lead['name'], lead['name']).lower()}"
                       if lead else "ownership attribution unavailable")
        rows = [
            (f"{tot['open']}", "open-ended holdings",
             "The calculated upper total remains a floor because these buckets have no stated ceiling.",
             "#assets?val=1000001"),
            (rng_pair(top.get("vlo"), top.get("vhi")) if top else "—", "largest individual range",
             top["name"] if top else "No holding rows were reported.", "#assets"),
            (f"{summary['counts']['transactions']:,}", "reported transactions",
             f"Combined statutory value range: {rng_sum(tx)}.", "#txs"),
            (share, share_label,
             "Based on owner codes printed in the filing, not inferred beneficial ownership.",
             "#panel-ownership"),
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
    return (" Measured against the reported minimum, the filing's owner codes assign "
            + ", ".join(parts[:-1]) + (" and " if len(parts) > 1 else "") + parts[-1] + ".")


def answer_lede(summary, year):
    tot, tx = summary["holdings"], summary["transaction_total"]
    if is_ptr_only(summary):
        return (f"Rep. Ro Khanna's {year} filings currently consist of periodic transaction reports rather than "
                f"an annual holdings statement, so no {year} net worth range is reported yet. Those reports cover "
                f"<b>{summary['counts']['transactions']:,} transactions</b> with a combined statutory value of "
                f"<b>{rng_sum(tx)}</b>. The annual statement covering {year} is filed the following spring.")
    lede = (f"Rep. Ro Khanna's {year} U.S. House financial disclosure reports assets totalling "
            f"<b>{fmt(tot['lo'])} to {fmt(tot['hiF'])}</b> across {summary['counts']['assets']:,} line-items. ")
    if tot["open"]:
        lede += (f"Because {tot['open']} holdings are disclosed only as open-ended buckets with no stated ceiling, "
                 "the upper number is a floor rather than a true maximum. ")
    lede += ("House filings report statutory value ranges, not exact amounts, and they cover the member, spouse "
             "and dependent children together — so this is a disclosure range, not a certified personal net worth.")
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
            + ptr_year_note(summaries, current, url_for))


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
                      f"No annual holdings statement covering {year} has been filed yet, so no {year} range exists. "
                      f"The most recent annual filing, for {annual_years(summaries)[-1]}, reports "
                      f"{rng_sum(summaries[annual_years(summaries)[-1]]['holdings'])} in assets."))
    else:
        answer = (f"Khanna's {year} House financial disclosure reports assets in a combined range of "
                  f"{fmt(tot['lo'])} to {fmt(tot['hiF'])}, summed from the statutory value bands on the form. ")
        if tot["open"]:
            answer += (f"{tot['open']} holdings are reported as open-ended, so the upper figure is a floor. ")
        answer += ("The disclosure covers the member, spouse and dependent children, and reports ranges rather "
                   "than exact values, so it is not a certified personal net worth.")
        items.append((f"What is Ro Khanna's net worth in {year}?", answer))
    items.append((f"How much stock trading did Ro Khanna report in {year}?",
                  f"The {year} filings record {summary['counts']['transactions']:,} reported transactions with a "
                  f"combined statutory value of {rng_sum(tx)}. Reported transactions cover the member, spouse and "
                  "dependent children, and do not establish who directed any individual trade."))
    owners = material_owners(summary)
    if owners:
        breakdown = "; ".join(
            f"{OWNER_NAMES.get(o['name'], o['name'])}: {rng_sum(o)} ({(o['lo'] / tot['lo']) * 100:.1f}% of the "
            f"reported minimum)" for o in owners)
        items.append(("Whose assets are counted in Ro Khanna's disclosure?",
                      f"House rules require members to report reportable interests of the filer, spouse and "
                      f"dependent children. In the {year} filing the owner codes break down as — {breakdown}. "
                      "Owner codes are what the form prints; they are not a finding about beneficial ownership."))
    items.append(("Where does this data come from?",
                  "Every figure is transcribed from the official filings published by the Clerk of the U.S. House "
                  "of Representatives. The filings are paper scans with no machine-readable text, so each page is "
                  "transcribed and cross-checked against OCR, with uncertain readings flagged against the source "
                  "scan. This is an independent, unofficial transcription."))
    return items


def answer_panel(summary, year, summaries, url_for):
    faqs = "".join(f"<dt>{esc(q)}</dt><dd>{esc(a)}</dd>" for q, a in faq_items(summary, year, summaries))
    return ('<section class="panel answer-panel" id="answer">'
            '<div class="section-heading"><div><span class="section-kicker">In brief</span>'
            f'<h2>Ro Khanna’s reported net worth, {year}</h2></div></div>'
            f'<p class="answer-lede">{answer_lede(summary, year)}</p>'
            '<h3>Reported holdings by filing year</h3>'
            f'{year_table(summaries, year, url_for)}'
            '<h3>Frequently asked questions</h3>'
            f'<dl class="faq">{faqs}</dl></section>')


# ---------------------------------------------------------------- head + h1

def titles(summary, year, is_root):
    tot, tx = summary["holdings"], summary["transaction_total"]
    if is_ptr_only(summary):
        title = f"Ro Khanna Stock Trades {year}: {summary['counts']['transactions']:,} Reported Trades"
        h1 = f"Ro Khanna’s {year} Stock Trades: {summary['counts']['transactions']:,} Reported Transactions"
        desc = (f"Ro Khanna's {year} periodic transaction reports: {summary['counts']['transactions']:,} trades "
                f"worth {rng_sum(tx)}, transcribed from official U.S. House filings with source scans.")
    else:
        span = f"{fmt(tot['lo'])}–{fmt(tot['hiF'])}"
        title = (f"Ro Khanna Net Worth: {span} ({year} Filing)" if is_root
                 else f"Ro Khanna Net Worth {year}: {span} Reported")
        h1 = f"Ro Khanna Net Worth: {span} in Reported Holdings ({year} Disclosure)"
        desc = (f"Ro Khanna's {year} House financial disclosure reports {span} in assets across "
                f"{summary['counts']['assets']:,} line-items, plus {summary['counts']['transactions']:,} stock "
                "trades. Searchable, with source scans.")
    return title, h1, desc


def masthead(summary, year, h1):
    kicker = (summary.get("meta") or {}).get("kicker") or f"{year} Financial Disclosure · U.S. House · California 17th"
    return (f'<div class="kicker">{esc(kicker)}</div><h1>{esc(h1)}</h1>'
            '<p class="deck">A source-linked view of holdings, income, and transactions reported for the '
            'member, spouse, and dependent children.</p>')


def json_ld(summary, year, url, title, desc, summaries, is_root):
    dataset = {
        "@context": "https://schema.org",
        "@type": "Dataset",
        "name": f"Ro Khanna {year} Financial Disclosure",
        "description": desc,
        "url": url,
        "creator": {"@type": "Organization", "name": "Khanna Disclosure Explorer"},
        "about": {"@type": "Person", "name": "Ro Khanna", "alternateName": "Rohit Khanna",
                  "jobTitle": "U.S. Representative"},
        "spatialCoverage": "California 17th congressional district",
        "temporalCoverage": year,
        "isBasedOn": summary.get("source_pdf") or SOURCE_INDEX,
        "license": "https://creativecommons.org/publicdomain/zero/1.0/",
        "variableMeasured": [
            {"@type": "PropertyValue", "name": "Reported asset value (minimum)",
             "value": summary["holdings"]["lo"], "unitCode": "USD"},
            {"@type": "PropertyValue", "name": "Reported asset value (maximum)",
             "value": summary["holdings"]["hiF"], "unitCode": "USD"},
            {"@type": "PropertyValue", "name": "Reported transactions",
             "value": summary["counts"]["transactions"]},
        ],
    }
    faq = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [{"@type": "Question", "name": q,
                        "acceptedAnswer": {"@type": "Answer", "text": a}}
                       for q, a in faq_items(summary, year, summaries)],
    }
    crumbs = [{"@type": "ListItem", "position": 1, "name": "Ro Khanna Financial Disclosures", "item": f"{ORIGIN}/"}]
    if not is_root:
        crumbs.append({"@type": "ListItem", "position": 2, "name": f"{year} filing", "item": url})
    breadcrumb = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": crumbs}
    return "\n".join(
        f'<script type="application/ld+json">\n{json.dumps(block, ensure_ascii=False, indent=2)}\n</script>'
        for block in (dataset, faq, breadcrumb))


def head(summary, year, url, title, desc, summaries, is_root):
    return "\n".join([
        f"<title>{esc(title)}</title>",
        f'<link rel="canonical" href="{esc(url)}">',
        f'<meta name="description" content="{esc(desc)}">',
        '<meta name="robots" content="index,follow,max-image-preview:large">',
        '<meta name="author" content="Khanna Disclosure Explorer">',
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
        json_ld(summary, year, url, title, desc, summaries, is_root),
    ])


# ---------------------------------------------------------------- rendering

def render(template, summaries, year, root_year):
    summary = summaries[year]
    is_root = year == root_year

    def url_for(y):
        return "/" if y == root_year else f"/{y}/"

    url = f"{ORIGIN}/" if is_root else f"{ORIGIN}/{year}/"
    title, h1, desc = titles(summary, year, is_root)
    replacements = {
        "<!--SEO_HEAD-->": head(summary, year, url, title, desc, summaries, is_root),
        "<!--SEO_MASTHEAD-->": masthead(summary, year, h1),
        "<!--SEO_ANSWER-->": answer_panel(summary, year, summaries, url_for),
        "<!--PR_STORYLEAD-->": story_lead(summary, year),
        "<!--PR_STATCARDS-->": stat_cards(summary, year),
        "<!--PR_KEYFINDINGS-->": key_findings(summary, year),
        "<!--PR_OWNERSHIP-->": ownership(summary),
        "<!--PR_POSITION_YEAR-->": esc(year),
        "<!--PR_POSITION_FACT-->": esc(position_fact(summary)),
        "@@ROOT_YEAR@@": root_year,
    }
    out = template
    for token, value in replacements.items():
        if token not in out:
            raise ValueError(f"template is missing placeholder {token}")
        out = out.replace(token, value)
    return out


def write_sitemap(summaries, root_year):
    entries = [("/", "1.0", "weekly")]
    for y in sorted(summaries, reverse=True):
        if y == root_year:
            continue
        freq = "weekly" if y >= "2025" else "monthly"
        entries.append((f"/{y}/", "0.8" if y >= "2023" else "0.6", freq))
    body = "\n".join(
        f"  <url>\n    <loc>{ORIGIN}{path}</loc>\n"
        f"    <changefreq>{freq}</changefreq>\n    <priority>{prio}</priority>\n  </url>"
        for path, prio, freq in entries)
    (ROOT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{body}\n</urlset>\n", encoding="utf-8")
    return len(entries)


def main():
    template = TEMPLATE.read_text(encoding="utf-8")
    summaries = load_summaries()
    root_year = annual_years(summaries)[-1]

    (ROOT / "index.html").write_text(render(template, summaries, root_year, root_year), encoding="utf-8")
    pages = 1
    for year in sorted(summaries):
        if year == root_year:
            continue
        directory = ROOT / year
        directory.mkdir(exist_ok=True)
        (directory / "index.html").write_text(render(template, summaries, year, root_year), encoding="utf-8")
        pages += 1

    urls = write_sitemap(summaries, root_year)
    print(f"pages: {pages} rendered (root = {root_year}); sitemap: {urls} urls")


if __name__ == "__main__":
    main()
