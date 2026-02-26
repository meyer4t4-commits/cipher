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
    voice_minutes_limit = Column(Integer, default=15)  # Free gets 15 min of Cipher's voice

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
    # Voice IS the product. Free users get Cipher's voice from day one.
    # That's how they fall in love. The ceiling is: Cipher is the ONLY
    # voice. When they're frustrated and Cipher can't shift to rally
    # mode, when they need comfort and there's no anchor voice —
    # THAT's when they feel it. Also: limited voice minutes, no scanner,
    # slower models.
    # Conversion trigger: "I wish Cipher had a different voice for this"
    # ─────────────────────────────────────────────────────────────────────
    SubscriptionTier.FREE: {
        "monthly_tokens": 100_000,       # ~50 solid conversations, then wall
        "monthly_requests": 500,          # Hard limit they'll feel in week 2
        "daily_scans": 0,
        "voice_minutes": 15,             # Cipher's voice included — 15 min/mo
        "cipher_voice": True,            # Cipher's core voice is ALWAYS included
        "situational_voices": 0,         # No voice switching — Cipher only
        "cascade_routing": False,         # Single model only
        "evolution_scanner": False,
        "emotion_detection": False,       # Can't read the room yet
        "voice_cloning": False,
        "education_voices": 0,
        "priority_models": False,
        "custom_system_prompts": True,    # Builds investment
        "conversation_export": False,
        "voice_opt_out": True,            # Can turn off voice if they just want text
        "max_api_keys": 1,
        "max_conversations": 50,
        "price_monthly_usd": 0,
        "upgrade_hook": "Unlock situational voices — Cipher adapts HOW it speaks to what you need",
    },

    # ─────────────────────────────────────────────────────────────────────
    # PRO ($29/mo) — The Shift
    # Now Cipher adapts. When they're down, Anchor mode kicks in.
    # When they need fire, Motivator shows up. When they need to
    # think, Philosopher arrives. This is the "holy shit it reads me"
    # moment. But: only 4 situational voices (the core emotional ones).
    # They hear about Strategist, Coach, Educator, Creative but those
    # are locked. Also emotion detection turns on — Cipher picks up
    # on vocal cues. Scanner starts. More voice time.
    # Conversion trigger: "I want the strategy voice" or "can Cipher
    # teach me things?" or "I need all the voices"
    # ─────────────────────────────────────────────────────────────────────
    SubscriptionTier.PRO: {
        "monthly_tokens": 2_000_000,
        "monthly_requests": 10_000,
        "daily_scans": 1,
        "voice_minutes": 90,             # 1.5 hours — they'll feel it
        "cipher_voice": True,
        "situational_voices": 4,          # Cipher + Motivator + Anchor + Philosopher + Creative
        "cascade_routing": True,
        "evolution_scanner": True,
        "emotion_detection": True,        # Cipher reads vocal cues now
        "voice_cloning": False,
        "education_voices": 0,            # Teased: "Learn Italian with a Nonna voice"
        "priority_models": True,
        "custom_system_prompts": True,
        "conversation_export": True,
        "voice_opt_out": True,
        "max_api_keys": 2,
        "max_conversations": 500,
        "price_monthly_usd": 29,
        "upgrade_hook": "All 7 situational voices, education voices, and 5 hours of voice time",
    },

    # ─────────────────────────────────────────────────────────────────────
    # BUSINESS ($79/mo) — The Full Voice
    # Every voice unlocked. Every situation covered. Plus the education
    # voice stack — Nonna for Italian, Alan Watts for philosophy,
    # Einstein for science, Blues master for harmonica. This is where
    # creators, educators, and power users live.
    # Education platform voices are the big draw here. Someone who
    # wants to learn Italian with a warm Nonna character, or physics
    # with an Einstein-like voice, or guitar — they need this tier.
    # Ceiling: No voice cloning. No white-label.
    # Conversion trigger: "I want to clone my voice" or "white-label"
    # ─────────────────────────────────────────────────────────────────────
    SubscriptionTier.BUSINESS: {
        "monthly_tokens": 10_000_000,
        "monthly_requests": 50_000,
        "daily_scans": 3,
        "voice_minutes": 300,             # 5 hours/month
        "cipher_voice": True,
        "situational_voices": -1,          # ALL 7 situational voices
        "cascade_routing": True,
        "evolution_scanner": True,
        "emotion_detection": True,
        "voice_cloning": False,
        "education_voices": -1,            # ALL education voices (ever-growing catalog)
        "priority_models": True,
        "custom_system_prompts": True,
        "conversation_export": True,
        "voice_opt_out": True,
        "weekly_briefings": True,
        "api_webhooks": True,
        "max_api_keys": 10,
        "max_conversations": -1,
        "price_monthly_usd": 79,
        "upgrade_hook": "Clone your own voice, unlimited everything, white-label",
    },

    # ─────────────────────────────────────────────────────────────────────
    # ENTERPRISE ($199/mo) — The Empire
    # Voice cloning. White-label. SLA. Their operation IS Cipher.
    # They can clone their own voice for voiceovers, content, courses.
    # Design entirely new synthetic voices. Remove Elysian branding.
    # This is the "I built my business on this" tier.
    # ─────────────────────────────────────────────────────────────────────
    SubscriptionTier.ENTERPRISE: {
        "monthly_tokens": 50_000_000,
        "monthly_requests": 500_000,
        "daily_scans": 10,
        "voice_minutes": 1200,            # 20 hours/month
        "cipher_voice": True,
        "situational_voices": -1,
        "cascade_routing": True,
        "evolution_scanner": True,
        "emotion_detection": True,
        "voice_cloning": True,             # Clone your own voice
        "education_voices": -1,
        "priority_models": True,
        "custom_system_prompts": True,
        "conversation_export": True,
        "voice_opt_out": True,
        "weekly_briefings": True,
        "api_webhooks": True,
        "white_label": True,
        "dedicated_support": True,
        "sla_guarantee": True,
        "custom_voice_design": True,       # Design new synthetic voices
        "max_api_keys": 50,
        "max_conversations": -1,
        "price_monthly_usd": 199,
        "upgrade_hook": None,
    },
}
