# ============================================================================
# AI Enhanced PDF Scholar - Optimized Build & Development Makefile
# Performance-focused development workflow automation
# ============================================================================

# Python Configuration
PYTHON := python
PIP := $(PYTHON) -m pip
PYTEST := $(PYTHON) -m pytest
RUFF := $(PYTHON) -m ruff
MYPY := $(PYTHON) -m mypy
CI_LINT_BASE ?= origin/main

# Directories
SRC_DIR := src
TEST_DIR := tests
BUILD_DIR := build
DIST_DIR := dist

# Colors for output
RED := \033[0;31m
GREEN := \033[0;32m
YELLOW := \033[0;33m
BLUE := \033[0;34m
NC := \033[0m # No Color

.PHONY: help install install-dev install-prod clean test lint lint-full lint-staged format security audit performance benchmark all ci-local pre-commit pre-commit-install

# Default target
help: ## Show this help message
	@echo "$(BLUE)AI Enhanced PDF Scholar - Development Makefile$(NC)"
	@echo "=================================================="
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "$(GREEN)%-20s$(NC) %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# ============================================================================
# Installation Targets
# ============================================================================

install: ## Install production dependencies
	@echo "$(BLUE)Installing production dependencies...$(NC)"
	$(PIP) install --upgrade pip setuptools wheel
	$(PIP) install -r requirements-prod.txt
	@echo "$(GREEN)✓ Production dependencies installed$(NC)"

install-dev: ## Install development dependencies
	@echo "$(BLUE)Installing development dependencies...$(NC)"
	$(PIP) install --upgrade pip setuptools wheel
	$(PIP) install -r requirements-dev.txt
	$(PIP) install -e .
	@echo "$(GREEN)✓ Development environment ready$(NC)"

install-performance: ## Install performance optimization packages
	@echo "$(BLUE)Installing performance packages...$(NC)"
	$(PIP) install -e .[performance]
	@echo "$(GREEN)✓ Performance optimization packages installed$(NC)"

# ============================================================================
# Development Targets
# ============================================================================

clean: ## Clean build artifacts and cache
	@echo "$(BLUE)Cleaning build artifacts...$(NC)"
	rm -rf $(BUILD_DIR) $(DIST_DIR) *.egg-info
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name ".coverage" -delete
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov
	@echo "$(GREEN)✓ Build artifacts cleaned$(NC)"

format: ## Format code with Ruff (includes src/tests/backend/scripts)
	@echo "$(BLUE)Formatting code...$(NC)"
	$(RUFF) format $(SRC_DIR) $(TEST_DIR) backend scripts
	$(RUFF) check --fix $(SRC_DIR) $(TEST_DIR) backend scripts
	@echo "$(GREEN)✓ Code formatted$(NC)"

lint-full: ## Run full-repo linting (Ruff + MyPy) to gauge baseline debt
	@echo "$(BLUE)Running full linting (Ruff + MyPy)...$(NC)"
	$(RUFF) check $(SRC_DIR) $(TEST_DIR) backend scripts
	PYTHONPATH=. $(MYPY) $(SRC_DIR) backend
	@echo "$(GREEN)✓ Full linting finished$(NC)"

lint: lint-full ## Alias for backwards compatibility (full lint)

lint-staged: ## Run Ruff only on files changed vs. origin/main
	@echo "$(BLUE)Running lint on changed files...$(NC)"
	$(PYTHON) scripts/lint_staged.py
	@echo "$(GREEN)✓ Staged linting completed$(NC)"

lint-ci: ## Match the CI workflow (Black + Ruff + MyPy on changed files)
	@echo "$(BLUE)CI lint: resolving changed Python files vs. $(CI_LINT_BASE)...$(NC)"
	@CHANGED_FILES="$$( $(PYTHON) scripts/lint_staged.py --base $(CI_LINT_BASE) --list-files )"; \
	if [ -z "$$CHANGED_FILES" ]; then \
		echo "No Python files changed. Formatting and lint skipped."; \
	else \
		echo "Checking formatting with Black..."; \
		$(PYTHON) -m black --check --diff $$CHANGED_FILES || exit 1; \
		echo "Running Ruff on changed files..."; \
		$(PYTHON) scripts/lint_staged.py --base $(CI_LINT_BASE) -- --output-format=full || exit 1; \
	fi
	@echo "Running targeted MyPy..."
	@COUNT_FILE=$$(mktemp); \
	if $(PYTHON) scripts/mypy_changed.py --base $(CI_LINT_BASE) --count-file $$COUNT_FILE \
		--allow-prefix backend/api/main.py \
		--allow-prefix backend/api/middleware/error_handling.py \
		--allow-prefix backend/api/dependencies.py; then \
		echo "MyPy completed cleanly."; \
	else \
		ERRS=$$(cat $$COUNT_FILE 2>/dev/null || echo "unknown"); \
		echo "MyPy reported $$ERRS issues."; \
		exit 1; \
	fi

# ============================================================================
# Testing Targets
# ============================================================================

test: ## Run tests with coverage
	@echo "$(BLUE)Running tests...$(NC)"
	$(PYTEST) --cov=$(SRC_DIR) --cov-report=html --cov-report=term-missing
	@echo "$(GREEN)✓ Tests completed$(NC)"

test-fast: ## Run tests without coverage for faster feedback
	@echo "$(BLUE)Running fast tests...$(NC)"
	$(PYTEST) -x --tb=short
	@echo "$(GREEN)✓ Fast tests completed$(NC)"

test-parallel: ## Run tests in parallel
	@echo "$(BLUE)Running parallel tests...$(NC)"
	$(PYTEST) -n auto --cov=$(SRC_DIR)
	@echo "$(GREEN)✓ Parallel tests completed$(NC)"

# ============================================================================
# Security & Audit Targets
# ============================================================================

security: ## Run security scans
	@echo "$(BLUE)Running security scans...$(NC)"
	$(PYTHON) -m bandit -r $(SRC_DIR)
	@echo "$(GREEN)✓ Security scan completed$(NC)"

audit: ## Audit dependencies for vulnerabilities
	@echo "$(BLUE)Auditing dependencies...$(NC)"
	$(PYTHON) -m pip_audit
	@echo "$(GREEN)✓ Dependency audit completed$(NC)"

# ============================================================================
# Performance Targets
# ============================================================================

benchmark: ## Run performance benchmarks
	@echo "$(BLUE)Running performance benchmarks...$(NC)"
	$(PYTEST) --benchmark-only --benchmark-sort=mean
	@echo "$(GREEN)✓ Benchmarks completed$(NC)"

performance: ## Full performance analysis
	@echo "$(BLUE)Running performance analysis...$(NC)"
	$(PYTHON) -c "import time; start=time.time(); import fastapi, uvicorn, pydantic, llama_index; print(f'Import time: {time.time()-start:.3f}s')"
	@echo "$(GREEN)✓ Performance analysis completed$(NC)"

profile: ## Profile application startup
	@echo "$(BLUE)Profiling application...$(NC)"
	$(PYTHON) -m py_spy top --pid $$(pgrep -f "uvicorn.*web_main") --duration 30
	@echo "$(GREEN)✓ Profiling completed$(NC)"

# ============================================================================
# CI/CD Targets
# ============================================================================

ci-install: ## Fast CI installation
	@echo "$(BLUE)CI: Installing dependencies...$(NC)"
	$(PIP) install --upgrade pip setuptools wheel --no-cache-dir
	$(PIP) install -r requirements.txt --no-cache-dir
	$(PIP) install pytest pytest-cov ruff mypy --no-cache-dir

ci-test: ## CI optimized testing
	@echo "$(BLUE)CI: Running tests...$(NC)"
	$(PYTEST) --tb=short --cov=$(SRC_DIR) --cov-report=xml

ci-lint: ## CI optimized linting
	@echo "$(BLUE)CI: Running linting...$(NC)"
	$(PYTHON) -m ruff check $(SRC_DIR) $(TEST_DIR) --output-format=github

# ============================================================================
# Update Targets
# ============================================================================

update: ## Update dependencies to latest versions
	@echo "$(BLUE)Updating dependencies...$(NC)"
	$(PIP) list --outdated --format=json | jq -r '.[] | .name' | xargs -I {} $(PIP) install --upgrade {}
	@echo "$(GREEN)✓ Dependencies updated$(NC)"

check-updates: ## Check for available updates
	@echo "$(BLUE)Checking for updates...$(NC)"
	$(PIP) list --outdated
	@echo "$(GREEN)✓ Update check completed$(NC)"

# ============================================================================
# Comprehensive Targets
# ============================================================================

all: clean install-dev lint test security audit ## Run all checks
	@echo "$(GREEN)✓ All checks completed successfully$(NC)"

dev-setup: install-dev ## Complete development environment setup
	@echo "$(GREEN)✓ Development environment ready for coding$(NC)"

pre-commit: format lint test-fast ## Quick pre-commit checks
	@echo "$(GREEN)✓ Pre-commit checks passed$(NC)"

pre-commit-install: ## Install git hooks defined in .pre-commit-config.yaml
	@echo "$(BLUE)Installing pre-commit hooks...$(NC)"
	pre-commit install --install-hooks
	pre-commit install --hook-type pre-push || true
	@echo "$(GREEN)✓ Pre-commit hooks installed$(NC)"

ci-local: ## Run the full CI gate locally (lint + backend + frontend tests)
	@echo "$(BLUE)Running full CI parity suite...$(NC)"
	$(MAKE) lint-ci
	$(PYTEST) -q
	cd frontend && npm run test -- --run
	@echo "$(GREEN)✓ CI parity suite completed$(NC)"
