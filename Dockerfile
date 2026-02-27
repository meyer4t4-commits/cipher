# Cipher - Sovereign AI Intelligence Daemon
# Elysian Protocol

FROM python:3.12-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY pyproject.toml ./
RUN pip install --no-cache-dir pip --upgrade && \
    pip install --no-cache-dir . 2>/dev/null || \
    pip install --no-cache-dir \
    "fastapi>=0.115.0" \
    "uvicorn[standard]>=0.34.0" \
    "litellm>=1.55.0" \
    "sqlalchemy>=2.0.36" \
    "pydantic>=2.10.0" \
    "pydantic-settings>=2.7.0" \
    "python-jose[cryptography]>=3.3.0" \
    "passlib[bcrypt]>=1.7.4" \
    "python-multipart>=0.0.18" \
    "email-validator>=2.1.0" \
    "httpx>=0.28.0" \
    "python-dotenv>=1.0.1" \
    "rich>=13.9.0" \
    "tiktoken>=0.8.0"

# Copy application
COPY app/ ./app/
COPY dashboard/ ./dashboard/

# Create data directory
RUN mkdir -p /app/data

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8000/ping || exit 1

# Run
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
