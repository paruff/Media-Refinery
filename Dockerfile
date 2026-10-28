# syntax=docker/dockerfile:1
# Stage 1: hash-locked Python deps into a venv (no compilers or pip in the runtime image).
FROM python:3.14-slim@sha256:cd89c30eda26ee911a4611b18680086e0ea42e6f5f8cbe653d07fa7958c9cec8 AS builder
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m venv /opt/venv
WORKDIR /build
COPY requirements.txt .
RUN /opt/venv/bin/pip install --no-cache-dir --require-hashes -r requirements.txt

# Stage 2: runtime with every media tool the pipeline shells out to.
FROM python:3.14-slim@sha256:cd89c30eda26ee911a4611b18680086e0ea42e6f5f8cbe653d07fa7958c9cec8
# hadolint ignore=DL3008
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg libchromaprint-tools flac calibre epubcheck \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini run_refinery.py ./

# Run as any uid:gid with `user:` (compose: PUID/PGID); the default is 1000:1000.
RUN mkdir -p /input /output /work /archive /quarantine /data \
    && groupadd --gid 1000 refinery \
    && useradd --uid 1000 --gid 1000 --home-dir /data refinery \
    && chown -R refinery /app /input /output /work /archive /quarantine /data
USER 1000:1000

ENV HOME=/data \
    CALIBRE_CONFIG_DIRECTORY=/data/calibre-config \
    INPUT_DIR=/input \
    OUTPUT_DIR=/output \
    STAGING_DIR=/work \
    WORK_DIR=/work \
    ARCHIVE_DIR=/archive \
    QUARANTINE_DIR=/quarantine \
    MUSIC_ROOT=/output/Music \
    MOVIES_ROOT=/output/Movies \
    TV_ROOT=/output/TV \
    AUDIOBOOKS_ROOT=/output/Audiobooks \
    CALIBRE_LIBRARY=/output/Books \
    DATABASE_URL=sqlite+aiosqlite:////data/media_refinery.sqlite

VOLUME ["/input", "/output", "/work", "/archive", "/quarantine", "/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/ready', timeout=4)"]

CMD ["python", "run_refinery.py"]
