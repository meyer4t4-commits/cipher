#!/bin/bash
# ============================================================
# Cipher - Emergency Procedures (Elysian Protocol)
#
# Usage:
#   ./infra/scripts/emergency.sh stop        — Kill everything NOW
#   ./infra/scripts/emergency.sh lockdown    — Stop + revoke instructions
#   ./infra/scripts/emergency.sh audit       — Check for suspicious activity
#   ./infra/scripts/emergency.sh rotate      — Rotate all API keys (interactive)
# ============================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

CIPHER_DIR="${CIPHER_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
ACTION="${1:-help}"

case "$ACTION" in

# ========================================
# EMERGENCY STOP — Kill everything
# ========================================
stop)
    echo -e "${RED}═══ EMERGENCY STOP ═══${NC}"
    echo ""

    # Kill Docker containers
    echo "Stopping all Cipher containers..."
    cd "$CIPHER_DIR"
    docker compose down --timeout 5 2>/dev/null || true

    # Kill any bare uvicorn processes
    echo "Killing uvicorn processes..."
    pkill -f "uvicorn app.main:app" 2>/dev/null || true
    lsof -ti:8000 | xargs kill -9 2>/dev/null || true

    # Kill celery workers
    echo "Killing celery workers..."
    pkill -f "celery.*cipher" 2>/dev/null || true

    echo ""
    echo -e "${GREEN}All Cipher processes stopped.${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Check logs:     docker compose logs --tail=100"
    echo "  2. Audit activity: $0 audit"
    echo "  3. Restart:        docker compose up -d"
    ;;

# ========================================
# LOCKDOWN — Stop + full security response
# ========================================
lockdown)
    echo -e "${RED}═══ LOCKDOWN MODE ═══${NC}"
    echo ""

    # Stop everything first
    "$0" stop

    echo ""
    echo -e "${YELLOW}Manual steps required:${NC}"
    echo ""
    echo "  1. REVOKE API KEYS (do this NOW):"
    echo "     - Anthropic:  https://console.anthropic.com/ → API Keys → Revoke"
    echo "     - OpenAI:     https://platform.openai.com/api-keys → Revoke"
    echo "     - Groq:       https://console.groq.com/keys → Revoke"
    echo "     - DeepSeek:   https://platform.deepseek.com/ → API Keys → Revoke"
    echo "     - Brave:      https://brave.com/search/api/ → Dashboard → Revoke"
    echo "     - ElevenLabs: https://elevenlabs.io/ → Profile → API Keys → Revoke"
    echo "     - Replicate:  https://replicate.com/account/api-tokens → Revoke"
    echo "     - fal.ai:     https://fal.ai/dashboard/keys → Revoke"
    echo "     - Stability:  https://platform.stability.ai/account/keys → Revoke"
    echo ""
    echo "  2. REVOKE COMMUNICATION TOKENS:"
    echo "     - Telegram:   Message @BotFather → /revoke"
    echo "     - Slack:      https://api.slack.com/apps → Your App → Revoke Tokens"
    echo "     - Gmail:      https://myaccount.google.com/apppasswords → Revoke app password"
    echo "     - Twilio:     https://console.twilio.com/ → Auth Tokens → Rotate"
    echo ""
    echo "  3. CHECK FOR DATA EXFILTRATION:"
    echo "     - Review Anthropic usage: https://console.anthropic.com/ (usage tab)"
    echo "     - Review OpenAI usage: https://platform.openai.com/usage"
    echo "     - Check Telegram bot history for outbound messages"
    echo "     - Check Gmail sent folder for unauthorized emails"
    echo ""
    echo "  4. AFTER ROTATING ALL KEYS:"
    echo "     - Update .env with new keys"
    echo "     - Run: ./infra/scripts/harden.sh"
    echo "     - Restart: docker compose up -d"
    ;;

# ========================================
# AUDIT — Check for suspicious activity
# ========================================
audit)
    echo -e "${CYAN}═══ SECURITY AUDIT ═══${NC}"
    echo ""

    # Check running processes
    echo "[ Cipher Processes ]"
    ps aux | grep -E "uvicorn|celery|cipher" | grep -v grep || echo "  No Cipher processes running"
    echo ""

    # Check open ports
    echo "[ Open Ports ]"
    lsof -i -P -n | grep -E "LISTEN" | grep -E "8000|6379|80|443" || echo "  No Cipher ports open"
    echo ""

    # Check Docker containers
    echo "[ Docker Containers ]"
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null | grep -E "cipher|redis" || echo "  No Cipher containers running"
    echo ""

    # Check recent log entries for errors
    echo "[ Recent Errors (last 50 lines) ]"
    if [ -f "$CIPHER_DIR/logs/launchd-stderr.log" ]; then
        tail -50 "$CIPHER_DIR/logs/launchd-stderr.log" | grep -i "error\|fail\|exception\|unauthorized" || echo "  No recent errors in launchd logs"
    fi
    docker compose logs --tail=50 cipher 2>/dev/null | grep -i "error\|fail\|exception\|unauthorized\|500" || echo "  No recent errors in container logs"
    echo ""

    # Check for files modified in last 24 hours
    echo "[ Files Modified in Last 24h ]"
    find "$CIPHER_DIR" -maxdepth 3 -name "*.py" -newer "$CIPHER_DIR/.env" -mtime -1 2>/dev/null | head -20 || echo "  None"
    echo ""

    # Check .env modification time
    echo "[ .env Last Modified ]"
    ls -la "$CIPHER_DIR/.env" 2>/dev/null || echo "  .env not found"
    echo ""

    echo -e "${GREEN}Audit complete.${NC} Review above for anomalies."
    ;;

# ========================================
# ROTATE — Interactive key rotation guide
# ========================================
rotate)
    echo -e "${CYAN}═══ CREDENTIAL ROTATION ═══${NC}"
    echo ""
    echo "This guides you through rotating all API keys."
    echo "Recommended: every 90 days or after ANY suspected breach."
    echo ""

    KEYS=(
        "ANTHROPIC_API_KEY:https://console.anthropic.com/"
        "OPENAI_API_KEY:https://platform.openai.com/api-keys"
        "GROQ_API_KEY:https://console.groq.com/keys"
        "DEEPSEEK_API_KEY:https://platform.deepseek.com/"
        "BRAVE_SEARCH_API_KEY:https://brave.com/search/api/"
        "ELEVENLABS_API_KEY:https://elevenlabs.io/"
        "REPLICATE_API_KEY:https://replicate.com/account/api-tokens"
        "FAL_API_KEY:https://fal.ai/dashboard/keys"
        "STABILITY_API_KEY:https://platform.stability.ai/account/keys"
        "TELEGRAM_BOT_TOKEN:Message @BotFather /revoke then /newbot"
        "SLACK_BOT_TOKEN:https://api.slack.com/apps"
        "X_BEARER_TOKEN:https://developer.x.com/en/portal/dashboard"
    )

    for entry in "${KEYS[@]}"; do
        KEY="${entry%%:*}"
        URL="${entry#*:}"
        CURRENT=$(grep "^${KEY}=" "$CIPHER_DIR/.env" 2>/dev/null | cut -d= -f2 | head -c 20)

        if [ -n "$CURRENT" ] && [ "$CURRENT" != "sk-xxxxx" ] && [ "$CURRENT" != "your-" ]; then
            echo -e "  ${YELLOW}[ACTIVE]${NC} $KEY"
            echo "           Current: ${CURRENT}..."
            echo "           Rotate at: $URL"
        else
            echo -e "  ${CYAN}[SKIP]${NC}   $KEY (not configured)"
        fi
        echo ""
    done

    echo "After generating new keys:"
    echo "  1. Update .env with new values"
    echo "  2. Run: docker compose restart"
    echo "  3. Test: curl http://localhost:8000/ping"
    ;;

# ========================================
# HELP
# ========================================
*)
    echo "Cipher Emergency Procedures"
    echo ""
    echo "Usage: $0 <command>"
    echo ""
    echo "Commands:"
    echo "  stop      Kill all Cipher processes immediately"
    echo "  lockdown  Full emergency: stop + key revocation guide"
    echo "  audit     Check for suspicious activity"
    echo "  rotate    Interactive API key rotation guide"
    ;;
esac
