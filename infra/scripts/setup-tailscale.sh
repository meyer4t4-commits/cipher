#!/bin/bash
# ============================================================
# Cipher - Tailscale Remote Access Setup (Elysian Protocol)
#
# Enables secure remote access to Cipher from your iPhone
# without exposing any ports to the public internet.
#
# Usage: chmod +x infra/scripts/setup-tailscale.sh && ./infra/scripts/setup-tailscale.sh
# ============================================================

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo "═══════════════════════════════════════════"
echo "  Cipher — Tailscale Remote Access Setup"
echo "═══════════════════════════════════════════"
echo ""

# Step 1: Check/Install Tailscale
if command -v tailscale &>/dev/null; then
    echo -e "${GREEN}[OK]${NC} Tailscale is installed"
else
    echo "Installing Tailscale..."
    brew install --cask tailscale
    echo -e "${GREEN}[OK]${NC} Tailscale installed"
fi

# Step 2: Check if Tailscale is running
if tailscale status &>/dev/null 2>&1; then
    echo -e "${GREEN}[OK]${NC} Tailscale is connected"
    TAILSCALE_IP=$(tailscale ip -4 2>/dev/null || echo "unknown")
    echo "      Your Tailscale IP: $TAILSCALE_IP"
else
    echo -e "${YELLOW}[ACTION NEEDED]${NC} Open Tailscale app and log in"
    echo "      Then re-run this script"
    exit 1
fi

# Step 3: Set up Tailscale Serve to proxy to Cipher
echo ""
echo "Setting up Tailscale Serve to proxy port 8000..."
echo ""

# Use tailscale serve to forward HTTPS traffic to local Cipher
# This gives you a valid HTTPS cert automatically
tailscale serve --bg --https=8443 http://127.0.0.1:8000 2>/dev/null || {
    echo -e "${YELLOW}[INFO]${NC} tailscale serve may need manual setup."
    echo "      Run: tailscale serve --https=8443 http://127.0.0.1:8000"
}

echo ""
echo "═══════════════════════════════════════════"
echo -e "${GREEN}  Setup Complete${NC}"
echo ""
echo "  Access Cipher from any device on your tailnet:"
echo ""
echo "  API:       https://${TAILSCALE_IP}:8443/api/v1/"
echo "  Dashboard: https://${TAILSCALE_IP}:8443/dashboard/"
echo "  Health:    https://${TAILSCALE_IP}:8443/ping"
echo ""
echo "  On your iPhone:"
echo "  1. Install Tailscale from App Store"
echo "  2. Log in with same account"
echo "  3. Update CipherApp Constants.swift:"
echo "     defaultServerURL = \"https://${TAILSCALE_IP}:8443\""
echo ""
echo "  Your traffic is end-to-end encrypted via WireGuard."
echo "  No ports exposed to the public internet."
echo "═══════════════════════════════════════════"
