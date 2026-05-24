.PHONY: install dev-api dev-worker test eval sonar-up sonar-scan help

help:
	@echo "Targets: install dev-api dev-worker test eval sonar-up sonar-scan"

install:
	uv sync

dev-api:
	uv run uvicorn app.api.main:app --reload --port 8000

dev-worker:
	uv run python -m app.worker

test:
	uv run pytest

eval:
	uv run python evals/run_evals.py

sonar-up:
	docker compose -f docker-compose.sonar.yml up -d

sonar-scan:
	./scripts/sonar-scan.sh
