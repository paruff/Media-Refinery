requirements: check-venv
test: check-venv unit integration features
unit: check-venv
integration: check-venv
features: check-venv
run: check-venv
lint: check-venv
fmt: check-venv
type-check: check-venv
coverage: check-venv
test-report: check-venv

# Python-centric Makefile for Media-Refinery

.PHONY: ui-test docker-test compose-check venv hooks hooks-update deps-lock precom test unit integration features run lint fmt type-check coverage clean container container-build container-up container-down help check-venv

VENV?=.venv
PYTHON?=$(VENV)/bin/python
PYTEST?=$(VENV)/bin/pytest
PIP?=$(VENV)/bin/pip
BEHAVE?=$(VENV)/bin/behave


precom:
	@echo "[PRECOM] Same hooks as CI: ruff, mypy, bandit, gitleaks, yamllint, actionlint, zizmor, hadolint, ..."
	@SKIP=no-commit-to-branch,pytest-unit pre-commit run --all-files

test: unit integration features

unit:
	$(PYTEST) tests/unit/ --maxfail=3 --disable-warnings -v

integration:
	$(PYTEST) tests/integration/ --maxfail=3 --disable-warnings -v

features:
	$(BEHAVE) tests/features

run:
	$(PYTHON) -m app.main

lint:
	@which flake8 >/dev/null 2>&1 && flake8 app/ tests/ || echo "flake8 not installed; skipping lint"

fmt:
	@which $(VENV)/bin/black >/dev/null 2>&1 && $(VENV)/bin/black app/ tests/ || echo "black not installed; skipping format"
	@which $(VENV)/bin/isort >/dev/null 2>&1 && $(VENV)/bin/isort app/ tests/ || echo "isort not installed; skipping import sort"

type-check:
	@which $(VENV)/bin/mypy >/dev/null 2>&1 && $(VENV)/bin/mypy app/ || echo "mypy not installed; skipping type check"

# TDD-friendly targets
.PHONY: tdd ci check format

# `tdd` runs quick formatting, lint and unit tests for fast feedback loop
tdd: precom unit

# `ci` runs the full precommit suite and all tests
ci: precom test compose-check

# `check` runs lint and type checks
check: lint type-check

# `format` alias for formatting tools
format: fmt

coverage:
	$(PYTEST) --cov=app --cov=tests --cov-report=term --cov-report=html

clean:
	rm -rf .pytest_cache .coverage htmlcov
	rm -rf $(VENV)

# Comprehensive test summary including mutation analysis
.PHONY: test-report
test-report:
	@echo "[TEST-REPORT] Running unit, integration, and BDD tests with coverage and mutation analysis"
	$(PYTEST) --cov=app --cov=tests --cov-report=term-missing --cov-report=html
	@echo "[TEST-REPORT] Running behave BDD tests (if available)"
	$(BEHAVE) tests/features
	@echo "[TEST-REPORT] Running mutation analysis with mutmut (if available)"
	@which mutmut >/dev/null 2>&1 && mutmut run || echo "mutmut not installed; skipping mutation analysis"
	@which mutmut >/dev/null 2>&1 && mutmut results || echo "mutmut not installed; skipping mutation results"
	@echo "[TEST-REPORT] See htmlcov/index.html for detailed coverage report."
	@echo "[TEST-REPORT] See above for mutation analysis summary."

container: container-build container-up

container-build:
	docker build -t media-refinery:latest .

container-up:
	docker-compose up -d

container-down:
	docker-compose down

help:
	@echo "Media-Refinery Python Makefile targets:"
	@echo "  precom         Lint, format, type-check (all pre-commit checks)"
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

.PHONY: check-venv venv
venv: ## create .venv from the hash-locked requirements (uv)
	uv venv --python 3.14 $(VENV)
	uv pip install --python $(VENV)/bin/python -r requirements.txt
	uv pip install --python $(VENV)/bin/python --no-deps --require-hashes -r requirements-dev.txt

check-venv:
	@test -x "$(VENV)/bin/python" || { echo "[ERROR] $(VENV) missing - run: make venv"; exit 1; }

.PHONY: compose-check
compose-check: ## docker compose config -q (falls back to the official compose image if no plugin)
	@docker compose version >/dev/null 2>&1 \
	  && docker compose config -q \
	  || docker run --rm -v "$$PWD":/w -w /w docker/compose-bin:v2.40.3 /docker-compose config -q

# ---- tooling (no venv required) ----------------------------------------------
hooks: ## one-time: install git hooks (pre-commit, commit-msg, pre-push)
	@command -v uv >/dev/null || { echo "install uv: https://docs.astral.sh/uv/"; exit 1; }
	uv python install 3.14
	pre-commit install --install-hooks

hooks-update: ## bump every hook to the latest release, frozen to commit SHAs
	pre-commit autoupdate --freeze

deps-lock: ## re-lock all requirements*.txt (hash-verified)
	uv pip compile requirements.in --upgrade --python-version 3.14 --python-platform x86_64-manylinux_2_28 --generate-hashes --no-header -o requirements.txt
	uv pip compile requirements-dev.in -c requirements.txt --python-version 3.14 --python-platform x86_64-manylinux_2_28 --generate-hashes --no-header -o requirements-dev.txt
	uv pip compile requirements-hooks.in --python-version 3.14 --python-platform x86_64-manylinux_2_28 --generate-hashes --no-header -o requirements-hooks.txt

ui-test: ## G10 web UI tests (Playwright + axe) inside the image: real ffmpeg, no local installs
	docker build -t media-refinery:ci .
	docker run --rm --user root -v "$$PWD":/src:ro -e REQUIRE_FFMPEG=1 media-refinery:ci sh -c \
	  'cp -r /src /w && cd /w && rm -rf .venv && pip install -q --no-deps --require-hashes -r requirements-dev.txt \
	  && playwright install --with-deps chromium >/dev/null && pytest tests/integration/ui -p no:cacheprovider -ra'

docker-test: ## run the CI test job inside the image (real ffmpeg; no local installs)
	docker build -t media-refinery:ci .
	docker run --rm --user root -v "$$PWD":/src:ro -e DATABASE_URL=sqlite+aiosqlite:///:memory: -e REQUIRE_FFMPEG=1 media-refinery:ci sh -c \
	  'cp -r /src /w && cd /w && rm -rf .venv && pip install -q --no-deps --require-hashes -r requirements-dev.txt \
	  && playwright install --with-deps chromium >/dev/null \
	  && mkdir -p input staging output data \
	  && pytest tests/unit tests/integration -n auto -p no:cacheprovider --timeout=120 -ra --cov=app --cov-report=term --cov-fail-under=$${COV_MIN:-80}; \
	  rc=$$?; behave tests/features || rc=1; exit $$rc'
