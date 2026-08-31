.PHONY: install test verify-case serve

install:
	python -m pip install -e '.[dev]'

test:
	pytest

verify-case:
	listed-company-network verify-case --manifest case_studies/nvidia/case_manifest.json

serve:
	LCN_DATA_PATH=case_studies/nvidia/frozen_2026-08-25/data/snapshot_2026-08-25.json listed-company-network serve
