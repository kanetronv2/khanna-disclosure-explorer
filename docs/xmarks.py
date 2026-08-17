#!/usr/bin/env python3
"""Report X-mark columns per data row for a Form A schedule_a page.

Pixel-measures each checkbox cell from the 300-dpi hires PNG, so the Block B/C/D
column a mark sits in is determined geometrically rather than by eye. Cross-checked
against 113 independently transcribed 2025-14 pages: 2,592 value cells compared,
one disagreement, which the scan confirmed as a transcription error (p.57 ELI LILLY).

Usage: python3 docs/xmarks.py <page> [doc]   e.g. python3 docs/xmarks.py 143 2025-14
NOTE: rows[] includes group-header rows, so it aligns with the FULL rows list in the
page JSON (group + asset), not just the asset rows.

Output per row: row index, owner-ink, name-ink, list of (block,col) with X.
Column maps are derived from detected vlines; verified for the schedule_a layout.
"""
import sys, json
import numpy as np
from PIL import Image

import os
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC = sys.argv[2] if len(sys.argv) > 2 else "2025-14"
ROOT = os.path.join(REPO, "docs", DOC)

VAL = ["None","$1-$1,000","$1,001-$15,000","$15,001-$50,000","$50,001-$100,000",
       "$100,001-$250,000","$250,001-$500,000","$500,001-$1,000,000",
       "$1,000,001-$5,000,000","$5,000,001-$25,000,000","$25,000,001-$50,000,000",
       "Over $50,000,000","Spouse/DC Asset over $1,000,000"]
INC = ["NONE","DIVIDENDS","RENT","INTEREST","CAPITAL GAINS","EXCEPTED/BLIND TRUST",
       "TAX-DEFERRED","OTHER"]
AMT = ["None","$1-$200","$201-$1,000","$1,001-$2,500","$2,501-$5,000","$5,001-$15,000",
       "$15,001-$50,000","$50,001-$100,000","$100,001-$1,000,000",
       "$1,000,001-$5,000,000","Over $5,000,000",
       "Spouse/DC Asset with income over $1,000,000"]

def runs(mask, min_gap=3):
    idx = np.where(mask)[0]
    if len(idx) == 0: return []
    groups = []; start = prev = idx[0]
    for i in idx[1:]:
        if i - prev > min_gap:
            groups.append((start, prev)); start = i
        prev = i
    groups.append((start, prev))
    return [int((a+b)//2) for a,b in groups]

def ink(d, y0, y1, x0, x1, pad=5):
    # measure only the central region of the cell to avoid border bleed
    h, w = y1 - y0, x1 - x0
    yc0, yc1 = y0 + int(0.22*h), y1 - int(0.22*h)
    xc0, xc1 = x0 + int(0.25*w), x1 - int(0.25*w)
    sub = d[yc0:yc1, xc0:xc1]
    if sub.size == 0: return 0.0
    return float(sub.mean())

def analyze(page, root=None):
    root = root or ROOT
    im = Image.open(f"{root}/hires/page-{page:03d}.png").convert("L")
    d = np.array(im) < 128
    H, W = d.shape
    hcount = d.sum(axis=1)
    hlines = runs(hcount > 0.55 * W)
    if len(hlines) < 5:
        return {"page": page, "error": "no grid", "hlines": hlines}
    gaps = [hlines[i+1]-hlines[i] for i in range(len(hlines)-1)]
    big = int(np.argmax(gaps))  # tall bucket-label header
    top, bot = hlines[0], hlines[-1]
    vcount = d[hlines[big+1]:bot, :].sum(axis=0)
    span = bot - hlines[big+1]
    vlines = runs(vcount > 0.75 * span)
    # data rows: after the tall header; skip the ASSET NAME header row (gap>60)
    rows = []
    for i in range(big+1, len(hlines)-1):
        g = hlines[i+1]-hlines[i]
        if 30 <= g <= 70:
            rows.append((hlines[i], hlines[i+1]))
    out = {"page": page, "n_rows": len(rows), "vlines": vlines, "rows": []}
    # column x-boundaries (expected layout; verify against vlines)
    # find block boundaries: name col ends ~1123, EIF 1123-1181, B: 13 cols, C: 8, D: 12, E: last
    v = vlines
    out["n_vlines"] = len(v)
    if len(v) != 38:
        out["warn"] = "unexpected vline count"
    try:
        owner = (v[0], v[1])
        namec = (v[1], v[2])
        eif   = (v[2], v[3])
        bcols = [(v[3+i], v[4+i]) for i in range(13)]      # v[3]..v[16]
        ccols = [(v[16+i], v[17+i]) for i in range(8)]     # v[16]..v[24]
        dcols = [(v[24+i], v[25+i]) for i in range(12)]    # v[24]..v[36]
        ecol  = (v[36], v[37])
    except IndexError:
        out["error"] = "vline layout"
        return out
    for ri, (y0, y1) in enumerate(rows):
        r = {"i": ri, "y": [y0, y1]}
        r["owner_ink"] = round(ink(d, y0, y1, *owner), 3)
        r["name_ink"] = round(ink(d, y0, y1, *namec), 3)
        r["eif_ink"] = round(ink(d, y0, y1, *eif), 3)
        B = [round(ink(d, y0, y1, *c), 3) for c in bcols]
        C = [round(ink(d, y0, y1, *c), 3) for c in ccols]
        D = [round(ink(d, y0, y1, *c), 3) for c in dcols]
        r["E_ink"] = round(ink(d, y0, y1, *ecol), 3)
        th = 0.10
        r["value"] = [VAL[i] for i, x in enumerate(B) if x > th]
        r["inc"] = [INC[i] for i, x in enumerate(C) if x > th]
        r["amt"] = [AMT[i] for i, x in enumerate(D) if x > th]
        faint = []
        for blk, arr, names in (("B",B,VAL),("C",C,INC),("D",D,AMT)):
            for i2, x2 in enumerate(arr):
                if 0.03 < x2 <= th:
                    faint.append(f"{blk}:{names[i2]}:{x2}")
        if faint: r["faint"] = faint
        r["raw"] = {"B": B, "C": C, "D": D}
        out["rows"].append(r)
    return out

if __name__ == "__main__":
    print(json.dumps(analyze(int(sys.argv[1]))))
