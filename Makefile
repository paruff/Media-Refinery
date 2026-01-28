.PHONY: all build test clean install docker-build docker-up docker-down help

# Binary name
BINARY_NAME=media-refinery
DOCKER_IMAGE=media-refinery:latest

# Go parameters
GOCMD=go
GOBUILD=$(GOCMD) build
GOTEST=$(GOCMD) test
GOGET=$(GOCMD) get
GOMOD=$(GOCMD) mod
GOCLEAN=$(GOCMD) clean

all: test build

## build: Build the binary
build:
	go build ./...

## test: Run tests
test:
	$(GOTEST) -v ./...

## test-coverage: Run tests with coverage
test-coverage:
	$(GOTEST) -v -coverprofile=coverage.out ./...
	$(GOCMD) tool cover -html=coverage.out -o coverage.html

## clean: Clean build artifacts
clean:
	$(GOCLEAN)
	rm -f $(BINARY_NAME)
	rm -f coverage.out coverage.html

## install: Install the binary
install: build
	cp $(BINARY_NAME) /usr/local/bin/

## deps: Download dependencies
deps:
	$(GOMOD) download
	$(GOMOD) tidy

## fmt: Format code
fmt:
	$(GOCMD) fmt ./...

## vet: Run go vet
vet:
	$(GOCMD) vet ./...

## lint: Run golangci-lint (requires golangci-lint installed)
lint:
	golangci-lint run ./...

## docker-build: Build Docker image
docker-build:
	docker build -t $(DOCKER_IMAGE) .

## docker-up: Start all Docker services
docker-up:
	docker-compose up -d

## docker-down: Stop all Docker services
docker-down:
	docker-compose down

## docker-logs: Show Docker logs
docker-logs:
	docker-compose logs -f

## docker-run: Run media-refinery in Docker
docker-run:
	docker-compose run --rm media-refinery

## run: Run the application (requires config.yaml)
run: build
	./$(BINARY_NAME) -config config.yaml

## run-dry: Run in dry-run mode
run-dry: build
	./$(BINARY_NAME) -config config.yaml -dry-run

## init-config: Generate default configuration
init-config: build
	./$(BINARY_NAME) -init -config config.yaml

## help: Show this help message
help:
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@sed -n 's/^##//p' ${MAKEFILE_LIST} | column -t -s ':' | sed -e 's/^/ /'

# Unit Tests
unit-test:
	go test ./pkg/... -v

# Integration Tests
integration-test: lint fmt
	bash ./test/integration_test.sh

# Benchmark Tests
benchmark-test:
	go test -bench=. ./pkg/...

# BDD/E2E Tests
bdd-test:
	go test ./test/bdd -v

# Security Scans
security-scan:
	trivy fs .

# Static Code Analysis
static-analysis:
	golangci-lint run ./...
