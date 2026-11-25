#!/bin/zsh
set -e
cd /Users/multivac/Code/khanna
for f in docs/src/2026-*.pdf; do
  doc=$(basename $f .pdf)
  mkdir -p docs/$doc/pages docs/$doc/hires docs/$doc/tess docs/$doc/text
  pdftoppm -jpeg -r 150 -jpegopt quality=80 $f docs/$doc/pages/page
  pdftoppm -png -r 300 -gray $f docs/$doc/hires/page
done
echo "rendered in source PDF orientation"
# zero-pad
python3 - <<'PY'
import os, re, glob
for f in glob.glob("docs/2026-*/*/page-*.*"):
    d, b = os.path.split(f)
    m = re.match(r"page-(\d+)\.(\w+)$", b)
    if m and len(m.group(1)) < 3:
        os.rename(f, os.path.join(d, f"page-{int(m.group(1)):03d}.{m.group(2)}"))
PY
python3 docs/crop2026.py
ls docs/2026-*/hires/*.png | xargs -I {} -P 8 sh -c 'd=$(dirname $(dirname {})); b=$(basename {} .png); tesseract {} $d/tess/$b 2>/dev/null'
echo "PREP2026_DONE tess=$(ls docs/2026-*/tess/*.txt | wc -l)"
