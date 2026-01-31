# API Documentation

## Overview
Media-Refinery exposes a REST API via FastAPI.

**Base URL**: `http://localhost:8000`
**API Docs**: `http://localhost:8000/docs` (Swagger UI)
**OpenAPI Spec**: `http://localhost:8000/openapi.json`

## Authentication
Currently no authentication (planned for v2.0).

## Endpoints

### Audio Conversion

#### POST /api/v1/audio/convert
Create audio conversion job.

**Request**:
```json
{
  "input_path": "/input/song.mp3",
  "output_dir": "/output",
  "format": "flac",
  "preserve_metadata": true
}
```

**Response** (201):
```json
{
  "job_id": 123,
  "status": "pending",
  "created_at": "2026-01-31T12:00:00Z"
}
```

#### GET /api/v1/jobs/{job_id}
Get job status.

**Response** (200):
```json
{
  "job_id": 123,
  "status": "completed",
  "input_path": "/input/song.mp3",
  "output_path": "/output/song.flac",
  "checksum": "abc123...",
  "created_at": "2026-01-31T12:00:00Z",
  "completed_at": "2026-01-31T12:01:30Z"
}
```

### Health Check

#### GET /health
System health status.

**Response** (200):
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "dependencies": {
    "ffmpeg": "available",
    "redis": "connected",
    "database": "connected"
  }
}
```

## Error Responses

### 400 Bad Request
```json
{
  "detail": "Invalid input format"
}
```

### 404 Not Found
```json
{
  "detail": "Job 123 not found"
}
```

### 500 Internal Server Error
```json
{
  "detail": "Conversion failed: FFmpeg error"
}
```
