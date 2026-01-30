on:
env:
jobs:
# Copilot Instructions for Media-Refinery (Python/FastAPI)

## Project Overview

Media-Refinery is a robust media normalization pipeline built with Python and FastAPI, designed to transform unorganized media libraries into well-structured, metadata-rich archives. This document provides guidance for AI coding assistants (GitHub Copilot, Cursor, etc.) to maintain consistency, quality, and best practices for a modern Python backend.

## Core Principles

### 1. Idempotency & Safety
- **All operations MUST be idempotent**: Running the same operation multiple times should produce the same result without side effects
- **Always implement dry-run mode**: Every file operation should support a preview mode
- **Implement atomic operations**: Use rename operations instead of in-place modifications
- **Rollback capability**: Track all changes to enable rollback on failure
- **Checksum verification**: Validate file integrity before and after operations

### 2. Python & FastAPI Best Practices

#### Code Structure
- `app/` – Main application code (FastAPI, models, services, API routes)
- `tests/` – Unit, integration, and BDD (behave) tests
- `config/` – Configuration files and environment templates
- `scripts/` – Utility scripts (optional)

#### Error Handling
- Always raise exceptions with context (e.g., `raise ValueError(f"Invalid file: {filename}")`)
- Use FastAPI's exception handlers for API errors
- Never ignore exceptions; log or handle them explicitly

#### Dependency Management
- Use `pyproject.toml` and `requirements.txt` for dependencies
- Pin versions for reproducibility
- Use virtual environments (`.venv/`)

#### Configuration Management
- Use Pydantic models for config validation
- Support environment variable overrides (e.g., with `python-dotenv`)

#### Logging & Observability
- Use Python's `logging` module or `structlog` for structured logs
- Log at appropriate levels (info, warning, error)
- Expose `/metrics` endpoint using `prometheus_client` for Prometheus

#### API Design
- Use FastAPI for REST endpoints
- Document all endpoints with OpenAPI (FastAPI auto-generates docs)
- Use Pydantic models for request/response validation

#### Security
- Validate all user input (Pydantic, type hints)
- Never trust file paths or extensions from user input
- Store secrets in environment variables or secret managers

#### Performance
- Use async endpoints and database calls (SQLAlchemy async)
- Stream large files instead of loading into memory
- Profile and optimize critical paths

### 3. Test-Driven Development (TDD)

#### Test Structure
- `tests/unit/` – Unit tests for individual functions/classes
- `tests/integration/` – Integration tests for service/database/API flows
- `tests/features/` – BDD feature files (behave)
- Use `pytest` for all test types
- Use `pytest-asyncio` for async tests
- Use `pytest-cov` for coverage

#### Test Coverage Requirements
- **Minimum 80% code coverage** for all packages
- **100% coverage** for critical paths (file operations, normalization, database)
- **Integration tests** for all external dependencies (ffmpeg, APIs)
- **End-to-end tests** for complete workflows

#### Testing Commands
```bash
# Run all tests
pytest

# Run tests with coverage
pytest --cov=app --cov-report=term-missing

# Run integration tests only
pytest tests/integration/

# Run behave BDD tests
behave tests/features/

# Run specific test
pytest -k test_name
```

#### Linting & Formatting
- Use `black` for code formatting
- Use `ruff` or `flake8` for linting
- Use `pre-commit` to enforce standards

#### Example pre-commit config
```yaml
-   repo: https://github.com/psf/black
    rev: 23.7.0
    hooks:
      - id: black
-   repo: https://github.com/charliermarsh/ruff-pre-commit
    rev: v0.1.6
    hooks:
      - id: ruff
```

### 4. GitOps Principles

#### Version Control Standards
- Use `.gitignore` to exclude venvs, build artifacts, test outputs, and secrets
- Keep configuration examples (e.g., `config.example.yaml`)

#### Commit Message Convention
```
<type>(<scope>): <subject>

<body>

<footer>

Types:
- feat: New feature
- fix: Bug fix
- docs: Documentation changes
- style: Code style changes (formatting)
- refactor: Code refactoring
- test: Test additions/changes
- chore: Build process or auxiliary tool changes
- perf: Performance improvements
```

#### Branch Strategy
```
main          - Production-ready code
├── develop   - Integration branch
    ├── feature/movie-normalization
    ├── feature/music-enrichment
    ├── fix/codec-detection
    └── refactor/api-structure
```

#### CI/CD Pipeline (.github/workflows/ci.yml)
- Use GitHub Actions for CI
- Steps:
  - Checkout code
  - Set up Python
  - Install dependencies
  - Lint (ruff, black)
  - Run tests (pytest, behave)
  - Collect and upload coverage
  - Build and optionally push Docker image

#### Example (Python) CI job
```yaml
name: CI
on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main, develop ]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install -r requirements-dev.txt || true
      - name: Lint
        run: |
          ruff .
          black --check .
      - name: Run tests
        run: pytest --cov=app --cov-report=xml
      - name: Run behave
        run: behave tests/features/
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml
```

### 5. Documentation Standards

- Use docstrings for all public classes, methods, and functions
- Document API endpoints with FastAPI (OpenAPI/Swagger UI)
- Keep `README.md` up to date with setup, usage, and contribution instructions
- Use comments to explain complex logic

### 6. Quick Reference Checklist

When implementing new features or fixing bugs, ensure:

- [ ] All exceptions are handled or logged
- [ ] Tests are written (unit + integration + BDD)
- [ ] Test coverage is >80%
- [ ] Logging uses structured format with appropriate levels
- [ ] Metrics are exposed for monitoring
- [ ] Configuration is validated on load
- [ ] Dry-run mode is supported
- [ ] Operations are idempotent
- [ ] File paths are validated against directory traversal
- [ ] Secrets are not hardcoded
- [ ] Code is formatted with `black`
- [ ] Linting passes with `ruff`
- [ ] Documentation is updated
- [ ] Commit message follows convention
- [ ] CI pipeline passes

### 7. Common Patterns & Anti-Patterns

#### ✅ DO
```python
# Use explicit error handling
try:
    do_something()
except Exception as e:
    logger.error(f"Operation failed: {e}")

# Use structured logging
logger.info("Processing complete", extra={"files": count, "duration": elapsed})

# Use parameterized/pytest.mark.parametrize tests
import pytest
@pytest.mark.parametrize("input,expected", [(1,2), (2,3)])
def test_add_one(input, expected):
    assert add_one(input) == expected
```

#### ❌ DON'T
```python
# Don't ignore exceptions
try:
    do_something()
except:
    pass  # NEVER DO THIS

# Don't use print for logging
print("Processed", count)

# Don't repeat test code
def test_case1(): ...
def test_case2(): ...
# ... many similar tests
```

## Additional Resources

- [FastAPI Best Practices](https://fastapi.tiangolo.com/)
- [Pytest Documentation](https://docs.pytest.org/en/stable/)
- [GitOps Principles](https://www.gitops.tech/)
- [Black](https://black.readthedocs.io/en/stable/)
- [Ruff](https://docs.astral.sh/ruff/)
- [Prometheus Python Client](https://github.com/prometheus/client_python)

---

*This document should be reviewed and updated regularly as the project evolves and new patterns emerge.*
