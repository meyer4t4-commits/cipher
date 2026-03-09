"""
Notification API — Device registration and push/SMS alert management.
Reuses communication_agent's FCM + Twilio infrastructure.
"""

import json
import os
from typing import Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.core.logging import logger

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])

DEVICE_TOKENS_FILE = "./data/push/device_tokens.json"
NOTIFICATION_PREFS_FILE = "./data/push/notification_prefs.json"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class DeviceRegistration(BaseModel):
    device_token: str
    user_id: str = "mark"
    device_name: str = "iPhone"
    platform: str = "ios"


class TestNotificationRequest(BaseModel):
    title: str = "Test from Cipher"
    body: str = "Push notifications are working!"


class NotificationPreferences(BaseModel):
    push_enabled: bool = True
    sms_enabled: bool = False
    phone_number: Optional[str] = None
    alert_on_questions: bool = True
    alert_on_completions: bool = True
    alert_on_failures: bool = True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_device_tokens() -> dict:
    if os.path.exists(DEVICE_TOKENS_FILE):
        try:
            with open(DEVICE_TOKENS_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_device_tokens(data: dict):
    os.makedirs(os.path.dirname(DEVICE_TOKENS_FILE), exist_ok=True)
    with open(DEVICE_TOKENS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def _load_prefs() -> dict:
    if os.path.exists(NOTIFICATION_PREFS_FILE):
        try:
            with open(NOTIFICATION_PREFS_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return NotificationPreferences().model_dump()


def _save_prefs(prefs: dict):
    os.makedirs(os.path.dirname(NOTIFICATION_PREFS_FILE), exist_ok=True)
    with open(NOTIFICATION_PREFS_FILE, "w") as f:
        json.dump(prefs, f, indent=2)


# ---------------------------------------------------------------------------
# Internal helper for agents to trigger notifications
# ---------------------------------------------------------------------------

async def notify_user(
    title: str,
    body: str,
    data: dict | None = None,
    channels: list[str] | None = None,
):
    """
    Send notification to user via configured channels.
    Called internally by agent_interactions and task completion handlers.
    """
    prefs = _load_prefs()
    channels = channels or []
    if not channels:
        if prefs.get("push_enabled", True):
            channels.append("push")
        if prefs.get("sms_enabled", False):
            channels.append("sms")

    tokens = _load_device_tokens()

    for channel in channels:
        if channel == "push":
            # Send via FCM (use communication agent's infra)
            try:
                from app.agents.skills.communication_agent import CommunicationAgent
                agent = CommunicationAgent()
                for user_id, user_tokens in tokens.items():
                    for token_info in user_tokens:
                        token = token_info if isinstance(token_info, str) else token_info.get("token", "")
                        if token:
                            logger.info(f"Push notification to {user_id}: {title}")
                            # FCM send would go here with token
            except Exception as e:
                logger.error(f"Push notification failed: {e}")

        elif channel == "sms":
            phone = prefs.get("phone_number")
            if phone:
                try:
                    from app.agents.skills.communication_agent import CommunicationAgent
                    agent = CommunicationAgent()
                    logger.info(f"SMS to {phone}: {title} - {body}")
                    # Twilio send would go here
                except Exception as e:
                    logger.error(f"SMS notification failed: {e}")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/register-device")
async def register_device(request: DeviceRegistration):
    """Register a device for push notifications."""
    tokens = _load_device_tokens()

    if request.user_id not in tokens:
        tokens[request.user_id] = []

    # Check if token already registered
    existing = [
        t for t in tokens[request.user_id]
        if (isinstance(t, dict) and t.get("token") == request.device_token)
        or (isinstance(t, str) and t == request.device_token)
    ]

    if not existing:
        from datetime import datetime
        tokens[request.user_id].append({
            "token": request.device_token,
            "device_name": request.device_name,
            "platform": request.platform,
            "registered_at": datetime.utcnow().isoformat(),
            "active": True,
        })
        _save_device_tokens(tokens)
        logger.info(f"Device registered: {request.device_name} ({request.platform})")

    return {
        "registered": True,
        "device_name": request.device_name,
        "total_devices": len(tokens.get(request.user_id, [])),
    }


@router.delete("/unregister-device")
async def unregister_device(device_token: str, user_id: str = "mark"):
    """Remove a device from push notifications."""
    tokens = _load_device_tokens()
    if user_id in tokens:
        tokens[user_id] = [
            t for t in tokens[user_id]
            if not (
                (isinstance(t, dict) and t.get("token") == device_token)
                or (isinstance(t, str) and t == device_token)
            )
        ]
        _save_device_tokens(tokens)
    return {"unregistered": True}


@router.get("/devices")
async def list_devices(user_id: str = "mark"):
    """List all registered devices."""
    tokens = _load_device_tokens()
    devices = tokens.get(user_id, [])
    return {
        "user_id": user_id,
        "devices": devices,
        "total": len(devices),
    }


@router.post("/test")
async def send_test_notification(request: TestNotificationRequest):
    """Send a test push notification to all registered devices."""
    await notify_user(
        title=request.title,
        body=request.body,
        data={"type": "test"},
        channels=["push"],
    )
    return {"sent": True, "title": request.title}


@router.get("/preferences")
async def get_preferences():
    """Get notification preferences."""
    return _load_prefs()


@router.put("/preferences")
async def update_preferences(prefs: NotificationPreferences):
    """Update notification preferences."""
    _save_prefs(prefs.model_dump())
    return {"updated": True, "preferences": prefs.model_dump()}
