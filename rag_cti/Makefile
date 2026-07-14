.PHONY: install install-dev test test-fast lint fmt fmt-check type-check ci \
        qdrant-up qdrant-down qdrant-logs \
        seed-mitre seed-relationships seed-pdfs fetch-otx fetch-otx-mitre-actor-raw fetch-whois ingest ingest-all \
        rebuild-otx \
        eval-attribution eval-capabilities eval-techniquerag certify render-results \
        eval-all clean

install:
	pip install -e .

install-dev:
	pip install -e ".[dev]"

test:
	pytest

test-fast:
	pytest -x --no-cov

lint:
	ruff check src/ tests/ scripts/

fmt:
	ruff format src/ tests/ scripts/

fmt-check:
	ruff format --check src/ tests/ scripts/

type-check:
	mypy src/

# Local CI: mirrors the GitHub workflow — lint + format + type + test all gate.
ci: lint fmt-check type-check test

qdrant-up:
	docker compose up -d qdrant

qdrant-down:
	docker compose down

qdrant-logs:
	docker compose logs -f qdrant

# ── Ingestion ────────────────────────────────────────────────────────
seed-mitre:
	python scripts/seed_mitre.py

seed-relationships:
	python scripts/seed_mitre_relationships.py

seed-pdfs:
	python scripts/seed_pdfs.py

fetch-otx:
	python scripts/fetch_otx_mitre_actor_raw.py

fetch-otx-mitre-actor-raw:
	python scripts/fetch_otx_mitre_actor_raw.py

# Requires WHOXY_API_KEY and a domains file: make fetch-whois DOMAINS=domains.txt
fetch-whois:
	python scripts/fetch_whois.py --domains $(DOMAINS)

ingest:
	python scripts/ingest.py

# Full corpus rebuild: seed every source then embed+upsert into Qdrant.
ingest-all: seed-mitre seed-relationships seed-pdfs fetch-otx
	python scripts/ingest.py --sources mitre mitre_relationships otx pdfs

# Rebuild data/processed/otx.jsonl from data/raw/otx/ with the canonical
# connector rendering (no API calls). Ingest into a NEW collection for A/B:
#   make rebuild-otx && python scripts/ingest.py --sources otx --collection cti_chunks_v3
rebuild-otx:
	python scripts/rebuild_otx_jsonl.py

# ── Evaluation ───────────────────────────────────────────────────────
eval-attribution:
	python scripts/eval_attribution.py --query-set data/eval/query_set_v3.jsonl \
		--output data/eval/attribution_v3_results.json

eval-capabilities:
	python scripts/eval_capabilities.py

eval-techniquerag:
	python scripts/eval_techniquerag.py --max-records 50

certify:
	python scripts/certify_annotator.py --provider deepseek

render-results:
	python scripts/render_results.py

# The certification trio + README refresh in one shot (real LLM calls; long).
# COLLECTION optionally overrides the Qdrant collection for all three stages.
eval-all:
	python scripts/certify_annotator.py --provider deepseek $(if $(COLLECTION),--collection $(COLLECTION))
	python scripts/eval_attribution.py --query-set data/eval/query_set_v3.jsonl \
		--output data/eval/attribution_v3_results.json $(if $(COLLECTION),--collection $(COLLECTION))
	python scripts/eval_capabilities.py --ragas $(if $(COLLECTION),--collection $(COLLECTION))
	python scripts/render_results.py --write

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; \
	find . -name "*.pyc" -delete 2>/dev/null; \
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov; \
	true
