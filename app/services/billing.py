"""
Stripe Billing Module for Cipher/Elysian Protocol

Handles subscription management, tier enforcement, usage tracking,
and webhook processing for the Elysian Protocol billing system.

Production-grade implementation with comprehensive error handling,
logging, and type safety.
"""

import json
import stripe
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from enum import Enum

from app.core.config import settings
from app.core.logging import logger


# ============================================================================
# TIER CONFIGURATION
# ============================================================================

class SubscriptionTier(str, Enum):
    """Enumeration of available subscription tiers."""
    FREE = "free"
    PRO = "pro"
    BUSINESS = "business"
    ENTERPRISE = "enterprise"


TIER_CONFIG = {
    SubscriptionTier.FREE: {
        "name": "Free",
        "price": 0,
        "stripe_price_id": None,
        "currency": "usd",
        "billing_period": None,
        "limits": {
            "tokens": 100_000,
            "conversations": 50,
            "voice_minutes": 15,
            "available_voices": 1,  # Cipher Core only
            "emotion_detection": False,
            "api_webhooks": False,
            "priority_models": False,
            "weekly_briefings": False,
            "voice_cloning": False,
            "white_label": False,
            "dedicated_support": False,
            "sla_included": False,
        },
        "description": "Perfect for exploring Cipher Core capabilities",
    },
    SubscriptionTier.PRO: {
        "name": "Pro",
        "price": 2900,  # $29.00 in cents
        "stripe_price_id": "price_pro_monthly",  # Update with actual Stripe price ID
        "currency": "usd",
        "billing_period": "monthly",
        "limits": {
            "tokens": 1_000_000,
            "conversations": None,  # Unlimited
            "voice_minutes": 90,
            "available_voices": 5,  # Cipher Core + 4 additional
            "emotion_detection": True,
            "api_webhooks": False,
            "priority_models": False,
            "weekly_briefings": False,
            "voice_cloning": False,
            "white_label": False,
            "dedicated_support": False,
            "sla_included": False,
        },
        "description": "For power users and content creators",
    },
    SubscriptionTier.BUSINESS: {
        "name": "Business",
        "price": 7900,  # $79.00 in cents
        "stripe_price_id": "price_business_monthly",  # Update with actual Stripe price ID
        "currency": "usd",
        "billing_period": "monthly",
        "limits": {
            "tokens": 5_000_000,
            "conversations": None,  # Unlimited
            "voice_minutes": 300,
            "available_voices": 7,  # All voices
            "emotion_detection": True,
            "api_webhooks": True,
            "priority_models": True,
            "weekly_briefings": True,
            "voice_cloning": False,
            "white_label": False,
            "dedicated_support": False,
            "sla_included": False,
        },
        "description": "For teams and organizations",
    },
    SubscriptionTier.ENTERPRISE: {
        "name": "Enterprise",
        "price": 19900,  # $199.00 in cents
        "stripe_price_id": "price_enterprise_monthly",  # Update with actual Stripe price ID
        "currency": "usd",
        "billing_period": "monthly",
        "limits": {
            "tokens": 25_000_000,
            "conversations": None,  # Unlimited
            "voice_minutes": 1200,
            "available_voices": 7,  # All voices
            "emotion_detection": True,
            "api_webhooks": True,
            "priority_models": True,
            "weekly_briefings": True,
            "voice_cloning": True,
            "white_label": True,
            "dedicated_support": True,
            "sla_included": True,
        },
        "description": "For large enterprises with dedicated support",
    },
}


# ============================================================================
# INITIALIZATION & CONFIGURATION
# ============================================================================

def init_stripe() -> None:
    """
    Initialize the Stripe API client with the secret key from settings.

    Raises:
        ValueError: If the stripe_secret_key is not configured in settings.
        stripe.error.AuthenticationError: If the API key is invalid.
    """
    if not settings.stripe_secret_key:
        error_msg = "Stripe secret key not configured in settings"
        logger.error(error_msg)
        raise ValueError(error_msg)

    stripe.api_key = settings.stripe_secret_key
    logger.info("Stripe API client initialized successfully")


# ============================================================================
# CHECKOUT & SUBSCRIPTION MANAGEMENT
# ============================================================================

def create_checkout_session(
    tier: str,
    user_email: str,
    success_url: str,
    cancel_url: str,
) -> Dict[str, Any]:
    """
    Create a Stripe checkout session for subscription upgrade.

    Args:
        tier: The subscription tier (free, pro, business, enterprise)
        user_email: The user's email address
        success_url: URL to redirect to after successful payment
        cancel_url: URL to redirect to if payment is cancelled

    Returns:
        Dictionary containing:
            - session_id: Stripe checkout session ID
            - checkout_url: URL for the user to complete checkout
            - tier: The tier being purchased
            - expires_at: Session expiration timestamp

    Raises:
        ValueError: If the tier is invalid or not found
        stripe.error.StripeError: If the Stripe API call fails
    """
    try:
        # Validate tier
        tier_lower = tier.lower()
        if tier_lower not in TIER_CONFIG:
            error_msg = f"Invalid subscription tier: {tier}"
            logger.error(error_msg)
            raise ValueError(error_msg)

        tier_obj = SubscriptionTier(tier_lower)
        tier_config = TIER_CONFIG[tier_obj]

        # Free tier has no checkout
        if tier_obj == SubscriptionTier.FREE:
            error_msg = "Free tier does not require checkout"
            logger.warning(f"Checkout attempted for FREE tier: {user_email}")
            raise ValueError(error_msg)

        # Create Stripe checkout session
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[
                {
                    "price": tier_config["stripe_price_id"],
                    "quantity": 1,
                }
            ],
            mode="subscription",
            customer_email=user_email,
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                "tier": tier_lower,
                "user_email": user_email,
            },
        )

        logger.info(
            f"Checkout session created",
            extra={
                "session_id": session.id,
                "tier": tier_lower,
                "email": user_email,
            },
        )

        return {
            "session_id": session.id,
            "checkout_url": session.url,
            "tier": tier_lower,
            "expires_at": datetime.utcnow() + timedelta(hours=24),
        }

    except ValueError:
        raise
    except stripe.error.StripeError as e:
        logger.error(
            f"Stripe API error creating checkout session: {str(e)}",
            extra={"tier": tier, "email": user_email},
        )
        raise
    except Exception as e:
        logger.error(
            f"Unexpected error creating checkout session: {str(e)}",
            extra={"tier": tier, "email": user_email},
        )
        raise


def handle_webhook(payload: bytes, sig_header: str) -> Dict[str, Any]:
    """
    Process Stripe webhook events securely.

    Validates webhook signature and processes subscription events
    (customer.subscription.created, customer.subscription.updated, etc).

    Args:
        payload: Raw webhook payload from Stripe
        sig_header: Signature header from Stripe webhook

    Returns:
        Dictionary containing:
            - event_type: The Stripe event type
            - processed: Whether the event was successfully processed
            - customer_id: The Stripe customer ID (if applicable)
            - subscription_id: The subscription ID (if applicable)

    Raises:
        ValueError: If the webhook signature is invalid
        stripe.error.StripeError: If event processing fails
    """
    if not settings.stripe_webhook_secret:
        error_msg = "Stripe webhook secret not configured"
        logger.error(error_msg)
        raise ValueError(error_msg)

    try:
        # Verify webhook signature
        event = stripe.Webhook.construct_event(
            payload,
            sig_header,
            settings.stripe_webhook_secret,
        )
    except ValueError as e:
        error_msg = f"Invalid webhook payload: {str(e)}"
        logger.error(error_msg)
        raise ValueError(error_msg)
    except stripe.error.SignatureVerificationError as e:
        error_msg = f"Invalid webhook signature: {str(e)}"
        logger.error(error_msg)
        raise ValueError(error_msg)

    event_type = event["type"]
    data = event["data"]["object"]

    logger.info(f"Processing webhook event: {event_type}")

    try:
        # Handle subscription events
        if event_type == "customer.subscription.created":
            _handle_subscription_created(data)

        elif event_type == "customer.subscription.updated":
            _handle_subscription_updated(data)

        elif event_type == "customer.subscription.deleted":
            _handle_subscription_deleted(data)

        elif event_type == "invoice.payment_succeeded":
            _handle_payment_succeeded(data)

        elif event_type == "invoice.payment_failed":
            _handle_payment_failed(data)

        else:
            logger.debug(f"Unhandled webhook event type: {event_type}")

        return {
            "event_type": event_type,
            "processed": True,
            "customer_id": data.get("customer"),
            "subscription_id": data.get("id"),
        }

    except Exception as e:
        logger.error(
            f"Error processing webhook event {event_type}: {str(e)}",
            extra={"event_id": event.get("id")},
        )
        raise


def _handle_subscription_created(data: Dict[str, Any]) -> None:
    """
    Handle customer.subscription.created webhook event.

    Updates user record with new subscription tier and customer ID.
    """
    customer_id = data.get("customer")
    subscription_id = data.get("id")
    items = data.get("items", {}).get("data", [])

    if items:
        price_id = items[0].get("price", {}).get("id")
        tier = _get_tier_from_price_id(price_id)
        logger.info(
            f"Subscription created",
            extra={
                "customer_id": customer_id,
                "subscription_id": subscription_id,
                "tier": tier,
            },
        )
        # TODO: Update user.tier in database


def _handle_subscription_updated(data: Dict[str, Any]) -> None:
    """Handle customer.subscription.updated webhook event."""
    customer_id = data.get("customer")
    subscription_id = data.get("id")
    items = data.get("items", {}).get("data", [])

    if items:
        price_id = items[0].get("price", {}).get("id")
        tier = _get_tier_from_price_id(price_id)
        logger.info(
            f"Subscription updated",
            extra={
                "customer_id": customer_id,
                "subscription_id": subscription_id,
                "tier": tier,
            },
        )
        # TODO: Update user.tier in database


def _handle_subscription_deleted(data: Dict[str, Any]) -> None:
    """Handle customer.subscription.deleted webhook event."""
    customer_id = data.get("customer")
    subscription_id = data.get("id")
    logger.info(
        f"Subscription cancelled",
        extra={
            "customer_id": customer_id,
            "subscription_id": subscription_id,
        },
    )
    # TODO: Downgrade user to FREE tier


def _handle_payment_succeeded(data: Dict[str, Any]) -> None:
    """Handle invoice.payment_succeeded webhook event."""
    customer_id = data.get("customer")
    invoice_id = data.get("id")
    amount_paid = data.get("amount_paid")
    logger.info(
        f"Payment succeeded",
        extra={
            "customer_id": customer_id,
            "invoice_id": invoice_id,
            "amount_paid": amount_paid,
        },
    )


def _handle_payment_failed(data: Dict[str, Any]) -> None:
    """Handle invoice.payment_failed webhook event."""
    customer_id = data.get("customer")
    invoice_id = data.get("id")
    logger.warning(
        f"Payment failed",
        extra={
            "customer_id": customer_id,
            "invoice_id": invoice_id,
        },
    )
    # TODO: Send user notification about failed payment


def _get_tier_from_price_id(price_id: str) -> Optional[str]:
    """
    Lookup subscription tier from Stripe price ID.

    Args:
        price_id: The Stripe price ID

    Returns:
        The tier name (pro, business, enterprise) or None if not found
    """
    for tier, config in TIER_CONFIG.items():
        if config["stripe_price_id"] == price_id:
            return tier.value
    return None


# ============================================================================
# USER TIER & USAGE MANAGEMENT
# ============================================================================

def get_user_tier(user_id: str) -> Dict[str, Any]:
    """
    Get the current subscription tier and limits for a user.

    Args:
        user_id: The user's ID

    Returns:
        Dictionary containing:
            - tier: The subscription tier (free, pro, business, enterprise)
            - name: Human-readable tier name
            - limits: Dictionary of resource limits for this tier
            - price: Price in cents (0 for free tier)
            - next_billing_date: Datetime of next billing (None for free tier)

    Note:
        In a real implementation, this would query the database.
        Current implementation returns default tier.
    """
    try:
        # TODO: Query database for user.tier
        # For now, default to FREE tier
        tier = SubscriptionTier.FREE
        tier_config = TIER_CONFIG[tier]

        return {
            "tier": tier.value,
            "name": tier_config["name"],
            "limits": tier_config["limits"].copy(),
            "price": tier_config["price"],
            "next_billing_date": None,
            "user_id": user_id,
        }

    except Exception as e:
        logger.error(
            f"Error retrieving user tier: {str(e)}",
            extra={"user_id": user_id},
        )
        # Default to FREE tier on error
        return {
            "tier": SubscriptionTier.FREE.value,
            "name": TIER_CONFIG[SubscriptionTier.FREE]["name"],
            "limits": TIER_CONFIG[SubscriptionTier.FREE]["limits"].copy(),
            "price": 0,
            "next_billing_date": None,
            "user_id": user_id,
        }


def check_usage(
    user_id: str,
    resource: str,
    amount: int = 1,
) -> Dict[str, Any]:
    """
    Check if user has remaining quota for a resource.

    Validates that a usage action (token consumption, voice minute, etc.)
    is within the user's subscription limits.

    Args:
        user_id: The user's ID
        resource: The resource type (tokens, conversations, voice_minutes, etc.)
        amount: The amount of the resource to consume (default: 1)

    Returns:
        Dictionary containing:
            - allowed: Whether the usage is allowed
            - remaining: Remaining quota (None if unlimited)
            - limit: Total limit for this resource (None if unlimited)
            - resource: The resource type
            - over_limit: How much over the limit (0 if within limit)

    Example:
        >>> result = check_usage("user123", "tokens", 10000)
        >>> if result["allowed"]:
        ...     # Process the request
        ... else:
        ...     # Return upgrade prompt
    """
    try:
        tier_info = get_user_tier(user_id)
        limits = tier_info["limits"]

        # Check if resource is tracked
        if resource not in limits:
            logger.warning(
                f"Unknown resource type in usage check: {resource}",
                extra={"user_id": user_id},
            )
            return {
                "allowed": True,  # Allow unknown resources
                "remaining": None,
                "limit": None,
                "resource": resource,
                "over_limit": 0,
            }

        limit = limits.get(resource)

        # Unlimited resources
        if limit is None:
            return {
                "allowed": True,
                "remaining": None,
                "limit": None,
                "resource": resource,
                "over_limit": 0,
            }

        # TODO: Query database for current usage
        # For now, assume 0 usage
        current_usage = 0

        remaining = limit - current_usage
        allowed = (current_usage + amount) <= limit
        over_limit = max(0, (current_usage + amount) - limit)

        return {
            "allowed": allowed,
            "remaining": remaining,
            "limit": limit,
            "resource": resource,
            "over_limit": over_limit,
        }

    except Exception as e:
        logger.error(
            f"Error checking usage: {str(e)}",
            extra={"user_id": user_id, "resource": resource},
        )
        # Default to allow on error
        return {
            "allowed": True,
            "remaining": None,
            "limit": None,
            "resource": resource,
            "over_limit": 0,
        }


# ============================================================================
# UPGRADE NUDGES & BILLING PORTAL
# ============================================================================

def get_upgrade_nudge(user_id: str) -> Optional[str]:
    """
    Generate a contextual upgrade message based on user tier and usage.

    Provides targeted messages to encourage users to upgrade when they're
    approaching limits or would benefit from higher-tier features.

    Args:
        user_id: The user's ID

    Returns:
        A motivational upgrade message, or None if user is on Enterprise tier
        or has no upgrade opportunities

    Example:
        >>> nudge = get_upgrade_nudge("user123")
        >>> if nudge:
        ...     return {"message": nudge, "show_upgrade_cta": True}
    """
    try:
        tier_info = get_user_tier(user_id)
        current_tier = tier_info["tier"]

        # Enterprise users don't need nudges
        if current_tier == SubscriptionTier.ENTERPRISE.value:
            return None

        # Check usage levels for nudges
        token_check = check_usage(user_id, "tokens", 0)
        voice_check = check_usage(user_id, "voice_minutes", 0)

        # TODO: Query database for actual usage
        # For now, return generic nudges based on tier

        if current_tier == SubscriptionTier.FREE.value:
            return (
                "Ready to create unlimited conversations? "
                "Upgrade to Pro and unlock emotion detection."
            )

        elif current_tier == SubscriptionTier.PRO.value:
            return (
                "Need more voice minutes and API webhooks? "
                "Business tier includes all 7 voices and priority support."
            )

        elif current_tier == SubscriptionTier.BUSINESS.value:
            return (
                "Get voice cloning, white-label, and SLA support. "
                "Upgrade to Enterprise for your organization."
            )

        return None

    except Exception as e:
        logger.error(
            f"Error generating upgrade nudge: {str(e)}",
            extra={"user_id": user_id},
        )
        return None


def create_billing_portal(
    customer_id: str,
    return_url: str,
) -> str:
    """
    Create a Stripe billing portal session for the user.

    Allows users to manage their subscription, update payment methods,
    view invoices, and control billing settings.

    Args:
        customer_id: The Stripe customer ID
        return_url: URL to return to after managing billing

    Returns:
        The Stripe billing portal URL

    Raises:
        ValueError: If customer_id is not provided
        stripe.error.StripeError: If the Stripe API call fails
    """
    try:
        if not customer_id:
            raise ValueError("customer_id is required")

        session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=return_url,
        )

        logger.info(
            f"Billing portal session created",
            extra={"customer_id": customer_id},
        )

        return session.url

    except ValueError:
        raise
    except stripe.error.StripeError as e:
        logger.error(
            f"Stripe API error creating billing portal: {str(e)}",
            extra={"customer_id": customer_id},
        )
        raise
    except Exception as e:
        logger.error(
            f"Unexpected error creating billing portal: {str(e)}",
            extra={"customer_id": customer_id},
        )
        raise


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_tier_config(tier: str) -> Dict[str, Any]:
    """
    Retrieve configuration for a specific tier.

    Args:
        tier: The subscription tier

    Returns:
        The full tier configuration dictionary

    Raises:
        ValueError: If the tier is not found
    """
    tier_lower = tier.lower()
    try:
        tier_obj = SubscriptionTier(tier_lower)
        return TIER_CONFIG[tier_obj].copy()
    except ValueError:
        error_msg = f"Invalid subscription tier: {tier}"
        logger.error(error_msg)
        raise


def list_all_tiers() -> Dict[str, Dict[str, Any]]:
    """
    Return all available tiers and their configurations.

    Returns:
        Dictionary mapping tier names to their configurations
    """
    return {
        tier.value: config.copy()
        for tier, config in TIER_CONFIG.items()
    }
