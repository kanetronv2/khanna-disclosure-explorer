#!/usr/bin/env python3
"""Schedule B counterpart to docs/xmarks.py — measures tx-type / cap-gain / amount columns.

Same geometric approach: the 300-dpi hires PNG is thresholded, the grid is recovered from
long horizontal/vertical ink runs, and each checkbox cell is measured. Schedule B has a
different column map from Schedule A (20 detected vlines, not 38) and its marks are
lowercase "x" printing lighter than Schedule A's, so it uses its own ink thresholds -
see THRESHOLD and CG_THRESHOLD below, both derived from the measured ink distribution.

Usage: python3 docs/bmarks.py <page> [doc]
NOTE: rows[] includes group-header rows, so it aligns with the FULL page-JSON rows list.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
from PIL import Image

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "docs"))
from xmarks import ink, runs  # identical grid/cell measurement

TX = ["Purchase", "Sale", "Partial Sale", "Exchange"]
AMT = ["$1,001-$15,000", "$15,001-$50,000", "$50,001-$100,000", "$100,001-$250,000",
       "$250,001-$500,000", "$500,001-$1,000,000", "$1,000,001-$5,000,000",
       "$5,000,001-$25,000,000", "$25,000,001-$50,000,000", "Over $50,000,000",
       "Over $1,000,000 (Spouse/DC Asset)"]

# Empirically separated over 51,480 measured Schedule B cells in 2025-14: cells the
# transcription marks read 0.071 at the lowest, unmarked cells 0.058 at the highest.
# 0.065 sits in that gap - it clears the scanner specks that sat just above the original
# 0.05 (0.051-0.058) without dropping any real mark.
THRESHOLD = 0.065

# The cap-gain box is a single isolated checkbox rather than one of a row of buckets, so it
# picks up no neighbouring grid ink: across 2025-14 unmarked cells measure 0.000 flat while
# marked ones start at 0.061. A lighter threshold is both safe and necessary here - the
# 0.065 above would drop the faintest real marks.
CG_THRESHOLD = 0.03


def analyze(page, root=None):
    root = root or os.path.join(REPO, "docs", "2025-14")
    im = Image.open(f"{root}/hires/page-{page:03d}.png").convert("L")
    d = np.array(im) < 128
    H, W = d.shape
    hlines = runs(d.sum(axis=1) > 0.55 * W)
    if len(hlines) < 5:
        return {"page": page, "error": "no grid"}
    gaps = [hlines[i + 1] - hlines[i] for i in range(len(hlines) - 1)]
    big = int(np.argmax(gaps))
    bot = hlines[-1]
    span = bot - hlines[big + 1]
    vlines = runs(d[hlines[big + 1]:bot, :].sum(axis=0) > 0.75 * span)
    rows = [(hlines[i], hlines[i + 1]) for i in range(big + 1, len(hlines) - 1)
            if 30 <= hlines[i + 1] - hlines[i] <= 70]
    out = {"page": page, "n_rows": len(rows), "n_vlines": len(vlines), "vlines": vlines, "rows": []}
    v = vlines
    # Normally 20 rules: edge | owner | asset | 4 tx-type | cap-gain | date | 11 amounts.
    # On some sheets the owner/asset divider is too faint to detect, giving 19; the tell is
    # a full asset-name-width gap between the first two rules. Shift the map rather than
    # skip the page - the owner column is only used for an informational ink reading.
    off = 0
    if len(v) == 19 and v[1] - v[0] > 900:
        off = 1
    elif len(v) != 20:
        out["error"] = "unexpected vline count"
        return out
    owner = (v[0], v[1]) if not off else None
    namec = (v[1 - off], v[2 - off])
    txcols = [(v[2 - off + i], v[3 - off + i]) for i in range(4)]
    cg, date = (v[6 - off], v[7 - off]), (v[7 - off], v[8 - off])
    acols = [(v[8 - off + i], v[9 - off + i]) for i in range(11)]
    for i, (y0, y1) in enumerate(rows):
        r = {"i": i, "y": [y0, y1],
             "owner_ink": round(ink(d, y0, y1, *owner), 3) if owner else None,
             "name_ink": round(ink(d, y0, y1, *namec), 3),
             "cg_ink": round(ink(d, y0, y1, *cg), 3),
             "date_ink": round(ink(d, y0, y1, *date), 3)}
        T = [round(ink(d, y0, y1, *c), 3) for c in txcols]
        A = [round(ink(d, y0, y1, *c), 3) for c in acols]
        r["tx"] = [TX[j] for j, x in enumerate(T) if x > THRESHOLD]
        r["amt"] = [AMT[j] for j, x in enumerate(A) if x > THRESHOLD]
        r["capgain"] = r["cg_ink"] > CG_THRESHOLD
        faint = [f"{blk}:{names[j]}:{x}" for blk, arr, names in (("T", T, TX), ("A", A, AMT))
                 for j, x in enumerate(arr) if 0.02 < x <= THRESHOLD]
        if faint:
            r["faint"] = faint
        r["raw"] = {"T": T, "A": A}
        out["rows"].append(r)
    return out


if __name__ == "__main__":
    print(json.dumps(analyze(int(sys.argv[1]),
                             os.path.join(REPO, "docs", sys.argv[2]) if len(sys.argv) > 2 else None)))
