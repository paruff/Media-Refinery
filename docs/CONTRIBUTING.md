# Media Refinery Contribution Quickstart Guide

Welcome to the Media Refinery project! This guide will help you get started as a contributor.

---

## 🛠 Repository Structure

The repository is structured as follows:

- **`cmd/`**: Contains the main application entry point code.
- **`pkg/`**: Hosts the core logic of the project, including components for configuration, logging, validation, and processing.
- **`test/`**: Contains integration and unit test scripts.
- **`config.example.yaml`**: Provides a template configuration file for setup.
- **`ARCHITECTURE.md`**: Detailed documentation of the project's architecture.
- **`SUMMARY.md`**: A summary of features, configurations, and enhancements.
- **`DOCKER.md`**: Instructions for setting up the project using Docker.
- **`docker-compose.yml`** and **`Dockerfile`**: Docker setup files for containerized deployment.
- **`Makefile`**: Defines common commands such as building, testing, and more.
- **`README.md`**: General project overview and setup instructions.

---

## 🚀 Steps to Contribute

### 1. Fork the Repository
Create a fork to work on your changes.

```bash
git clone https://github.com/your-username/media-refinery.git
cd media-refinery
```

### 2. Setup Your Environment
- Install dependencies:
  ```bash
go mod tidy
```
- (Optional) Use Docker for streamlined setup:
  - Start services:
    ```bash
docker-compose up -d
```

### 3. Explore Contribution Areas
Check out where you can contribute:
- Bug fixes: `ISSUES.md` (if available).
- New features: Refer to `ARCHITECTURE.md`, `SUMMARY.md`.
- Tests: See `test/` for existing coverage.

### 4. Run Tests
Verify your changes:
```bash
make test
```

### 5. Write New Tests
- Add unit tests in `pkg/`.
- Add integration tests in `test/`.

### 6. Open a Pull Request
Push your changes and create a pull request explaining what you've added or fixed.

### 7. Adhere to Guidelines
- Follow the coding style used in the project.
- Update documentation where necessary.
