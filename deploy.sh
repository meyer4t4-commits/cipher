#!/bin/bash
# ============================================================
# Cipher - One-Command Railway Deployment
# Elysian Protocol
#
# Usage: ./deploy.sh
# ============================================================

set -e

echo "═══════════════════════════════════════════"
echo "  Cipher Deployment — Elysian Protocol"
echo "═══════════════════════════════════════════"
echo ""

# Check if Railway CLI is installed
if ! command -v railway &> /dev/null; then
    echo "Installing Railway CLI..."
    brew install railway
fi

# Check if logged in
echo "Checking Railway login..."
if ! railway whoami &> /dev/null 2>&1; then
    echo "Not logged in. Opening Railway login..."
    railway login --browserless
fi

echo ""
echo "Logged in as: $(railway whoami 2>/dev/null || echo 'unknown')"
echo ""

# Check if project is linked
if ! railway status &> /dev/null 2>&1; then
    echo "No Railway project linked. Creating..."
    railway init --name cipher
    echo "Project created."
fi

# Load API keys from .env
echo "Setting environment variables from .env..."
if [ -f .env ]; then
    # Extract key values from .env (skip comments and empty lines)
    while IFS='=' read -r key value; do
        # Skip comments and empty lines
        [[ "$key" =~ ^#.*$ ]] && continue
        [[ -z "$key" ]] && continue
        # Skip placeholder values
        [[ "$value" == "sk-xxxxx" ]] && continue
        [[ "$value" == "your-"* ]] && continue
        [[ -z "$value" ]] && continue

        # Set on Railway
        railway variables set "$key=$value" 2>/dev/null && echo "  Set $key" || true
    done < .env

    # Override production-specific values
    railway variables set APP_ENV=production 2>/dev/null
    railway variables set APP_DEBUG=false 2>/dev/null
    railway variables set SCANNER_ENABLED=false 2>/dev/null
    echo "  Set production overrides"
else
    echo "WARNING: No .env file found. Set variables manually in Railway dashboard."
fi

echo ""
echo "Deploying to Railway..."
echo ""

# Deploy
railway up --detach

echo ""
echo "═══════════════════════════════════════════"
echo "  Deployment initiated."
echo ""
echo "  Check status:  railway status"
echo "  View logs:     railway logs"
echo "  Get URL:       railway domain"
echo ""
echo "  Next: Add custom domain in Railway dashboard"
echo "  Point api.elysianprotocol.io → Railway URL"
echo "═══════════════════════════════════════════"
