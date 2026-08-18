.PHONY: open-data audit pages

open-data:
	python3 ocr/compile.py
	python3 docs/compile17.py
	python3 scripts/build_open_data.py --check
	python3 scripts/build_asset_comparison.py
	python3 scripts/build_site_data.py
	python3 scripts/build_pages.py

audit:
	python3 scripts/build_open_data.py --check
	python3 scripts/build_asset_comparison.py
	python3 scripts/build_site_data.py
	python3 scripts/build_pages.py

# Re-render the static pages and sitemap from templates/index.html.
pages:
	python3 scripts/build_pages.py
