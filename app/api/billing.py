"""
Billing API endpoints for the Cipher project.

Handles subscription management, checkout, webhooks, usage tracking,
and billing portal access through Stripe integration.
"""

from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field, EmailStr

from app.core.logging import logger
from app.core.config import settings
from app.services import billing
from app.db.models import User
from app.api.auth import get_current_user


router = APIRouter(prefix="/billing", tags=["billing"])


# ============================================================================
# Pydantic Models
# ============================================================================


class CheckoutRequest(BaseModel):
    """Request body for creating a checkout session."""

    tier: str = Field(..., description="Subscription tier (pro, business, enterprise)")
    success_url: str = Field(..., description="URL to redirect to after successful payment")
    cancel_url: str = Field(..., description="URL to redirect to if payment is cancelled")


class CheckoutResponse(BaseModel):
    """Response with checkout session details."""

    session_id: str
    checkout_url: str
    tier: str
    expires_at: str


class UsageResponse(BaseModel):
    """Response with user's resource usage statistics."""

    user_id: int
    tier: str
    tier_name: str
    limits: Dict[str, Any]
    current_usage: Dict[str, int] = {}
    upgrade_nudge: Optional[str] = None


class TierResponse(BaseModel):
    """Response with subscription tier details."""

    name: str
    price: int  # in cents
    currency: str
    billing_period: Optional[str]
    description: str
    limits: Dict[str, Any]
    features: list = []


class TiersResponse(BaseModel):
    """Response with all available subscription tiers."""

    tiers: Dict[str, TierResponse]
    free_tier_id: str = "free"


class BillingPortalResponse(BaseModel):
    """Response with billing portal session URL."""

    portal_url: str
    customer_id: str


class WebhookResponse(BaseModel):
    """Response confirming webhook processing."""

    event_type: str
    processed: bool
    customer_id: Optional[str] = None
    subscription_id: Optional[str] = None


# ============================================================================
# Endpoints
# ============================================================================


@router.post(
    "/checkout",
    response_model=CheckoutResponse,
    status_code=status.HTTP_200_OK,
)
async def create_checkout(
    request: CheckoutRequest,
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Create a Stripe checkout session for subscription upgrade.

    Requires authentication. User email is automatically used for checkout.

    - **tier**: The subscription tier (pro, business, enterprise)
    - **success_url**: URL to redirect to after successful payment
    - **cancel_url**: URL to redirect to if payment is cancelled

    Returns checkout session details including Stripe checkout URL.
    """
    try:
        logger.info(
            f"Creating checkout session",
            extra={
                "user_id": current_user.id,
                "tier": request.tier,
                "email": current_user.email,
            },
        )

        checkout_data = billing.create_checkout_session(
            tier=request.tier,
            user_email=current_user.email,
            success_url=request.success_url,
            cancel_url=request.cancel_url,
        )

        return {
            "session_id": checkout_data["session_id"],
            "checkout_url": checkout_data["checkout_url"],
            "tier": checkout_data["tier"],
            "expires_at": checkout_data["expires_at"].isoformat(),
        }

    except ValueError as e:
        logger.warning(f"Invalid checkout request: {str(e)}", extra={"user_id": current_user.id})
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(
            f"Error creating checkout session: {str(e)}",
            extra={"user_id": current_user.id},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create checkout session",
        )


@router.post(
    "/webhook",
    response_model=WebhookResponse,
    status_code=status.HTTP_200_OK,
)
async def handle_webhook(request: Request) -> dict:
    """
    Receive and process Stripe webhook events.

    This endpoint is called by Stripe directly. No authentication required.

    Handles subscription events:
    - customer.subscription.created
    - customer.subscription.updated
    - customer.subscription.deleted
    - invoice.payment_succeeded
    - invoice.payment_failed

    Stripe signature verification is performed automatically.
    """
    try:
        # Get raw body for signature verification
        payload = await request.body()
        sig_header = request.headers.get("stripe-signature")

        if not sig_header:
            logger.warning("Webhook received without stripe-signature header")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing stripe-signature header",
            )

        logger.info("Processing Stripe webhook")

        result = billing.handle_webhook(payload, sig_header)

        return {
            "event_type": result["event_type"],
            "processed": result["processed"],
            "customer_id": result.get("customer_id"),
            "subscription_id": result.get("subscription_id"),
        }

    except ValueError as e:
        logger.warning(f"Invalid webhook: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process webhook",
        )


@router.get(
    "/usage",
    response_model=UsageResponse,
    status_code=status.HTTP_200_OK,
)
async def get_usage(
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Get current user's usage statistics and tier information.

    Requires authentication.

    Returns:
    - User's current subscription tier
    - Tier limits for various resources
    - Current usage (if available)
    - Contextual upgrade message if applicable
    """
    try:
        logger.info(f"Retrieving usage for user", extra={"user_id": current_user.id})

        tier_info = billing.get_user_tier(str(current_user.id))
        upgrade_nudge = billing.get_upgrade_nudge(str(current_user.id))

        # Populate actual usage from database
        current_usage = {}
        for resource in ["tokens", "conversations", "voice_minutes"]:
            usage_check = billing.check_usage(str(current_user.id), resource, 0)
            if usage_check.get("limit") is not None:
                current_usage[resource] = {
                    "used": usage_check["limit"] - (usage_check.get("remaining") or 0),
                    "limit": usage_check["limit"],
                    "remaining": usage_check.get("remaining"),
                }

        return {
            "user_id": current_user.id,
            "tier": tier_info["tier"],
            "tier_name": tier_info["name"],
            "limits": tier_info["limits"],
            "current_usage": current_usage,
            "upgrade_nudge": upgrade_nudge,
        }

    except Exception as e:
        logger.error(
            f"Error retrieving usage: {str(e)}",
            extra={"user_id": current_user.id},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve usage information",
        )


@router.get(
    "/tiers",
    response_model=TiersResponse,
    status_code=status.HTTP_200_OK,
)
async def get_tiers() -> dict:
    """
    Get all available subscription tiers with features and pricing.

    Public endpoint (no authentication required).

    Returns detailed information about each tier:
    - Pricing and billing period
    - Resource limits
    - Feature availability
    """
    try:
        logger.info("Retrieving tier information")

        all_tiers = billing.list_all_tiers()
        tiers_response = {}

        for tier_key, tier_config in all_tiers.items():
            tiers_response[tier_key] = {
                "name": tier_config["name"],
                "price": tier_config["price"],
                "currency": tier_config.get("currency", "usd"),
                "billing_period": tier_config.get("billing_period"),
                "description": tier_config.get("description", ""),
                "limits": tier_config.get("limits", {}),
                "features": [
                    k for k, v in tier_config.get("limits", {}).items()
                    if v is True
                ],
            }

        return {
            "tiers": tiers_response,
            "free_tier_id": "free",
        }

    except Exception as e:
        logger.error(f"Error retrieving tiers: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve tier information",
        )


@router.post(
    "/portal",
    response_model=BillingPortalResponse,
    status_code=status.HTTP_200_OK,
)
async def create_portal(
    return_url: str = Query(..., description="URL to return to after managing billing"),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Create a Stripe billing portal session for the user.

    Requires authentication. Allows users to:
    - Manage their subscription
    - Update payment methods
    - View invoices
    - Control billing settings

    - **return_url**: URL to return to after managing billing

    Returns the billing portal URL.
    """
    try:
        logger.info(
            f"Creating billing portal session",
            extra={"user_id": current_user.id},
        )

        # TODO: Get customer_id from database user record
        # For now, use a placeholder that should be populated
        customer_id = getattr(current_user, "stripe_customer_id", None)

        if not customer_id:
            logger.warning(
                f"User has no Stripe customer ID",
                extra={"user_id": current_user.id},
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User has not yet created a subscription",
            )

        portal_url = billing.create_billing_portal(
            customer_id=customer_id,
            return_url=return_url,
        )

        return {
            "portal_url": portal_url,
            "customer_id": customer_id,
        }

    except ValueError as e:
        logger.warning(f"Invalid portal request: {str(e)}", extra={"user_id": current_user.id})
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(
            f"Error creating billing portal: {str(e)}",
            extra={"user_id": current_user.id},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create billing portal session",
        )
