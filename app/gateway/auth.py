"""
Elysian Gateway — Authentication Middleware
API key validation, rate limiting, and feature gating.

Usage in routes:
    @router.get("/premium-feature")
    async def premium(auth: GatewayAuth = Depends(require_premium)):
        ...
"""

import hashlib
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import logger
from app.db.database import get_db
from app.gateway.models import (
    ElysianAccount, ElysianAPIKey, ElysianUsage,
    KeyStatus, SubscriptionTier, TIER_LIMITS
)


# ──────────────────────────────────────────────
# In-memory rate limit cache (Redis replacement)
# ──────────────────────────────────────────────

class RateLimiter:
    """Simple in-memory sliding window rate limiter."""

    def __init__(self):
        self._minute_windows: dict[str, list[float]] = defaultdict(list)
        self._day_counts: dict[str, int] = defaultdict(int)
        self._day_key_cache: dict[str, str] = {}

    def _current_day(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def check_rate_limit(self, key_id: str, rpm_limit: int, rpd_limit: int) -> tuple[bool, str]:
        """Returns (allowed, reason)."""
        now = time.time()
        day = self._current_day()

        # Minute window: clear entries older than 60s
        window = self._minute_windows[key_id]
        window[:] = [t for t in window if now - t < 60]

        if len(window) >= rpm_limit:
            return False, f"Rate limit exceeded: {rpm_limit} requests/minute"

        # Day window: reset if new day
        day_key = f"{key_id}:{day}"
        if self._day_key_cache.get(key_id) != day:
            self._day_counts[key_id] = 0
            self._day_key_cache[key_id] = day

        if self._day_counts[key_id] >= rpd_limit:
            return False, f"Daily limit exceeded: {rpd_limit} requests/day"

        # Record this request
        window.append(now)
        self._day_counts[key_id] += 1

        return True, ""

    def cleanup(self):
        """Periodic cleanup of stale entries."""
        now = time.time()
        stale_keys = []
        for key_id, window in self._minute_windows.items():
            window[:] = [t for t in window if now - t < 60]
            if not window and self._day_key_cache.get(key_id, "") != self._current_day():
                stale_keys.append(key_id)
        for k in stale_keys:
            del self._minute_windows[k]
            self._day_counts.pop(k, None)
            self._day_key_cache.pop(k, None)


rate_limiter = RateLimiter()


# ──────────────────────────────────────────────
# API Key Hashing
# ──────────────────────────────────────────────

def hash_api_key(key: str) -> str:
    """SHA-256 hash for API key storage. Keys are never stored in plaintext."""
    return hashlib.sha256(key.encode()).hexdigest()


def key_prefix(key: str) -> str:
    """Extract display prefix: ely_sk_xxxx..."""
    return key[:16] + "..."


# ──────────────────────────────────────────────
# Gateway Auth Result
# ──────────────────────────────────────────────

class GatewayAuth:
    """Resolved auth context available in route handlers."""

    def __init__(
        self,
        account: ElysianAccount,
        api_key: ElysianAPIKey,
        tier: SubscriptionTier,
        tier_limits: dict,
    ):
        self.account = account
        self.api_key = api_key
        self.tier = tier
        self.tier_limits = tier_limits
        self.account_id = account.id
        self.is_premium = account.is_premium

    def can(self, feature: str) -> bool:
        """Check if the current tier allows a feature."""
        return self.tier_limits.get(feature, False)

    def feature_limit(self, feature: str) -> int:
        """Get the numeric limit for a feature."""
        return self.tier_limits.get(feature, 0)


# ──────────────────────────────────────────────
# Dependency: Validate API Key
# ──────────────────────────────────────────────

async def validate_api_key(
    request: Request,
    x_elysian_key: Optional[str] = Header(None, alias="X-Elysian-Key"),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
) -> GatewayAuth:
    """
    Extract and validate the Elysian API key from request headers.
    Supports: X-Elysian-Key header or Authorization: Bearer <key>
    """
    # Extract key from headers
    raw_key = None
    if x_elysian_key:
        raw_key = x_elysian_key
    elif authorization and authorization.startswith("Bearer ely_sk_"):
        raw_key = authorization.removeprefix("Bearer ").strip()

    if not raw_key:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "missing_api_key",
                "message": "Elysian API key required. Include X-Elysian-Key header or Authorization: Bearer ely_sk_...",
                "docs": "https://elysianprotocol.com/docs/auth",
            },
        )

    if not raw_key.startswith("ely_sk_"):
        raise HTTPException(
            status_code=401,
            detail={
                "error": "invalid_key_format",
                "message": "API key must start with ely_sk_",
            },
        )

    # Look up key
    key_hashed = hash_api_key(raw_key)
    api_key = db.query(ElysianAPIKey).filter(ElysianAPIKey.key_hash == key_hashed).first()

    if not api_key:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "invalid_api_key",
                "message": "API key not found or invalid",
            },
        )

    if not api_key.is_valid:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "key_inactive",
                "message": f"API key is {api_key.status}",
            },
        )

    # Load account
    account = db.query(ElysianAccount).filter(ElysianAccount.id == api_key.account_id).first()

    if not account or not account.is_active:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "account_inactive",
                "message": "Account is disabled or not found",
            },
        )

    # Rate limiting
    allowed, reason = rate_limiter.check_rate_limit(
        api_key.id,
        api_key.requests_per_minute,
        api_key.requests_per_day,
    )
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "rate_limited",
                "message": reason,
            },
        )

    # Update last used
    api_key.last_used_at = datetime.now(timezone.utc)
    db.commit()

    # Build auth context
    tier = SubscriptionTier(account.tier)
    tier_limits = TIER_LIMITS.get(tier, TIER_LIMITS[SubscriptionTier.FREE])

    return GatewayAuth(
        account=account,
        api_key=api_key,
        tier=tier,
        tier_limits=tier_limits,
    )


# ──────────────────────────────────────────────
# Dependency: Optional API Key (for mixed routes)
# ──────────────────────────────────────────────

async def optional_api_key(
    request: Request,
    x_elysian_key: Optional[str] = Header(None, alias="X-Elysian-Key"),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
) -> Optional[GatewayAuth]:
    """
    Validate API key if present, return None if not.
    Use for routes that work in both free and premium modes.
    """
    has_key = bool(x_elysian_key) or (authorization and "ely_sk_" in (authorization or ""))
    if not has_key:
        return None

    try:
        return await validate_api_key(request, x_elysian_key, authorization, db)
    except HTTPException:
        return None


# ──────────────────────────────────────────────
# Dependency: Require Premium
# ──────────────────────────────────────────────

async def require_premium(
    auth: GatewayAuth = Depends(validate_api_key),
) -> GatewayAuth:
    """Require a valid API key with Pro or Enterprise tier."""
    if not auth.is_premium:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "upgrade_required",
                "message": "This feature requires Elysian Pro or Enterprise",
                "current_tier": auth.tier.value,
                "upgrade_url": "https://elysianprotocol.com/pricing",
            },
        )
    return auth


# ──────────────────────────────────────────────
# Dependency: Require Specific Feature
# ──────────────────────────────────────────────

def require_feature(feature: str):
    """Factory for feature-specific auth dependencies."""
    async def _check(auth: GatewayAuth = Depends(validate_api_key)):
        if not auth.can(feature):
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "feature_not_available",
                    "message": f"Feature '{feature}' is not available on your {auth.tier.value} plan",
                    "upgrade_url": "https://elysianprotocol.com/pricing",
                },
            )
        return auth
    return _check


# ──────────────────────────────────────────────
# Usage Recording Helper
# ──────────────────────────────────────────────

def record_usage(
    db: Session,
    auth: GatewayAuth,
    feature: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    voice_seconds: int = 0,
    cost_usd: float = 0.0,
    model: str = "",
    provider: str = "",
    latency_ms: float = 0.0,
):
    """Record usage for billing and metering."""
    billing_month = datetime.now(timezone.utc).strftime("%Y-%m")

    usage = ElysianUsage(
        account_id=auth.account_id,
        api_key_id=auth.api_key.id,
        feature=feature,
        model=model,
        provider=provider,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
        voice_seconds=voice_seconds,
        cost_usd=cost_usd,
        latency_ms=latency_ms,
        billing_month=billing_month,
    )
    db.add(usage)
    db.commit()

    logger.debug(
        f"Usage recorded: {feature} | account={auth.account_id[:8]}... | "
        f"tokens={input_tokens + output_tokens} | cost=${cost_usd:.4f}"
    )
