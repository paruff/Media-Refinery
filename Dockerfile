# Build stage
FROM golang:1.21-alpine AS builder

# Install build dependencies
RUN apk add --no-cache git

# Set working directory
WORKDIR /build

# Copy go mod files
COPY go.mod go.sum* ./

# Download dependencies
RUN go mod download

# Copy source code
COPY . .

# Build the application
RUN CGO_ENABLED=0 GOOS=linux go build -a -installsuffix cgo -o media-refinery ./cmd/refinery

# Final stage
FROM alpine:latest

# Install runtime dependencies
RUN apk --no-cache add \
    ca-certificates \
    ffmpeg \
    && rm -rf /var/cache/apk/*

# Create app directory
WORKDIR /app

# Copy binary from builder
COPY --from=builder /build/media-refinery .

# Create directories
RUN mkdir -p /input /output /work

# Set default environment
ENV INPUT_DIR=/input \
    OUTPUT_DIR=/output \
    WORK_DIR=/work

# Expose any necessary ports (none for CLI tool)

# Default command
ENTRYPOINT ["/app/media-refinery"]
CMD ["-config", "/app/config.yaml"]
