# syntax=docker/dockerfile:1

# ---- Base image ----
FROM python:3.13-slim

# Sensible Python/pip defaults for containers
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HOST=0.0.0.0 \
    PORT=8000

WORKDIR /app

# ---- Dependencies (cached layer) ----
# Copy only requirements first so the pip layer is reused when app code changes.
COPY requirements.txt .
RUN pip install -r requirements.txt

# ---- Application code ----
COPY . .

# Run as a non-root user
RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Liveness probe hits the app's /health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen(f\"http://127.0.0.1:{os.getenv('PORT','8000')}/health\")" || exit 1

# Production server (no --reload). Honors $PORT.
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}"]
