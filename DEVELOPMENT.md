# Development Guide

## Quick Start

### Prerequisites
- Python 3.11+
- FFmpeg installed
- Docker (optional, for containerized development)

### Setup
```bash
# Clone repository
git clone https://github.com/paruff/Media-Refinery.git
cd Media-Refinery

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install

# Run tests
make test
```

### Development Workflow
1. Create feature branch: `git checkout -b feature/your-feature`
2. **Write tests first** (TDD - non-negotiable)
3. Implement feature
4. Run tests: `make test`
5. Check coverage: `make coverage` (must be >85%)
6. Lint code: `make precommit`
7. Commit with conventional commits: `git commit -m "feat: add feature"`
8. Push and create PR

### Running Locally
```bash
# Local mode (no Redis/Celery required)
python run_refinery.py

# Distributed mode (requires Redis/Celery)
python run_refinery.py --distributed
```

### Docker Development
```bash
# Build image
make docker-build

# Run container
make docker-run

# Run with docker-compose
docker-compose up
```

### Testing
```bash
make test              # All tests
make test-unit         # Unit tests only
make test-integration  # Integration tests
make coverage          # Coverage report
```

### Common Tasks
```bash
make lint             # Run linters
make format           # Auto-format code
make type-check       # Run mypy
make precommit        # Run all quality checks
```

### Troubleshooting
See [FAQ.md](FAQ.md) for common issues.
