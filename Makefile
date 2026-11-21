.DEFAULT_GOAL := help
.PHONY: help setup test lint fmt check

help: ## List targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "}; {printf "  make %-8s %s\n", $$1, $$2}'

setup: ## Install Python 3.13 and all dependencies into .venv
	uv sync

test: ## Run the tests
	uv run pytest -q

lint: ## Lint and type-check
	uv run ruff check .
	uv run pyright

fmt: ## Format code and apply safe lint fixes
	uv run ruff format .
	uv run ruff check --fix .

check: ## Everything CI runs: format check, lint, types, tests
	uv run ruff format --check .
	uv run ruff check .
	uv run pyright
	uv run pytest -q
