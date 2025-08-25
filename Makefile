# Makefile for Research System
# Ensures Python 3.11+ is used for all operations

# Detect Python 3.11+
PYTHON := $(shell command -v python3.11 2> /dev/null || command -v python3.12 2> /dev/null || echo python3)
PYTHON_VERSION := $(shell $(PYTHON) -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "0.0")
PYTHON_VERSION_OK := $(shell $(PYTHON) -c "import sys; exit(0 if sys.version_info >= (3, 11) else 1)" 2>/dev/null && echo "yes" || echo "no")

# Check Python version
check-python:
	@if [ "$(PYTHON_VERSION_OK)" != "yes" ]; then \
		echo "Error: Python 3.11+ is required (found Python $(PYTHON_VERSION))"; \
		echo "Please install Python 3.11 or higher"; \
		exit 1; \
	fi
	@echo "Using Python $(PYTHON_VERSION) at $(PYTHON)"

.PHONY: help
help: ## Show this help message
	@echo "Research System - Available Commands:"
	@echo
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo

.PHONY: setup
setup: check-python ## Install all dependencies
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -e ".[web,test,dev,monitoring]"
	@echo "✓ Setup complete"

.PHONY: test
test: check-python ## Run all tests
	PYTHONPATH=. $(PYTHON) -m pytest tests/ -v

.PHONY: test-fast
test-fast: check-python ## Run fast tests (no external deps)
	PYTHONPATH=. $(PYTHON) -m pytest tests/test_api_compliance.py tests/test_dedup.py tests/test_entity_norm.py tests/test_normalizations.py tests/test_url_norm_s3.py -v

.PHONY: test-ci
test-ci: check-python ## Run tests as CI would
	PYTHONPATH=. $(PYTHON) -m pytest -q

.PHONY: lint
lint: check-python ## Run linting
	$(PYTHON) -m ruff check research_system/
	$(PYTHON) -m mypy research_system/

.PHONY: format
format: check-python ## Format code
	$(PYTHON) -m black research_system/ tests/
	$(PYTHON) -m ruff check --fix research_system/

.PHONY: clean
clean: ## Clean build artifacts
	rm -rf build/ dist/ *.egg-info
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type f -name ".DS_Store" -delete

.PHONY: run
run: check-python ## Run research on a topic (use TOPIC="your topic")
	@if [ -z "$(TOPIC)" ]; then \
		echo "Error: Please provide a topic with TOPIC='your topic'"; \
		exit 1; \
	fi
	$(PYTHON) -m research_system --topic "$(TOPIC)"

.PHONY: install-dev
install-dev: check-python ## Install development dependencies only
	$(PYTHON) -m pip install -e ".[dev]"

.PHONY: verify
verify: check-python test-fast ## Quick verification that basics work
	@echo "✓ Basic verification passed"

# Default target
.DEFAULT_GOAL := help