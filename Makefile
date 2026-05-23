.PHONY: install dev-api dev-worker test eval help

help:
	@echo "Targets: install dev-api dev-worker test eval"

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
