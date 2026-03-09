# ============================================================
# Cipher - Sovereign AI Intelligence Daemon
# Elysian Protocol — Production Dockerfile (Memory-Optimized)
# ============================================================

# Stage 1: Build dependencies
FROM python:3.12-slim AS builder

WORKDIR /build

COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2: Production image
FROM python:3.12-slim

# Security: create non-root user
RUN groupadd -r cipher && useradd -r -g cipher -d /app -s /sbin/nologin cipher

WORKDIR /app

# System deps — minimal (no Playwright/Chromium to save ~300MB RAM)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy Python packages from builder stage
COPY --from=builder /install /usr/local

# Copy application
COPY --chown=cipher:cipher app/ ./app/
COPY --chown=cipher:cipher dashboard/ ./dashboard/

# Create data directories with correct ownership
RUN mkdir -p /app/data && chown -R cipher:cipher /app/data

# Security: drop to non-root
USER cipher

# Health check endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/ping || exit 1

# Default port
ENV PORT=8000
EXPOSE ${PORT}

# Use exec form for proper signal handling
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1 --limit-concurrency 20 --timeout-keep-alive 120"]
