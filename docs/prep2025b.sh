#!/bin/zsh
# One-off prep for docs/src/2025-14.pdf (the 2025 Annual Form A, Clerk ID 9116272).
#
# Differs from prep2025.sh in two ways, on purpose:
#   - scoped to the single new document, so the 13 existing 2025 PTR docs are not re-rendered;
#   - NO sips -r 270 rotation - unlike the sideways 2025 PTR scans, the annual's pages are
#     already upright (792x610.56pt landscape, rot=0). Do not run prep2025.sh on this doc.
set -e
cd "$(dirname "$0")/.."
doc=2025-14
f=docs/src/$doc.pdf
mkdir -p docs/$doc/pages docs/$doc/hires docs/$doc/tess docs/$doc/text
pdftoppm -jpeg -r 150 -jpegopt quality=80 $f docs/$doc/pages/page
pdftoppm -png -r 300 -gray $f docs/$doc/hires/page
echo "rendered"
# zero-pad
python3 - <<PY
import os, re, glob
for f in glob.glob("docs/$doc/*/page-*.*"):
    d, b = os.path.split(f)
    m = re.match(r"page-(\d+)\.(\w+)$", b)
    if m and len(m.group(1)) < 3:
        os.rename(f, os.path.join(d, f"page-{int(m.group(1)):03d}.{m.group(2)}"))
PY
# quad crops (same geometry as crop2025.py, scoped to this doc; threads because a
# ProcessPoolExecutor cannot spawn workers from a heredoc __main__ on macOS)
python3 - <<PY
import glob, sys
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, "docs")
from crop2025 import crop_page
pages = sorted(glob.glob("docs/$doc/hires/*.png"))
with ThreadPoolExecutor(max_workers=8) as ex:
    list(ex.map(crop_page, pages))
print("CROP_DONE", len(pages))
PY
ls docs/$doc/hires/*.png | xargs -I {} -P 8 sh -c 'd=$(dirname $(dirname {})); b=$(basename {} .png); tesseract {} $d/tess/$b 2>/dev/null'
echo "PREP2025B_DONE pages=$(ls docs/$doc/pages/*.jpg | wc -l | tr -d ' ') tess=$(ls docs/$doc/tess/*.txt | wc -l | tr -d ' ')"
