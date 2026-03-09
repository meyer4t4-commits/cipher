#!/bin/bash
# ============================================================
# Cipher - Security Hardening Script (Elysian Protocol)
#
# Run ONCE after initial setup, and again after any config changes.
# Usage: chmod +x infra/scripts/harden.sh && ./infra/scripts/harden.sh
# ============================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

CIPHER_DIR="${CIPHER_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
PASS=0
WARN=0
FAIL=0

echo "═══════════════════════════════════════════"
echo "  Cipher Security Hardening — Elysian Protocol"
echo "═══════════════════════════════════════════"
echo ""

# --- 1. File Permissions ---
echo "[ Phase 1 ] File Permissions"

# .env must be owner-read only
if [ -f "$CIPHER_DIR/.env" ]; then
    chmod 600 "$CIPHER_DIR/.env"
    echo -e "  ${GREEN}[PASS]${NC} .env set to 600 (owner read/write only)"
    ((PASS++))
else
    echo -e "  ${RED}[FAIL]${NC} .env not found at $CIPHER_DIR/.env"
    ((FAIL++))
fi

# Data directory
if [ -d "$CIPHER_DIR/data" ]; then
    chmod 700 "$CIPHER_DIR/data"
    chmod -R go-rwx "$CIPHER_DIR/data" 2>/dev/null || true
    echo -e "  ${GREEN}[PASS]${NC} data/ locked to owner only"
    ((PASS++))
else
    mkdir -p "$CIPHER_DIR/data"
    chmod 700 "$CIPHER_DIR/data"
    echo -e "  ${YELLOW}[WARN]${NC} data/ created and locked"
    ((WARN++))
fi

# Logs directory
mkdir -p "$CIPHER_DIR/logs"
chmod 700 "$CIPHER_DIR/logs"
echo -e "  ${GREEN}[PASS]${NC} logs/ locked to owner only"
((PASS++))

# SSL directory (if exists)
if [ -d "$CIPHER_DIR/infra/nginx/ssl" ]; then
    chmod 700 "$CIPHER_DIR/infra/nginx/ssl"
    chmod 600 "$CIPHER_DIR/infra/nginx/ssl"/* 2>/dev/null || true
    echo -e "  ${GREEN}[PASS]${NC} SSL certs locked"
    ((PASS++))
fi

echo ""

# --- 2. .env Audit ---
echo "[ Phase 2 ] Credential Audit"

if [ -f "$CIPHER_DIR/.env" ]; then
    # Check for placeholder/dummy values
    PLACEHOLDERS=$(grep -c "xxxxx\|your-.*-here\|change-this\|placeholder" "$CIPHER_DIR/.env" 2>/dev/null || echo "0")
    if [ "$PLACEHOLDERS" -gt "0" ]; then
        echo -e "  ${YELLOW}[WARN]${NC} $PLACEHOLDERS placeholder values found in .env — replace before production"
        ((WARN++))
    else
        echo -e "  ${GREEN}[PASS]${NC} No placeholder values in .env"
        ((PASS++))
    fi

    # Check SECRET_KEY isn't default
    if grep -q "change-this-in-production" "$CIPHER_DIR/.env" 2>/dev/null; then
        echo -e "  ${RED}[FAIL]${NC} SECRET_KEY is still the default — generate a real one"
        ((FAIL++))
    else
        echo -e "  ${GREEN}[PASS]${NC} SECRET_KEY is set"
        ((PASS++))
    fi

    # Check APP_DEBUG isn't true in production
    if grep -q "APP_ENV=production" "$CIPHER_DIR/.env" && grep -q "APP_DEBUG=true" "$CIPHER_DIR/.env"; then
        echo -e "  ${RED}[FAIL]${NC} APP_DEBUG=true in production — disable it"
        ((FAIL++))
    else
        echo -e "  ${GREEN}[PASS]${NC} Debug mode appropriate for environment"
        ((PASS++))
    fi
fi

echo ""

# --- 3. Network Security ---
echo "[ Phase 3 ] Network Security"

# Check if Docker is binding to 0.0.0.0
if grep -q '0\.0\.0\.0:8000' "$CIPHER_DIR/docker-compose.yml" 2>/dev/null; then
    echo -e "  ${RED}[FAIL]${NC} docker-compose.yml binds port 8000 to 0.0.0.0 — change to 127.0.0.1:8000:8000"
    ((FAIL++))
else
    echo -e "  ${GREEN}[PASS]${NC} API port bound to localhost only"
    ((PASS++))
fi

if grep -q '0\.0\.0\.0:6379' "$CIPHER_DIR/docker-compose.yml" 2>/dev/null; then
    echo -e "  ${RED}[FAIL]${NC} Redis bound to 0.0.0.0 — change to 127.0.0.1:6379:6379"
    ((FAIL++))
else
    echo -e "  ${GREEN}[PASS]${NC} Redis port bound to localhost only"
    ((PASS++))
fi

# Check macOS firewall
if command -v defaults &>/dev/null; then
    FW_STATUS=$(defaults read /Library/Preferences/com.apple.alf globalstate 2>/dev/null || echo "0")
    if [ "$FW_STATUS" -ge "1" ]; then
        echo -e "  ${GREEN}[PASS]${NC} macOS Firewall is ON"
        ((PASS++))
    else
        echo -e "  ${YELLOW}[WARN]${NC} macOS Firewall appears OFF — enable in System Settings → Network → Firewall"
        ((WARN++))
    fi
fi

echo ""

# --- 4. Docker Security ---
echo "[ Phase 4 ] Docker Security"

if command -v docker &>/dev/null; then
    if docker info &>/dev/null 2>&1; then
        echo -e "  ${GREEN}[PASS]${NC} Docker is running"
        ((PASS++))
    else
        echo -e "  ${YELLOW}[WARN]${NC} Docker is installed but not running"
        ((WARN++))
    fi
else
    echo -e "  ${YELLOW}[WARN]${NC} Docker not installed — needed for production deployment"
    ((WARN++))
fi

# Check for no-new-privileges in compose
if grep -q "no-new-privileges" "$CIPHER_DIR/docker-compose.yml" 2>/dev/null; then
    echo -e "  ${GREEN}[PASS]${NC} Container privilege escalation blocked"
    ((PASS++))
else
    echo -e "  ${YELLOW}[WARN]${NC} Add security_opt: [no-new-privileges:true] to containers"
    ((WARN++))
fi

# Check for resource limits
if grep -q "limits:" "$CIPHER_DIR/docker-compose.yml" 2>/dev/null; then
    echo -e "  ${GREEN}[PASS]${NC} Container resource limits set"
    ((PASS++))
else
    echo -e "  ${YELLOW}[WARN]${NC} No resource limits on containers — add deploy.resources.limits"
    ((WARN++))
fi

echo ""

# --- 5. Git Security ---
echo "[ Phase 5 ] Git Security"

# Check .gitignore includes sensitive files
if [ -f "$CIPHER_DIR/.gitignore" ]; then
    MISSING_GITIGNORE=()
    for pattern in ".env" "data/" "*.db" "logs/" "infra/nginx/ssl/"; do
        if ! grep -q "$pattern" "$CIPHER_DIR/.gitignore" 2>/dev/null; then
            MISSING_GITIGNORE+=("$pattern")
        fi
    done
    if [ ${#MISSING_GITIGNORE[@]} -gt 0 ]; then
        echo -e "  ${YELLOW}[WARN]${NC} .gitignore missing: ${MISSING_GITIGNORE[*]}"
        ((WARN++))
    else
        echo -e "  ${GREEN}[PASS]${NC} .gitignore covers sensitive files"
        ((PASS++))
    fi
else
    echo -e "  ${RED}[FAIL]${NC} No .gitignore found — sensitive data may be committed"
    ((FAIL++))
fi

echo ""

# --- Summary ---
echo "═══════════════════════════════════════════"
echo -e "  Results: ${GREEN}${PASS} passed${NC} | ${YELLOW}${WARN} warnings${NC} | ${RED}${FAIL} failed${NC}"
if [ "$FAIL" -gt "0" ]; then
    echo -e "  ${RED}FIX FAILURES BEFORE DEPLOYING TO PRODUCTION${NC}"
    exit 1
elif [ "$WARN" -gt "0" ]; then
    echo -e "  ${YELLOW}Review warnings for production readiness${NC}"
    exit 0
else
    echo -e "  ${GREEN}ALL CHECKS PASSED — ready for deployment${NC}"
    exit 0
fi
echo "═══════════════════════════════════════════"
