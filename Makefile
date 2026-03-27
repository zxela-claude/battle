.PHONY: install dev test build clean lint help

VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## Create venv and install package with dev deps
	python3 -m venv $(VENV)
	$(PIP) install -e ".[dev]"

dev: ## Activate venv (usage: source .venv/bin/activate)
	@echo "Run: source $(VENV)/bin/activate"

build: ## Build wheel and sdist
	$(PYTHON) -m build

test: ## Run tests
	$(PYTHON) -m pytest

lint: ## Run ruff linter
	$(PYTHON) -m ruff check src/ tests/

clean: ## Remove build artifacts and venv
	rm -rf dist/ build/ *.egg-info src/*.egg-info $(VENV)
	find . -type d -name __pycache__ -exec rm -rf {} +
