.PHONY: install dev-api dev-worker test coverage eval eval-reset sonar-up sonar-scan sonar-test help

help:
	@echo "Targets: install dev-api dev-worker test coverage eval eval-reset sonar-up sonar-scan sonar-test"

install:
	uv sync

dev-api:
	uv run uvicorn app.api.main:app --reload --port 8000

dev-worker:
	uv run python -m app.worker

test:
	uv run pytest

coverage:
	uv run pytest --cov=app --cov-report=term-missing --cov-report=html --cov-report=xml

eval:
	uv run python evals/run_evals.py

eval-reset:
	uv run python -m evals.reset

sonar-up:
	docker compose -f docker-compose.sonar.yml up -d

ifeq ($(OS),Windows_NT)
sonar-scan:
	powershell -NoProfile -ExecutionPolicy Bypass -File scripts/sonar-scan.ps1
sonar-test:
	powershell -NoProfile -ExecutionPolicy Bypass -File scripts/sonar-integration-test.ps1
else
sonar-scan:
	./scripts/sonar-scan.sh
sonar-test:
	./scripts/sonar-integration-test.sh
endif
