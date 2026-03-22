# ── Frammer Analytics Backend ────────────────────────────────────────────────
# Python 3.12 (matches .python-version)
FROM python:3.12-slim

# Set working directory — matches how config.py resolves BASE_DIR
WORKDIR /app

# ── Environment ──────────────────────────────────────────────────────────────
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

# ── System dependencies ───────────────────────────────────────────────────────
# gcc  — needed to compile some Python C extensions
# curl — used by the healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ── Python dependencies ───────────────────────────────────────────────────────
# Install duckdb + heavy deps as pre-built wheels first (avoids OOM on build)
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir --only-binary=duckdb,pandas,numpy \
        duckdb==1.1.3 pandas==2.2.3 numpy && \
    pip install --no-cache-dir -r requirements.txt

# ── Application code ──────────────────────────────────────────────────────────
COPY . .

# Ensure data directories exist so the file watcher doesn't crash
RUN mkdir -p data/raw data/processed

# ── Ports ─────────────────────────────────────────────────────────────────────
EXPOSE 8000

# ── Start ─────────────────────────────────────────────────────────────────────
# Runs the FastAPI app (same command as render.yaml / start.sh)
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT}"]
