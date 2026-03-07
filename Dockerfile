# Cipher - Sovereign AI Intelligence Daemon
# Elysian Protocol

FROM python:3.12-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Python deps — use requirements.txt for reliable installs
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application
COPY app/ ./app/
COPY dashboard/ ./dashboard/

# Create data directory
RUN mkdir -p /app/data

# Railway sets PORT env var — default to 8000 for local
ENV PORT=8000
EXPOSE ${PORT}

# Use shell form so $PORT gets expanded at runtime
CMD uvicorn app.main:app --host 0.0.0.0 --port $PORT
