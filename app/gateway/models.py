"""
Elysian Gateway — Database Models
API keys, subscriptions, usage metering, and billing.
"""

import secrets
import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey,
    Integer, String, Text, UniqueConstraint, Index
)
from sqlalchemy.orm import relationship

from app.db.database import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def generate_api_key() -> str:
    """Generate a secure Elysian API key: ely_sk_<48 random chars>"""
    return f"ely_sk_{secrets.token_urlsafe(36)}"


class SubscriptionTier(str, Enum):
    FREE = "free"           # $0  — hook them, let them feel the ceiling
    PRO = "pro"             # $29 — unlock the magic, create the habit
    BUSINESS = "business"   # $79 — they're building on it now, need more
    ENTERPRISE = "enterprise"  # $199 — they can't operate without it


class KeyStatus(str, Enum):
    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"
    SUSPENDED = "suspended"


# ──────────────────────────────────────────────
# Elysian Account (the billing entity)
# ──────────────────────────────────────────────

class ElysianAccount(Base):
    """
    An Elysian Protocol account — the billing and subscription entity.
    One account can have multiple API keys and multiple Orchid users.
    """
    __tablename__ = "elysian_accounts"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    display_name = Column(String(100), nullable=True)

    # Subscription
    tier = Column(String(20), default=SubscriptionTier.FREE.value, nullable=False)
    stripe_customer_id = Column(String(255), nullable=True)
    stripe_subscription_id = Column(String(255), nullable=True)
    btcpay_customer_id = Column(String(255), nullable=True)

    # Limits (overridable per account)
    monthly_token_limit = Column(Integer, default=100_000)  # Free tier default
    monthly_request_limit = Column(Integer, default=1_000)
    daily_scanner_scans = Column(Integer, default=0)  # 0 = disabled for free
    voice_minutes_limit = Column(Integer, default=0)  # 0 = disabled for free

    # Status
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    # Relationships
    api_keys = relationship("ElysianAPIKey", back_populates="account", cascade="all, delete-orphan")
    usage_records = relationship("ElysianUsage", back_populates="account", cascade="all, delete-orphan")

    @property
    def tier_enum(self) -> SubscriptionTier:
        return SubscriptionTier(self.tier)

    @property
    def is_premium(self) -> bool:
        return self.tier in (
            SubscriptionTier.PRO.value,
            SubscriptionTier.BUSINESS.value,
            SubscriptionTier.ENTERPRISE.value,
        )


# ──────────────────────────────────────────────
# API Keys
# ──────────────────────────────────────────────

class ElysianAPIKey(Base):
    """
    API key for authenticating with the Elysian Gateway.
    Each key is scoped to an account and can have custom permissions.
    """
    __tablename__ = "elysian_api_keys"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    account_id = Column(String(36), ForeignKey("elysian_accounts.id"), nullable=False, index=True)
    key_hash = Column(String(255), nullable=False, unique=True, index=True)
    key_prefix = Column(String(20), nullable=False)  # First 12 chars for display: ely_sk_xxxx...
    name = Column(String(100), default="Default Key")

    # Permissions (granular feature gating)
    can_chat = Column(Boolean, default=True)
    can_scan = Column(Boolean, default=False)
    can_voice = Column(Boolean, default=False)
    can_cascade = Column(Boolean, default=False)
    can_clone_voice = Column(Boolean, default=False)

    # Rate limiting
    requests_per_minute = Column(Integer, default=60)
    requests_per_day = Column(Integer, default=10_000)

    # Status
    status = Column(String(20), default=KeyStatus.ACTIVE.value, nullable=False)
    last_used_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    # Relationships
    account = relationship("ElysianAccount", back_populates="api_keys")

    @property
    def is_valid(self) -> bool:
        if self.status != KeyStatus.ACTIVE.value:
            return False
        if self.expires_at and self.expires_at < utcnow():
            return False
        return True


# ──────────────────────────────────────────────
# Usage Metering
# ──────────────────────────────────────────────

class ElysianUsage(Base):
    """
    Usage records for billing and metering.
    Tracks tokens, requests, voice minutes, scanner scans.
    """
    __tablename__ = "elysian_usage"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(String(36), ForeignKey("elysian_accounts.id"), nullable=False, index=True)
    api_key_id = Column(String(36), ForeignKey("elysian_api_keys.id"), nullable=True)

    # What was used
    feature = Column(String(50), nullable=False)  # chat, scanner, voice, cascade, clone
    model = Column(String(100), nullable=True)
    provider = Column(String(50), nullable=True)

    # Quantities
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    voice_seconds = Column(Integer, default=0)
    request_count = Column(Integer, default=1)

    # Cost
    cost_usd = Column(Float, default=0.0)
    latency_ms = Column(Float, default=0.0)

    # Billing period
    billing_month = Column(String(7), nullable=False)  # "2026-02" format
    created_at = Column(DateTime, default=utcnow)

    # Relationships
    account = relationship("ElysianAccount", back_populates="usage_records")

    __table_args__ = (
        Index("ix_usage_billing", "account_id", "billing_month"),
        Index("ix_usage_feature", "account_id", "feature", "billing_month"),
    )


# ──────────────────────────────────────────────
# Rate Limit Tracking (in-memory + DB backup)
# ──────────────────────────────────────────────

class RateLimitEntry(Base):
    """
    Persistent rate limit state.
    In production, this would be Redis. SQLite works for single-server.
    """
    __tablename__ = "elysian_rate_limits"

    id = Column(Integer, primary_key=True, autoincrement=True)
    api_key_id = Column(String(36), nullable=False, index=True)
    window_key = Column(String(50), nullable=False)  # "minute:2026-02-26T14:30" or "day:2026-02-26"
    request_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=utcnow)

    __table_args__ = (
        UniqueConstraint("api_key_id", "window_key", name="uq_rate_limit"),
    )


# ──────────────────────────────────────────────
# Tier Configuration (what each tier gets)
# ──────────────────────────────────────────────

TIER_LIMITS = {
    # ─────────────────────────────────────────────────────────────────────
    # FREE ($0) — The Hook
    # Goal: Let them taste Cipher. Give enough to create the habit.
    # Ceiling: They hit token limits fast. No voice. No scanner.
    # They FEEL what they're missing because the app teases premium
    # features in the UI ("Upgrade to hear Cipher speak").
    # Conversion trigger: "I want voice" or "I need more messages"
    # ─────────────────────────────────────────────────────────────────────
    SubscriptionTier.FREE: {
        "monthly_tokens": 100_000,       # ~50 solid conversations, then wall
        "monthly_requests": 500,          # Hard limit they'll feel in week 2
        "daily_scans": 0,
        "voice_minutes": 0,              # Voice is the #1 upgrade driver
        "cascade_routing": False,         # Single model only — they feel the slowness
        "voice_personalities": False,
        "evolution_scanner": False,
        "emotion_detection": False,
        "voice_cloning": False,
        "education_voices": False,
        "priority_models": False,         # No access to strongest models
        "custom_system_prompts": True,    # Let them customize — builds investment
        "conversation_export": False,     # Can't export — lock-in
        "max_api_keys": 1,
        "max_conversations": 50,          # Archive older ones
        "price_monthly_usd": 0,
        "upgrade_hook": "Unlock Cipher's voice, faster models, and unlimited conversations",
    },

    # ─────────────────────────────────────────────────────────────────────
    # PRO ($29/mo) — The Magic
    # Goal: This is where they fall in love. Voice + scanner + speed.
    # Ceiling: Voice minutes are tight (60 min). Scanner is daily-only.
    # 3 personalities only. They discover education voices exist but
    # can't use them. They want more voice time, more scans.
    # Conversion trigger: "I need more voice" or "I want the education
    # platform" or "Can I get real-time scans?"
    # ─────────────────────────────────────────────────────────────────────
    SubscriptionTier.PRO: {
        "monthly_tokens": 2_000_000,      # 10x free — generous but not unlimited
        "monthly_requests": 10_000,
        "daily_scans": 1,                 # Once per day — they'll want more
        "voice_minutes": 60,              # 1 hour/month — they'll burn through this
        "cascade_routing": True,           # FrugalGPT — they feel the speed jump
        "voice_personalities": 3,          # Cipher Core + Motivator + Anchor ONLY
        "evolution_scanner": True,         # Daily scans, but no real-time
        "emotion_detection": True,         # They experience the magic
        "voice_cloning": False,            # Teased: "Clone your voice on Business"
        "education_voices": False,         # Teased: "Education platform on Business"
        "priority_models": True,           # Access to Claude/GPT-4 class
        "custom_system_prompts": True,
        "conversation_export": True,
        "max_api_keys": 2,
        "max_conversations": 500,
        "price_monthly_usd": 29,
        "upgrade_hook": "Unlock all 8 voice personalities, education voices, and 5x more voice time",
    },

    # ─────────────────────────────────────────────────────────────────────
    # BUSINESS ($79/mo) — The Builder
    # Goal: They're building on Cipher now. Education platform. Team use.
    # Full voice stack. All personalities. This is where creators and
    # educators live.
    # Ceiling: No voice cloning. No white-label. No dedicated instances.
    # Scanner is 3x/day not real-time. Voice is 5 hours not unlimited.
    # Conversion trigger: "I want to clone voices" or "I need this for
    # my company" or "Can I white-label this?"
    # ─────────────────────────────────────────────────────────────────────
    SubscriptionTier.BUSINESS: {
        "monthly_tokens": 10_000_000,     # 5x Pro — serious usage
        "monthly_requests": 50_000,
        "daily_scans": 3,                 # 3x/day — morning, noon, evening
        "voice_minutes": 300,             # 5 hours/month — real usage
        "cascade_routing": True,
        "voice_personalities": 8,          # ALL 8 personalities unlocked
        "evolution_scanner": True,
        "emotion_detection": True,
        "voice_cloning": False,            # Still teased: "Enterprise for cloning"
        "education_voices": True,          # FULL education voice stack (10 voices)
        "priority_models": True,
        "custom_system_prompts": True,
        "conversation_export": True,
        "weekly_briefings": True,          # Markdown + JSON weekly recaps
        "api_webhooks": True,              # Webhook notifications for scans
        "max_api_keys": 10,
        "max_conversations": -1,           # Unlimited
        "price_monthly_usd": 79,
        "upgrade_hook": "Clone your own voice, unlimited everything, SLA guarantees, white-label",
    },

    # ─────────────────────────────────────────────────────────────────────
    # ENTERPRISE ($199/mo) — The Empire
    # Goal: They can't operate without Cipher. Their business runs on it.
    # Voice cloning. Unlimited everything. White-label. SLA.
    # This is the "my company IS Cipher" tier.
    # No ceiling — this is the top. Upsell is annual contracts and
    # custom enterprise deals ($499+/mo with dedicated infra).
    # ─────────────────────────────────────────────────────────────────────
    SubscriptionTier.ENTERPRISE: {
        "monthly_tokens": 50_000_000,     # Effectively unlimited for most
        "monthly_requests": 500_000,
        "daily_scans": 10,                # Near real-time monitoring
        "voice_minutes": 1200,            # 20 hours/month
        "cascade_routing": True,
        "voice_personalities": -1,         # Unlimited + custom personalities
        "evolution_scanner": True,
        "emotion_detection": True,
        "voice_cloning": True,             # THE key unlock — create your own voices
        "education_voices": True,
        "priority_models": True,
        "custom_system_prompts": True,
        "conversation_export": True,
        "weekly_briefings": True,
        "api_webhooks": True,
        "white_label": True,               # Remove Elysian branding
        "dedicated_support": True,
        "sla_guarantee": True,             # 99.9% uptime
        "custom_voice_design": True,       # Design entirely new voices
        "max_api_keys": 50,
        "max_conversations": -1,
        "price_monthly_usd": 199,
        "upgrade_hook": None,              # Top tier — upsell is annual/custom
    },
}
