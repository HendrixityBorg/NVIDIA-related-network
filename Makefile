SNAPSHOT ?= data/snapshot_2026-08-25.json

.PHONY: install build delivery-audit test validate compile smoke api

install:
	python3 -m venv .venv
	.venv/bin/pip install -e '.[dev]'

test:
	.venv/bin/pytest

build:
	.venv/bin/python scripts/build_snapshot_v2.py \
		--entity-registry-overlay runs/2026-08-25-run-003/agents/non_npn_listing_audit/researched_entity_registry_overlay.jsonl \
		--entity-registry-overlay runs/2026-08-25-run-003/agents/npn_listed_parent_resolution/listed_entity_registry_overlay.jsonl \
		--entity-registry-overlay runs/2026-08-25-run-003/agents/partner_regulatory_entity_normalization/entity_registry_overlay.jsonl \
		--entity-registry-overlay runs/2026-08-25-run-003/agents/partner_regulatory_entity_normalization/sec_cik_entity_registry_overlay.jsonl \
		--entity-merge-map runs/2026-08-25-run-003/agents/partner_regulatory_entity_normalization/entity_merge_map.jsonl
	.venv/bin/python scripts/audit_delivery.py

delivery-audit:
	.venv/bin/python scripts/audit_delivery.py

validate:
	.venv/bin/python scripts/validate_snapshot.py --snapshot $(SNAPSHOT)

compile:
	.venv/bin/python -m compileall -q src scripts tests runs/2026-08-25-run-003

smoke:
	.venv/bin/python -m arti.cli company NVDA
	.venv/bin/python -m arti.cli relationships --company NVDA --limit 1
	.venv/bin/python -m arti.cli evidence --limit 1

api:
	.venv/bin/uvicorn arti.api:app --host 127.0.0.1 --port 8000
