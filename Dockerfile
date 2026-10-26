FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg libchromaprint-tools flac \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --require-hashes -r requirements.txt

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini run_refinery.py ./

RUN mkdir -p /input /output /work /archive /quarantine /data \
    && useradd --system --uid 1000 refinery \
    && chown -R refinery /app /input /output /work /archive /quarantine /data
USER refinery

ENV INPUT_DIR=/input \
    OUTPUT_DIR=/output \
    STAGING_DIR=/work \
    WORK_DIR=/work \
    ARCHIVE_DIR=/archive \
    QUARANTINE_DIR=/quarantine \
    MUSIC_ROOT=/output/Music \
    MOVIES_ROOT=/output/Movies \
    TV_ROOT=/output/TV \
    DATABASE_URL=sqlite+aiosqlite:////data/media_refinery.sqlite

VOLUME ["/input", "/output", "/work", "/archive", "/quarantine", "/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=4)"]

CMD ["python", "run_refinery.py"]
