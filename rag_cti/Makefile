.PHONY: install install-dev test lint fmt type-check qdrant-up qdrant-down clean

install:
	pip install -e .

install-dev:
	pip install -e ".[dev]"

test:
	pytest

test-fast:
	pytest -x --no-cov

lint:
	ruff check src/ tests/

fmt:
	ruff format src/ tests/

type-check:
	mypy src/

qdrant-up:
	docker compose up -d qdrant

qdrant-down:
	docker compose down

qdrant-logs:
	docker compose logs -f qdrant

seed-mitre:
	python scripts/seed_mitre.py

bootstrap-qdrant:
	python scripts/bootstrap_qdrant.py

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; \
	find . -name "*.pyc" -delete 2>/dev/null; \
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov; \
	true
