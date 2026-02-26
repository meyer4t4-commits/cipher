"""
Elysian Gateway — Premium Route Wrappers & Feature Availability
Adds gateway authentication to existing scanner and voice routes.

In development mode: all routes work without API key (for local testing)
In production mode: premium routes require valid Elysian API key
"""

from typing import Optional

from fastapi import APIRouter, Depends, Header

from app.core.config import settings
from app.gateway.guards import premium_scanner, premium_voice, premium_voice_clone


# ──────────────────────────────────────────────
# Premium Routers (auth-gated)
# ──────────────────────────────────────────────

premium_scanner_router = APIRouter(
    prefix="/premium/scanner",
    tags=["Premium: Scanner"],
    dependencies=[Depends(premium_scanner)],
)

premium_voice_router = APIRouter(
    prefix="/premium/voice",
    tags=["Premium: Voice"],
    dependencies=[Depends(premium_voice)],
)

premium_evolution_router = APIRouter(
    prefix="/premium/evolution",
    tags=["Premium: Evolution"],
    dependencies=[Depends(premium_scanner)],
)


# ──────────────────────────────────────────────
# Feature Availability (no auth — shows the funnel)
# ──────────────────────────────────────────────

availability_router = APIRouter(tags=["Features"])


@availability_router.get("/features/available")
async def get_available_features(
    x_elysian_key: Optional[str] = Header(None, alias="X-Elysian-Key"),
):
    """
    Feature availability map — drives the iOS app's upgrade UI.
    Every locked feature shows which tier unlocks it and WHY they want it.
    This endpoint is the conversion engine.
    """
    is_dev = settings.app_env == "development"
    has_key = bool(x_elysian_key)

    return {
        "mode": "development" if is_dev else "production",
        "has_api_key": has_key,
        "tiers": {
            "free": {"price": 0, "name": "Free", "tagline": "Meet Cipher"},
            "pro": {"price": 29, "name": "Pro", "tagline": "Hear Cipher"},
            "business": {"price": 79, "name": "Business", "tagline": "Build with Cipher"},
            "enterprise": {"price": 199, "name": "Enterprise", "tagline": "Become Cipher"},
        },
        "features": {
            # ── FREE TIER ──
            "chat": {
                "available": True,
                "tier": "free",
                "description": "AI chat with your own API keys",
            },
            "streaming": {
                "available": True,
                "tier": "free",
                "description": "Real-time streaming responses",
            },
            "custom_prompts": {
                "available": True,
                "tier": "free",
                "description": "Custom system prompts",
            },
            "basic_models": {
                "available": True,
                "tier": "free",
                "description": "Basic model routing",
            },

            # ── PRO TIER ($29) ── upgrade hooks for free users
            "voice_synthesis": {
                "available": has_key or is_dev,
                "tier": "pro",
                "description": "Hear Cipher speak — 60 min/month",
                "upgrade_cta": "Upgrade to hear Cipher's voice",
            },
            "emotion_detection": {
                "available": has_key or is_dev,
                "tier": "pro",
                "description": "Cipher reads your emotional state from voice",
                "upgrade_cta": "Cipher can read the room — upgrade to Pro",
            },
            "voice_personalities_3": {
                "available": has_key or is_dev,
                "tier": "pro",
                "description": "3 voice modes: Cipher Core, Motivator, Anchor",
                "upgrade_cta": "Three voices, one daemon",
            },
            "cascade_routing": {
                "available": has_key or is_dev,
                "tier": "pro",
                "description": "FrugalGPT — faster, smarter model routing",
                "upgrade_cta": "Pro users get 3x faster responses",
            },
            "evolution_scanner": {
                "available": has_key or is_dev,
                "tier": "pro",
                "description": "Daily AI evolution scanner (60+ sources)",
                "upgrade_cta": "Know what's happening in AI before anyone else",
            },
            "priority_models": {
                "available": has_key or is_dev,
                "tier": "pro",
                "description": "Access Claude, GPT-4 class models",
                "upgrade_cta": "Unlock the most powerful models",
            },
            "conversation_export": {
                "available": has_key or is_dev,
                "tier": "pro",
                "description": "Export conversations as markdown/JSON",
                "upgrade_cta": "Own your conversations",
            },

            # ── BUSINESS TIER ($79) ── upgrade hooks for pro users
            "voice_personalities_all": {
                "available": False,
                "tier": "business",
                "description": "All 8 voice personalities unlocked",
                "upgrade_cta": "Unlock Strategist, Philosopher, Coach, Educator, Creative",
            },
            "education_voices": {
                "available": False,
                "tier": "business",
                "description": "10 education voices — Italian, Mandarin, Philosophy, Music, Science",
                "upgrade_cta": "Build your education platform with custom teaching voices",
            },
            "voice_5_hours": {
                "available": False,
                "tier": "business",
                "description": "5 hours of voice per month (vs 1 hour on Pro)",
                "upgrade_cta": "5x more voice time",
            },
            "weekly_briefings": {
                "available": False,
                "tier": "business",
                "description": "Weekly AI evolution briefings in JSON + Markdown",
                "upgrade_cta": "Get a weekly intelligence briefing",
            },
            "api_webhooks": {
                "available": False,
                "tier": "business",
                "description": "Webhook notifications for scanner findings",
                "upgrade_cta": "Get notified when AI drops something big",
            },
            "unlimited_conversations": {
                "available": False,
                "tier": "business",
                "description": "Unlimited conversation history",
                "upgrade_cta": "Never lose a conversation",
            },

            # ── ENTERPRISE TIER ($199) ── upgrade hooks for business users
            "voice_cloning": {
                "available": False,
                "tier": "enterprise",
                "description": "Clone your own voice with consent",
                "upgrade_cta": "Create your voice — for voiceovers, content, education",
            },
            "custom_voice_design": {
                "available": False,
                "tier": "enterprise",
                "description": "Design entirely new synthetic voices",
                "upgrade_cta": "Build voices that don't exist yet",
            },
            "white_label": {
                "available": False,
                "tier": "enterprise",
                "description": "Remove Elysian branding — make it yours",
                "upgrade_cta": "White-label Cipher for your business",
            },
            "voice_20_hours": {
                "available": False,
                "tier": "enterprise",
                "description": "20 hours of voice per month",
                "upgrade_cta": "Unlimited voice for your entire operation",
            },
            "sla_guarantee": {
                "available": False,
                "tier": "enterprise",
                "description": "99.9% uptime SLA guarantee",
                "upgrade_cta": "Enterprise-grade reliability",
            },
            "realtime_scanner": {
                "available": False,
                "tier": "enterprise",
                "description": "10x daily scans — near real-time monitoring",
                "upgrade_cta": "Know everything, the moment it happens",
            },
        },
        "upgrade_url": "https://elysianprotocol.com/pricing",
    }
