
# Python-centric Makefile for Media-Refinery

.PHONY: precom test unit integration features run lint fmt type-check coverage clean container container-build container-up container-down help

VENV?=.venv
PYTHON?=$(VENV)/bin/python
PYTEST?=$(VENV)/bin/pytest
PIP?=$(VENV)/bin/pip
BEHAVE?=$(VENV)/bin/behave

precom:
	@echo "[PRECOM] Lint, format, type-check, and security scan"
	@which black >/dev/null 2>&1 && black app/ tests/ || echo "black not installed; skipping format"
	@which isort >/dev/null 2>&1 && isort app/ tests/ || echo "isort not installed; skipping import sort"
	@which flake8 >/dev/null 2>&1 && flake8 app/ tests/ || echo "flake8 not installed; skipping lint"
	@which mypy >/dev/null 2>&1 && mypy app/ || echo "mypy not installed; skipping type check"
	@which bandit >/dev/null 2>&1 && bandit -r app/ || echo "bandit not installed; skipping security scan"

test: unit integration features

unit:
	$(PYTEST) tests/unit/ --maxfail=3 --disable-warnings -v

integration:
	$(PYTEST) tests/integration/ --maxfail=3 --disable-warnings -v

features:
	@which behave >/dev/null 2>&1 && $(BEHAVE) features/ || echo "behave not installed; skipping BDD features"

run:
	$(PYTHON) -m app.main

lint:
	@which flake8 >/dev/null 2>&1 && flake8 app/ tests/ || echo "flake8 not installed; skipping lint"

fmt:
	@which black >/dev/null 2>&1 && black app/ tests/ || echo "black not installed; skipping format"
	@which isort >/dev/null 2>&1 && isort app/ tests/ || echo "isort not installed; skipping import sort"

type-check:
	@which mypy >/dev/null 2>&1 && mypy app/ || echo "mypy not installed; skipping type check"

coverage:
	$(PYTEST) --cov=app --cov=tests --cov-report=term --cov-report=html

clean:
	rm -rf .pytest_cache .coverage htmlcov
	rm -rf $(VENV)

container: container-build container-up

container-build:
	docker build -t media-refinery:latest .

container-up:
	docker-compose up -d

container-down:
	docker-compose down

help:
	@echo "Media-Refinery Python Makefile targets:"
	@echo "  precom         Lint, format, type-check, security scan"
	@echo "  test           Run all tests (unit, integration, features)"
	@echo "  unit           Run unit tests only"
	@echo "  integration    Run integration tests only"
	@echo "  features       Run BDD/feature tests (behave)"
	@echo "  run            Run the main application"
	@echo "  lint           Run flake8 lint checks"
	@echo "  fmt            Run black and isort formatting"
	@echo "  type-check     Run mypy type checks"
	@echo "  coverage       Run test coverage report"
	@echo "  clean          Remove caches, venv, and coverage files"
	@echo "  container      Build and start Docker container"
	@echo "  container-build  Build Docker image"
	@echo "  container-up   Start Docker containers"
	@echo "  container-down Stop Docker containers"
	@echo "  help           Show this help message"
