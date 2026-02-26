"""
Elysian Gateway — Premium Route Wrappers & Feature Availability
"""

from typing import Optional

from fastapi import APIRouter, Depends, Header

from app.core.config import settings
from app.gateway.guards import premium_scanner, premium_voice, premium_voice_clone


# Premium routers (auth-gated)
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


availability_router = APIRouter(tags=["Features"])


@availability_router.get("/features/available")
async def get_available_features(
    x_elysian_key: Optional[str] = Header(None, alias="X-Elysian-Key"),
):
    """
    Feature availability map — drives the iOS app's upgrade UI.
    Every locked feature shows which tier unlocks it and a conversion hook.
    """
    is_dev = settings.app_env == "development"
    has_key = bool(x_elysian_key)

    return {
        "mode": "development" if is_dev else "production",
        "has_api_key": has_key,
        "tiers": {
            "free": {"price": 0, "name": "Free", "tagline": "Meet Cipher"},
            "pro": {"price": 29, "name": "Pro", "tagline": "Cipher adapts to you"},
            "business": {"price": 79, "name": "Business", "tagline": "Build with every voice"},
            "enterprise": {"price": 199, "name": "Enterprise", "tagline": "Own your voice"},
        },
        "features": {
            # ── FREE (all users) ──
            "chat": {
                "available": True, "tier": "free",
                "description": "AI chat — text always works, voice is a layer on top",
            },
            "streaming": {
                "available": True, "tier": "free",
                "description": "Real-time streaming responses",
            },
            "cipher_voice": {
                "available": True, "tier": "free",
                "description": "Cipher's voice — 15 min/month included free",
            },
            "text_mode": {
                "available": True, "tier": "free",
                "description": "Full text chat — always available, voice is optional",
            },
            "voice_opt_out": {
                "available": True, "tier": "free",
                "description": "Turn off voice anytime — text-only mode",
            },
            "custom_prompts": {
                "available": True, "tier": "free",
                "description": "Custom system prompts",
            },

            # ── PRO ($29) ──
            "situational_voices_4": {
                "available": has_key or is_dev, "tier": "pro",
                "description": "4 situational voices: Motivator, Anchor, Philosopher, Creative",
                "upgrade_cta": "Cipher adapts HOW it speaks to what you need",
            },
            "emotion_detection": {
                "available": has_key or is_dev, "tier": "pro",
                "description": "Cipher reads your emotional state from voice",
                "upgrade_cta": "Cipher reads the room — voice shifts automatically",
            },
            "cascade_routing": {
                "available": has_key or is_dev, "tier": "pro",
                "description": "Faster, smarter model routing",
                "upgrade_cta": "3x faster responses",
            },
            "evolution_scanner": {
                "available": has_key or is_dev, "tier": "pro",
                "description": "Daily AI evolution scanner",
                "upgrade_cta": "Know what's happening in AI before anyone",
            },
            "priority_models": {
                "available": has_key or is_dev, "tier": "pro",
                "description": "Access to Claude/GPT-4 class models",
            },
            "live_voice_chat": {
                "available": has_key or is_dev, "tier": "pro",
                "description": "Conversational live voice — fast, flowing, interruptible",
                "upgrade_cta": "Talk to Cipher like a real conversation",
            },

            # ── BUSINESS ($79) ──
            "all_situational_voices": {
                "available": False, "tier": "business",
                "description": "All 7 voices: +Strategist, Coach, Educator",
                "upgrade_cta": "Every voice for every situation",
            },
            "education_voices": {
                "available": False, "tier": "business",
                "description": "Education characters: Nonna Maria (Italian), The Sage (Philosophy), Blues (Harmonica), Dr. Nova (Physics), and more",
                "upgrade_cta": "Learn anything with character-driven teaching voices",
            },
            "voice_5_hours": {
                "available": False, "tier": "business",
                "description": "5 hours voice/month",
            },
            "weekly_briefings": {
                "available": False, "tier": "business",
                "description": "Weekly AI evolution briefings",
            },

            # ── ENTERPRISE ($199) ──
            "voice_cloning": {
                "available": False, "tier": "enterprise",
                "description": "Clone your own voice with consent",
                "upgrade_cta": "Create your voice for voiceovers, courses, content",
            },
            "custom_voice_design": {
                "available": False, "tier": "enterprise",
                "description": "Design entirely new synthetic voices",
            },
            "white_label": {
                "available": False, "tier": "enterprise",
                "description": "Remove Elysian branding",
            },
        },
        "upgrade_url": "https://elysianprotocol.com/pricing",
    }
