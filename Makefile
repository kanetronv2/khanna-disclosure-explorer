.PHONY: open-data audit pages llm-access llm-check indexnow

open-data:
	python3 ocr/compile.py
	python3 docs/compile17.py
	python3 scripts/build_open_data.py --check
	python3 scripts/build_asset_comparison.py
	python3 scripts/build_site_data.py
	python3 scripts/build_pages.py
	python3 scripts/build_llm_access.py
	python3 scripts/check_llm_access.py

audit:
	python3 scripts/build_open_data.py --check
	python3 scripts/build_asset_comparison.py
	python3 scripts/build_site_data.py
	python3 scripts/build_pages.py
	python3 scripts/build_llm_access.py
	python3 scripts/check_llm_access.py

# Re-render the static pages and sitemap from templates/index.html.
pages:
	python3 scripts/build_pages.py
	python3 scripts/build_llm_access.py
	python3 scripts/check_llm_access.py

llm-access:
	python3 scripts/build_llm_access.py

llm-check:
	python3 scripts/check_llm_access.py

indexnow:
	python3 scripts/submit_indexnow.py
