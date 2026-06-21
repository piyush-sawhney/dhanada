.PHONY: help install install-dev test test-unit test-integration lint format format-check typecheck security migrate upgrade-db downgrade-db run generate-kek clean ci

help:
	@echo "Dhanada Backend - Development Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make install       Install production dependencies"
	@echo "  make install-dev   Install with dev dependencies"
	@echo "  make generate-kek  Generate KEK for envelope encryption"
	@echo ""
	@echo "Development:"
	@echo "  make test          Run tests with coverage"
	@echo "  make lint          Run ruff linter"
	@echo "  make format        Format code with ruff"
	@echo "  make typecheck     Run mypy type checker"
	@echo "  make security      Run security scans (bandit, pip-audit, detect-secrets)"
	@echo ""
	@echo "Database:"
	@echo "  make migrate       Create new migration (usage: make migrate msg='add table')"
	@echo "  make upgrade-db    Apply migrations"
	@echo "  make downgrade-db  Revert last migration"
	@echo ""
	@echo "Run:"
	@echo "  make run           Start development server"
	@echo ""
	@echo "Maintenance:"
	@echo "  make clean         Remove build artifacts"

install:
	pip install -e .

install-dev:
	pip install -e ".[dev]"
	pre-commit install

test:
	python -m pytest

test-unit:
	python -m pytest tests/unit -v

test-integration:
	python -m pytest tests/integration -v

lint:
	python -m ruff check src tests

format:
	python -m ruff format src tests

format-check:
	python -m ruff format --check src tests

typecheck:
	python -m mypy src

security:
	python -m bandit -r src -ll
	pip-audit
	detect-secrets scan --all-files

migrate:
	python -m alembic revision --autogenerate -m "$(msg)"

upgrade-db:
	python -m alembic upgrade head

downgrade-db:
	python -m alembic downgrade -1

run:
	python -m uvicorn dhanada.main:app --reload --host 0.0.0.0 --port 8000

generate-kek:
	python scripts/generate_kek.py

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name ".coverage" -delete
	rm -rf htmlcov dist build *.egg-info 2>/dev/null || true

ci: lint format-check typecheck security test
	@echo "All CI checks passed!"