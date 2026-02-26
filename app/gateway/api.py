"""
Elysian Gateway — REST API
Account management, API key CRUD, usage metering, billing endpoints.

All routes prefixed with /api/v1/gateway/
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import logger
from app.core.security import create_access_token, hash_password, verify_password
from app.db.database import get_db
from app.gateway.auth import (
    GatewayAuth, hash_api_key, key_prefix,
    validate_api_key, require_premium, record_usage,
)
from app.gateway.models import (
    ElysianAccount, ElysianAPIKey, ElysianUsage,
    KeyStatus, SubscriptionTier, TIER_LIMITS,
    generate_api_key, generate_uuid,
)


router = APIRouter(prefix="/gateway", tags=["Elysian Gateway"])


# ──────────────────────────────────────────────
# Request / Response Models
# ──────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    display_name: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    token: str
    account_id: str
    email: str
    tier: str
    api_key: Optional[str] = None  # Only returned on registration


class CreateKeyRequest(BaseModel):
    name: str = "Default Key"
    can_chat: bool = True
    can_scan: bool = False
    can_voice: bool = False
    can_cascade: bool = False


class KeyResponse(BaseModel):
    id: str
    name: str
    key_prefix: str
    status: str
    can_chat: bool
    can_scan: bool
    can_voice: bool
    can_cascade: bool
    can_clone_voice: bool
    requests_per_minute: int
    requests_per_day: int
    created_at: str
    last_used_at: Optional[str]


class AccountResponse(BaseModel):
    id: str
    email: str
    display_name: Optional[str]
    tier: str
    is_active: bool
    is_verified: bool
    monthly_token_limit: int
    monthly_request_limit: int
    voice_minutes_limit: int
    daily_scanner_scans: int
    api_key_count: int
    created_at: str


class UsageSummary(BaseModel):
    billing_month: str
    total_tokens: int
    total_requests: int
    total_voice_seconds: int
    total_cost_usd: float
    by_feature: dict
    token_limit: int
    request_limit: int
    token_usage_pct: float
    request_usage_pct: float


class UpgradeRequest(BaseModel):
    tier: str  # "pro" or "enterprise"
    payment_method: str = "stripe"  # "stripe" or "btcpay"


class TierInfo(BaseModel):
    tier: str
    features: dict
    price_monthly_usd: int


# ──────────────────────────────────────────────
# Registration & Login
# ──────────────────────────────────────────────

@router.post("/register", response_model=AuthResponse)
async def register(req: RegisterRequest, db: Session = Depends(get_db)):
    """
    Create a new Elysian Protocol account.
    Returns a JWT token and your first API key.
    """
    # Check existing
    existing = db.query(ElysianAccount).filter(ElysianAccount.email == req.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="Account with this email already exists")

    # Create account
    account = ElysianAccount(
        id=generate_uuid(),
        email=req.email,
        hashed_password=hash_password(req.password),
        display_name=req.display_name or req.email.split("@")[0],
        tier=SubscriptionTier.FREE.value,
        monthly_token_limit=TIER_LIMITS[SubscriptionTier.FREE]["monthly_tokens"],
        monthly_request_limit=TIER_LIMITS[SubscriptionTier.FREE]["monthly_requests"],
    )
    db.add(account)

    # Generate first API key
    raw_key = generate_api_key()
    api_key = ElysianAPIKey(
        id=generate_uuid(),
        account_id=account.id,
        key_hash=hash_api_key(raw_key),
        key_prefix=key_prefix(raw_key),
        name="Default Key",
        can_chat=True,
        can_scan=False,
        can_voice=False,
        can_cascade=False,
    )
    db.add(api_key)
    db.commit()

    # JWT for dashboard access
    token = create_access_token({"sub": account.id, "email": account.email})

    logger.info(f"New Elysian account registered: {req.email}")

    return AuthResponse(
        token=token,
        account_id=account.id,
        email=account.email,
        tier=account.tier,
        api_key=raw_key,  # Only time the full key is returned
    )


@router.post("/login", response_model=AuthResponse)
async def login(req: LoginRequest, db: Session = Depends(get_db)):
    """Authenticate and receive a JWT token."""
    account = db.query(ElysianAccount).filter(ElysianAccount.email == req.email).first()

    if not account or not verify_password(req.password, account.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not account.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")

    token = create_access_token({"sub": account.id, "email": account.email})

    return AuthResponse(
        token=token,
        account_id=account.id,
        email=account.email,
        tier=account.tier,
    )


# ──────────────────────────────────────────────
# Account Management
# ──────────────────────────────────────────────

@router.get("/account", response_model=AccountResponse)
async def get_account(auth: GatewayAuth = Depends(validate_api_key)):
    """Get current account details."""
    account = auth.account
    return AccountResponse(
        id=account.id,
        email=account.email,
        display_name=account.display_name,
        tier=account.tier,
        is_active=account.is_active,
        is_verified=account.is_verified,
        monthly_token_limit=account.monthly_token_limit,
        monthly_request_limit=account.monthly_request_limit,
        voice_minutes_limit=account.voice_minutes_limit,
        daily_scanner_scans=account.daily_scanner_scans,
        api_key_count=len(account.api_keys),
        created_at=account.created_at.isoformat(),
    )


# ──────────────────────────────────────────────
# API Key Management
# ──────────────────────────────────────────────

@router.get("/keys", response_model=list[KeyResponse])
async def list_keys(
    auth: GatewayAuth = Depends(validate_api_key),
    db: Session = Depends(get_db),
):
    """List all API keys for the current account."""
    keys = db.query(ElysianAPIKey).filter(
        ElysianAPIKey.account_id == auth.account_id
    ).order_by(ElysianAPIKey.created_at.desc()).all()

    return [
        KeyResponse(
            id=k.id,
            name=k.name,
            key_prefix=k.key_prefix,
            status=k.status,
            can_chat=k.can_chat,
            can_scan=k.can_scan,
            can_voice=k.can_voice,
            can_cascade=k.can_cascade,
            can_clone_voice=k.can_clone_voice,
            requests_per_minute=k.requests_per_minute,
            requests_per_day=k.requests_per_day,
            created_at=k.created_at.isoformat(),
            last_used_at=k.last_used_at.isoformat() if k.last_used_at else None,
        )
        for k in keys
    ]


@router.post("/keys", response_model=dict)
async def create_key(
    req: CreateKeyRequest,
    auth: GatewayAuth = Depends(validate_api_key),
    db: Session = Depends(get_db),
):
    """Create a new API key. Returns the full key (only shown once)."""
    # Check key limit
    max_keys = auth.tier_limits.get("max_api_keys", 1)
    current_count = db.query(ElysianAPIKey).filter(
        ElysianAPIKey.account_id == auth.account_id,
        ElysianAPIKey.status == KeyStatus.ACTIVE.value,
    ).count()

    if current_count >= max_keys:
        raise HTTPException(
            status_code=403,
            detail=f"Maximum {max_keys} API keys allowed on {auth.tier.value} plan",
        )

    # Validate feature permissions against tier
    if req.can_scan and not auth.can("evolution_scanner"):
        raise HTTPException(status_code=403, detail="Scanner not available on your plan")
    if req.can_voice and not auth.tier_limits.get("situational_voices", 0):
        raise HTTPException(status_code=403, detail="Voice not available on your plan")
    if req.can_cascade and not auth.can("cascade_routing"):
        raise HTTPException(status_code=403, detail="Cascade routing not available on your plan")

    raw_key = generate_api_key()
    api_key = ElysianAPIKey(
        id=generate_uuid(),
        account_id=auth.account_id,
        key_hash=hash_api_key(raw_key),
        key_prefix=key_prefix(raw_key),
        name=req.name,
        can_chat=req.can_chat,
        can_scan=req.can_scan,
        can_voice=req.can_voice,
        can_cascade=req.can_cascade,
    )
    db.add(api_key)
    db.commit()

    logger.info(f"New API key created: {req.name} for account {auth.account_id[:8]}...")

    return {
        "id": api_key.id,
        "name": api_key.name,
        "key": raw_key,  # Only time the full key is shown
        "key_prefix": api_key.key_prefix,
        "message": "Save this key — it will not be shown again.",
    }


@router.delete("/keys/{key_id}")
async def revoke_key(
    key_id: str,
    auth: GatewayAuth = Depends(validate_api_key),
    db: Session = Depends(get_db),
):
    """Revoke an API key. Cannot revoke the key you're using."""
    if key_id == auth.api_key.id:
        raise HTTPException(status_code=400, detail="Cannot revoke the key you are currently using")

    api_key = db.query(ElysianAPIKey).filter(
        ElysianAPIKey.id == key_id,
        ElysianAPIKey.account_id == auth.account_id,
    ).first()

    if not api_key:
        raise HTTPException(status_code=404, detail="Key not found")

    api_key.status = KeyStatus.REVOKED.value
    db.commit()

    return {"message": "Key revoked", "key_id": key_id}


# ──────────────────────────────────────────────
# Usage & Billing
# ──────────────────────────────────────────────

@router.get("/usage", response_model=UsageSummary)
async def get_usage(
    month: Optional[str] = Query(None, description="Billing month (YYYY-MM)"),
    auth: GatewayAuth = Depends(validate_api_key),
    db: Session = Depends(get_db),
):
    """Get usage summary for the current or specified billing month."""
    billing_month = month or datetime.now(timezone.utc).strftime("%Y-%m")

    # Aggregate usage
    records = db.query(ElysianUsage).filter(
        ElysianUsage.account_id == auth.account_id,
        ElysianUsage.billing_month == billing_month,
    ).all()

    total_tokens = sum(r.total_tokens for r in records)
    total_requests = sum(r.request_count for r in records)
    total_voice = sum(r.voice_seconds for r in records)
    total_cost = sum(r.cost_usd for r in records)

    # Group by feature
    by_feature = {}
    for r in records:
        feat = r.feature
        if feat not in by_feature:
            by_feature[feat] = {"tokens": 0, "requests": 0, "cost_usd": 0.0, "voice_seconds": 0}
        by_feature[feat]["tokens"] += r.total_tokens
        by_feature[feat]["requests"] += r.request_count
        by_feature[feat]["cost_usd"] += r.cost_usd
        by_feature[feat]["voice_seconds"] += r.voice_seconds

    token_limit = auth.account.monthly_token_limit
    request_limit = auth.account.monthly_request_limit

    return UsageSummary(
        billing_month=billing_month,
        total_tokens=total_tokens,
        total_requests=total_requests,
        total_voice_seconds=total_voice,
        total_cost_usd=round(total_cost, 4),
        by_feature=by_feature,
        token_limit=token_limit,
        request_limit=request_limit,
        token_usage_pct=round((total_tokens / max(token_limit, 1)) * 100, 1),
        request_usage_pct=round((total_requests / max(request_limit, 1)) * 100, 1),
    )


@router.get("/usage/history")
async def get_usage_history(
    months: int = Query(6, ge=1, le=24),
    auth: GatewayAuth = Depends(validate_api_key),
    db: Session = Depends(get_db),
):
    """Get usage history for the last N months."""
    results = []
    now = datetime.now(timezone.utc)

    for i in range(months):
        month_date = now - timedelta(days=30 * i)
        billing_month = month_date.strftime("%Y-%m")

        records = db.query(ElysianUsage).filter(
            ElysianUsage.account_id == auth.account_id,
            ElysianUsage.billing_month == billing_month,
        ).all()

        results.append({
            "month": billing_month,
            "total_tokens": sum(r.total_tokens for r in records),
            "total_requests": sum(r.request_count for r in records),
            "total_cost_usd": round(sum(r.cost_usd for r in records), 4),
            "voice_seconds": sum(r.voice_seconds for r in records),
        })

    return {"history": results}


# ──────────────────────────────────────────────
# Tier & Pricing
# ──────────────────────────────────────────────

@router.get("/tiers", response_model=list[TierInfo])
async def list_tiers():
    """List all available subscription tiers and their features."""
    return [
        TierInfo(
            tier=tier.value,
            features=limits,
            price_monthly_usd=limits["price_monthly_usd"],
        )
        for tier, limits in TIER_LIMITS.items()
    ]


@router.post("/upgrade")
async def upgrade_tier(
    req: UpgradeRequest,
    auth: GatewayAuth = Depends(validate_api_key),
    db: Session = Depends(get_db),
):
    """
    Initiate a tier upgrade.
    In production, this creates a Stripe/BTCPay checkout session.
    For now, it upgrades immediately (development mode).
    """
    target_tier = req.tier.lower()
    if target_tier not in ("pro", "business", "enterprise"):
        raise HTTPException(status_code=400, detail="Invalid tier. Choose 'pro', 'business', or 'enterprise'")

    if auth.tier.value == target_tier:
        raise HTTPException(status_code=400, detail=f"Already on {target_tier} plan")

    # In development mode, upgrade immediately
    if settings.app_env == "development":
        tier_enum = SubscriptionTier(target_tier)
        limits = TIER_LIMITS[tier_enum]

        account = auth.account
        account.tier = target_tier
        account.monthly_token_limit = limits["monthly_tokens"]
        account.monthly_request_limit = limits["monthly_requests"]
        account.daily_scanner_scans = limits["daily_scans"]
        account.voice_minutes_limit = limits["voice_minutes"]

        # Update existing keys with new permissions
        for key in account.api_keys:
            if key.status == KeyStatus.ACTIVE.value:
                key.can_scan = bool(limits.get("evolution_scanner"))
                key.can_voice = bool(limits.get("situational_voices", 0))
                key.can_cascade = bool(limits.get("cascade_routing"))
                key.can_clone_voice = bool(limits.get("voice_cloning"))

        db.commit()

        logger.info(f"Account {account.id[:8]}... upgraded to {target_tier}")

        return {
            "message": f"Upgraded to {target_tier}!",
            "tier": target_tier,
            "features": limits,
            "note": "Development mode — no payment required",
        }

    # Production: create checkout session
    if req.payment_method == "stripe":
        # TODO: Integrate Stripe checkout
        return {
            "checkout_url": f"https://checkout.stripe.com/pay?tier={target_tier}",
            "message": "Complete payment to activate your upgrade",
        }
    elif req.payment_method == "btcpay":
        # TODO: Integrate BTCPay
        return {
            "checkout_url": f"{settings.btcpay_url}/checkout?tier={target_tier}",
            "message": "Complete Bitcoin payment to activate your upgrade",
        }


# ──────────────────────────────────────────────
# Health & Status
# ──────────────────────────────────────────────

@router.get("/health")
async def gateway_health():
    """Gateway health check."""
    return {
        "status": "operational",
        "service": "Elysian Gateway",
        "version": "1.0.0",
        "tiers_available": [t.value for t in SubscriptionTier],
        "features": [
            "api_key_auth",
            "rate_limiting",
            "usage_metering",
            "tier_management",
            "feature_gating",
        ],
    }


@router.get("/features")
async def check_features(auth: GatewayAuth = Depends(validate_api_key)):
    """Check which features are available for the current API key."""
    limits = auth.tier_limits
    return {
        "account_id": auth.account_id,
        "tier": auth.tier.value,
        "features": {
            "chat": auth.api_key.can_chat,
            "evolution_scanner": bool(limits.get("evolution_scanner")),
            "situational_voices": limits.get("situational_voices", 0),
            "cascade_routing": bool(limits.get("cascade_routing")),
            "emotion_detection": bool(limits.get("emotion_detection")),
            "voice_cloning": bool(limits.get("voice_cloning")),
            "education_voices": bool(limits.get("education_voices")),
            "priority_models": bool(limits.get("priority_models")),
            "weekly_briefings": bool(limits.get("weekly_briefings")),
            "api_webhooks": bool(limits.get("api_webhooks")),
            "white_label": bool(limits.get("white_label")),
            "custom_voice_design": bool(limits.get("custom_voice_design")),
        },
        "limits": {
            "monthly_tokens": auth.account.monthly_token_limit,
            "monthly_requests": auth.account.monthly_request_limit,
            "voice_minutes": auth.account.voice_minutes_limit,
            "daily_scans": auth.account.daily_scanner_scans,
            "max_conversations": limits.get("max_conversations", 50),
            "requests_per_minute": auth.api_key.requests_per_minute,
            "requests_per_day": auth.api_key.requests_per_day,
        },
        "upgrade_hook": limits.get("upgrade_hook"),
    }
