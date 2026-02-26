"""
Elysian Gateway — Feature Guards
Middleware that checks premium features against the user's tier.

These are decorators/dependencies for protecting existing routes
without rewriting them entirely.

Usage:
    from app.gateway.guards import premium_scanner, premium_voice

    @router.get("/scan", dependencies=[Depends(premium_scanner)])
    async def trigger_scan():
        ...
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Header, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import logger
from app.db.database import get_db
from app.gateway.auth import (
    GatewayAuth, hash_api_key, validate_api_key,
    optional_api_key, record_usage,
)
from app.gateway.models import (
    ElysianAccount, ElysianAPIKey, ElysianUsage,
    SubscriptionTier, TIER_LIMITS,
)


# ──────────────────────────────────────────────
# Development Mode Bypass
# ──────────────────────────────────────────────

def _is_dev_mode() -> bool:
    """In development mode, allow bypass for local testing."""
    return settings.app_env == "development"


# ──────────────────────────────────────────────
# Premium Feature Guards
# ──────────────────────────────────────────────

async def premium_scanner(
    request: Request,
    x_elysian_key: Optional[str] = Header(None, alias="X-Elysian-Key"),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """
    Guard for evolution scanner endpoints.
    In dev mode: allows access without a key.
    In production: requires Pro+ with scanner permission.
    """
    if _is_dev_mode():
        # Dev mode: allow without key, but still validate if key is provided
        auth = await optional_api_key(request, x_elysian_key, authorization, db)
        if auth and not auth.can("evolution_scanner"):
            raise HTTPException(
                status_code=403,
                detail="Scanner not available on your plan",
            )
        return auth

    # Production mode: key required
    auth = await validate_api_key(request, x_elysian_key, authorization, db)
    if not auth.can("evolution_scanner"):
        raise HTTPException(
            status_code=403,
            detail={
                "error": "upgrade_required",
                "message": "Evolution scanner requires Elysian Pro or Enterprise",
                "upgrade_url": "https://elysianprotocol.com/pricing",
            },
        )
    return auth


async def premium_voice(
    request: Request,
    x_elysian_key: Optional[str] = Header(None, alias="X-Elysian-Key"),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """
    Guard for voice/audio endpoints.
    In dev mode: allows access without a key.
    In production: requires Pro+ with voice permission.
    """
    if _is_dev_mode():
        auth = await optional_api_key(request, x_elysian_key, authorization, db)
        if auth and not auth.tier_limits.get("situational_voices", 0):
            raise HTTPException(
                status_code=403,
                detail="Voice features not available on your plan",
            )
        return auth

    auth = await validate_api_key(request, x_elysian_key, authorization, db)
    if not auth.tier_limits.get("situational_voices", 0):
        raise HTTPException(
            status_code=403,
            detail={
                "error": "upgrade_required",
                "message": "Voice features require Elysian Pro or Enterprise",
                "upgrade_url": "https://elysianprotocol.com/pricing",
            },
        )
    return auth


async def premium_cascade(
    request: Request,
    x_elysian_key: Optional[str] = Header(None, alias="X-Elysian-Key"),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """
    Guard for cascade/FrugalGPT routing.
    In dev mode: allows access without a key.
    In production: requires Pro+ with cascade permission.
    """
    if _is_dev_mode():
        auth = await optional_api_key(request, x_elysian_key, authorization, db)
        return auth

    auth = await validate_api_key(request, x_elysian_key, authorization, db)
    if not auth.can("cascade_routing"):
        raise HTTPException(
            status_code=403,
            detail={
                "error": "upgrade_required",
                "message": "Cascade routing requires Elysian Pro or Enterprise",
                "upgrade_url": "https://elysianprotocol.com/pricing",
            },
        )
    return auth


async def premium_voice_clone(
    request: Request,
    x_elysian_key: Optional[str] = Header(None, alias="X-Elysian-Key"),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """
    Guard for voice cloning (Enterprise only).
    """
    if _is_dev_mode():
        auth = await optional_api_key(request, x_elysian_key, authorization, db)
        return auth

    auth = await validate_api_key(request, x_elysian_key, authorization, db)
    if not auth.can("voice_cloning"):
        raise HTTPException(
            status_code=403,
            detail={
                "error": "enterprise_required",
                "message": "Voice cloning requires Elysian Enterprise",
                "upgrade_url": "https://elysianprotocol.com/pricing",
            },
        )
    return auth


# ──────────────────────────────────────────────
# Usage Checking (against monthly limits)
# ──────────────────────────────────────────────

async def check_token_budget(
    auth: Optional[GatewayAuth],
    db: Session,
    estimated_tokens: int = 1000,
) -> bool:
    """
    Check if the account has enough token budget remaining.
    Returns True if within limits, raises HTTPException if over.
    """
    if not auth:
        return True  # No auth = local mode, no limits

    billing_month = datetime.now(timezone.utc).strftime("%Y-%m")

    # Sum tokens used this month
    used = db.query(
        func.coalesce(func.sum(ElysianUsage.total_tokens), 0)
    ).filter(
        ElysianUsage.account_id == auth.account_id,
        ElysianUsage.billing_month == billing_month,
    ).scalar()

    remaining = auth.account.monthly_token_limit - used

    if remaining < estimated_tokens:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "token_limit_exceeded",
                "message": f"Monthly token limit reached ({auth.account.monthly_token_limit:,} tokens)",
                "used": used,
                "limit": auth.account.monthly_token_limit,
                "resets": f"{billing_month}-01T00:00:00Z",
                "upgrade_url": "https://elysianprotocol.com/pricing",
            },
        )

    return True


async def check_voice_budget(
    auth: Optional[GatewayAuth],
    db: Session,
    estimated_seconds: int = 30,
) -> bool:
    """Check voice minute budget."""
    if not auth:
        return True

    billing_month = datetime.now(timezone.utc).strftime("%Y-%m")

    used_seconds = db.query(
        func.coalesce(func.sum(ElysianUsage.voice_seconds), 0)
    ).filter(
        ElysianUsage.account_id == auth.account_id,
        ElysianUsage.billing_month == billing_month,
    ).scalar()

    limit_seconds = auth.account.voice_minutes_limit * 60
    remaining = limit_seconds - used_seconds

    if remaining < estimated_seconds:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "voice_limit_exceeded",
                "message": f"Monthly voice limit reached ({auth.account.voice_minutes_limit} minutes)",
                "used_minutes": round(used_seconds / 60, 1),
                "limit_minutes": auth.account.voice_minutes_limit,
                "upgrade_url": "https://elysianprotocol.com/pricing",
            },
        )

    return True


# Need sqlalchemy func import
from sqlalchemy import func
