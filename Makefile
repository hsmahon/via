.PHONY: help bootstrap dev build lint format typecheck test docstrings check smoke down logs clean

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

bootstrap: ## Install Python + Node dependencies and set up .env
	uv sync --all-packages
	cp -n .env.example .env || true
	npm ci

dev: ## Start the full local stack (build if needed)
	docker compose up --build --wait

build: ## Build all Docker images without starting them
	docker compose build

lint: ## Run all linters (ruff, eslint, prettier)
	uv run ruff check .
	uv run ruff format --check .
	npm run lint
	npm run format:check

format: ## Auto-format Python (ruff) and JS/TS (prettier)
	uv run ruff check --fix .
	uv run ruff format .
	npm run format

typecheck: ## Run mypy (production sources + meta-tests) and tsc
	uv run mypy backend/db/src backend/api/src backend/agent/harness/src backend/agent/observability/src backend/agent/prompts/src backend/agent/tools/src backend/agent/service/src backend/workers/video-processing-worker/src tests
	npm run typecheck

test: ## Run pytest and vitest
	uv run pytest
	npm test

docstrings: ## Enforce docstring presence/style (interrogate + docstring tests + eslint JSDoc)
	uv run interrogate -v backend tests
	uv run pytest tests/test_docstrings.py tests/test_docstring_validity.py -m docstring
	npm run docstrings:test

check: lint typecheck docstrings test ## Everything except docker build

smoke: ## Run the end-to-end smoke test against a running stack
	./scripts/smoke.sh

down: ## Stop the local stack
	docker compose down

logs: ## Tail logs from all services
	docker compose logs -f --tail=100

clean: ## Remove caches and build artifacts
	rm -rf .pytest_cache .mypy_cache .ruff_cache .venv frontend/ui/.next frontend/ui/node_modules node_modules
	find . -type d -name __pycache__ -exec rm -rf {} +
