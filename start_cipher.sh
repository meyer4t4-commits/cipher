#!/bin/bash
# ============================================================
# CIPHER STARTUP SCRIPT
# Run this from ~/cipher-app/ to bring Cipher online
# ============================================================

set -e

CIPHER_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$CIPHER_DIR"

echo "========================================"
echo "  CIPHER - Sovereign AI Daemon"
echo "  Starting up..."
echo "========================================"

# 1. Check Python
PYTHON=$(which python3 2>/dev/null || which python 2>/dev/null)
if [ -z "$PYTHON" ]; then
    echo "ERROR: Python not found. Install Python 3.11+"
    exit 1
fi
echo "[OK] Python: $($PYTHON --version)"

# 2. Check .env
if [ ! -f .env ]; then
    echo "ERROR: .env file not found. Copy .env.example to .env and fill in your keys."
    exit 1
fi
echo "[OK] .env found"

# 3. Install/update dependencies
echo "[...] Installing dependencies..."
$PYTHON -m pip install -r requirements.txt --quiet 2>&1 | tail -5
echo "[OK] Dependencies installed"

# 4. Kill any existing Cipher process
if lsof -i :8000 >/dev/null 2>&1; then
    echo "[...] Killing existing process on port 8000..."
    kill $(lsof -ti :8000) 2>/dev/null || true
    sleep 1
fi

# 5. Create data directories if missing
mkdir -p data/sentinel data/synthesis/briefs data/synthesis/sessions data/archivist data/chronos data/chroma

# 6. Start Cipher
echo "[...] Starting Cipher daemon on port 8000..."
echo ""

$PYTHON -m uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --reload \
    --log-level info

