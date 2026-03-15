"""
Sentinel Hand - Proactive Alerts Agent for Cipher AI System

Monitors email and SMS, predicts needs before the user asks, and takes preemptive action.
Generates prioritized alert digests with recommended actions.
"""

import asyncio
import json
import re
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

from app.agents.base import BaseAgent
from app.agents.models import AgentCapability, AgentResult, AgentTask
from app.core.config import settings
from app.core.logging import logger


# URGENCY SIGNALS - Patterns indicating urgent/time-sensitive communications
URGENCY_SIGNALS: List[str] = [
    r"\burgen[tc]\b",
    r"\bdeadline\b",
    r"\basap\b",
    r"\boverdue\b",
    r"\bpayment\s+due\b",
    r"\bexpires?\b",
    r"\bfinal\s+notice\b",
    r"\baction\s+required\b",
    r"\btime\s+sensitive\b",
    r"\brespond\s+by\b",
    r"\blast\s+chance\b",
    r"\bcritical\b",
    r"\bemergency\b",
    r"\bimmediately\b",
    r"\btoday\b",
    r"\btomorrow\b",
    r"\breply\s+asap\b",
    r"\bconfirm\s+receipt\b",
    r"\bpending\b",
    r"\brequires?\s+attention\b",
    r"\bverify\b",
    r"\bvalidate\b",
    r"\bupdate.*required\b",
    r"\bdue\s+today\b",
    r"\bmissed\b",
    r"\bimportant\b",
]

# CATEGORY RULES - Map categories to keyword patterns
CATEGORY_RULES: Dict[str, List[str]] = {
    "financial": ["invoice", "payment", "bank", "transfer", "receipt", "statement", "tax", "bill", "charge", "refund"],
    "scheduling": ["meeting", "appointment", "reschedule", "cancel", "calendar", "rsvp", "conference", "call", "call time", "sync"],
    "business": ["proposal", "contract", "agreement", "client", "deal", "partnership", "project", "deadline", "deliverable"],
    "personal": ["family", "doctor", "appointment", "birthday", "reminder", "health", "emergency", "contact"],
    "real_estate": ["property", "listing", "offer", "inspection", "closing", "mortgage", "appraisal", "lease", "rent"],
}

# PRIORITY WEIGHTS - Composite scoring factors
PRIORITY_WEIGHTS: Dict[str, float] = {
    "urgency": 0.4,
    "recency": 0.3,
    "sender_importance": 0.2,
    "category_weight": 0.1,
}


@dataclass
class AlertEntry:
    """Represents a single alert derived from email or SMS."""
    id: str
    source: str  # "email" or "sms"
    subject: str
    sender: str
    body_preview: str
    urgency_score: float
    category: str
    detected_deadline: Optional[datetime] = None
    recommended_action: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    status: str = "new"  # "new", "acknowledged", "resolved"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        if self.timestamp:
            data["timestamp"] = self.timestamp.isoformat()
        if self.detected_deadline:
            data["detected_deadline"] = self.detected_deadline.isoformat()
        return data

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "AlertEntry":
        """Create AlertEntry from dictionary."""
        if isinstance(data.get("timestamp"), str):
            data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        if isinstance(data.get("detected_deadline"), str):
            data["detected_deadline"] = datetime.fromisoformat(data["detected_deadline"])
        return AlertEntry(**data)


class SentinelAgent(BaseAgent):
    """
    Proactive Alerts Agent - Monitors email and SMS for time-sensitive communications,
    predicts needs before the user asks, and generates prioritized action digests.
    """

    name = "sentinel_agent"
    description = "Proactive alert system — monitors email and SMS, predicts needs, and takes preemptive action"
    version = "2.0.0"

    def __init__(self):
        """Initialize Sentinel Agent with capabilities."""
        super().__init__(
            name="sentinel",
            description="Proactive alerts — monitors email/SMS, predicts needs, generates prioritized action digests",
            version="1.0.0",
        )
        self.data_dir = Path("data/sentinel")
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            self.data_dir = Path("/tmp/cipher_data/sentinel")
            self.data_dir.mkdir(parents=True, exist_ok=True)
        self.alerts_file = self.data_dir / "alerts.json"
        self.predictions_file = self.data_dir / "predictions.json"
        self.drafts_file = self.data_dir / "drafts.json"
        self.friction_log_file = self.data_dir / "friction_log.json"

        self.capabilities = [
            AgentCapability(
                name="monitor_email",
                description="Scan inbox for urgent items, deadlines, and action-required messages",
                category="monitoring",
                timeout=60,
            ),
            AgentCapability(
                name="monitor_sms",
                description="Monitor SMS/text messages for time-sensitive communications",
                category="monitoring",
                timeout=30,
            ),
            AgentCapability(
                name="predict_needs",
                description="Analyze patterns to predict upcoming needs before they arise",
                category="intelligence",
                timeout=45,
            ),
            AgentCapability(
                name="alert_digest",
                description="Generate prioritized alert digest with recommended actions",
                category="monitoring",
                timeout=30,
            ),
            AgentCapability(
                name="auto_respond",
                description="Draft preemptive responses for predictable situations",
                category="automation",
                timeout=45,
            ),
        ]

    async def validate(self, task: AgentTask) -> bool:
        """Validate task before execution."""
        operation = task.params.get("operation", "")
        valid_ops = [cap.name for cap in self.capabilities]
        if operation not in valid_ops:
            logger.warning(f"[sentinel] Unknown operation '{operation}', valid: {valid_ops}")
            return False
        return True

    async def execute(self, task: AgentTask) -> AgentResult:
        """Execute the specified operation."""
        operation = task.params.get("operation", "")
        try:
            if operation == "monitor_email":
                result = await self._monitor_email()
            elif operation == "monitor_sms":
                result = await self._monitor_sms()
            elif operation == "predict_needs":
                result = await self._predict_needs()
            elif operation == "alert_digest":
                result = await self._alert_digest()
            elif operation == "auto_respond":
                result = await self._auto_respond()
            else:
                result = None

            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=result is not None,
                output=result,
            )
        except Exception as e:
            logger.error(f"Sentinel Agent execution failed: {str(e)}")
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error=str(e),
            )

    async def verify(self, result: AgentResult) -> bool:
        """Verify the result of execution."""
        return result.success

    async def _monitor_email(self) -> Dict[str, Any]:
        """Monitor email inbox for urgent items and deadlines."""
        try:
            # Require real IMAP credentials
            imap_user = getattr(settings, 'imap_user', '') or ''
            imap_pass = getattr(settings, 'imap_pass', '') or ''
            imap_host = getattr(settings, 'imap_host', '') or ''

            if not imap_user or not imap_pass:
                return {
                    "source": "email",
                    "error": "Email monitoring not configured. Set IMAP_HOST, IMAP_USER, and IMAP_PASS environment variables to enable real inbox monitoring.",
                    "status": "not_configured",
                    "setup_hint": "For Gmail: use an App Password (not your regular password) with IMAP_HOST=imap.gmail.com",
                }

            alerts = await self._fetch_email_via_imap()

            # Store alerts
            self._save_alerts(alerts)
            return {
                "source": "email",
                "alerts_count": len(alerts),
                "alerts": [a.to_dict() for a in alerts],
                "status": "completed",
            }
        except Exception as e:
            logger.error(f"Email monitoring failed: {str(e)}")
            return {"source": "email", "error": str(e), "status": "failed"}

    async def _fetch_email_via_imap(self) -> List[AlertEntry]:
        """Fetch emails via IMAP and score for urgency."""
        import imaplib
        import email as email_lib
        from email.header import decode_header

        logger.info("Connecting to IMAP server to fetch emails")
        alerts: List[AlertEntry] = []

        try:
            # Connect to IMAP
            imap = imaplib.IMAP4_SSL(settings.imap_host)
            imap.login(settings.imap_user, settings.imap_pass)
            imap.select("INBOX")

            # Search for recent unread emails (last 3 days)
            since_date = (datetime.utcnow() - timedelta(days=3)).strftime("%d-%b-%Y")
            status, message_ids = imap.search(None, f'(UNSEEN SINCE {since_date})')

            if status != "OK" or not message_ids[0]:
                imap.logout()
                return alerts

            ids = message_ids[0].split()[-20:]  # Last 20 unread

            for msg_id in ids:
                try:
                    status, msg_data = imap.fetch(msg_id, "(RFC822)")
                    if status != "OK" or not msg_data[0]:
                        continue

                    raw_email = msg_data[0][1]
                    msg = email_lib.message_from_bytes(raw_email)

                    # Decode subject
                    subject_raw = msg.get("Subject", "")
                    decoded_parts = decode_header(subject_raw)
                    subject = ""
                    for part, enc in decoded_parts:
                        if isinstance(part, bytes):
                            subject += part.decode(enc or "utf-8", errors="replace")
                        else:
                            subject += part

                    sender = msg.get("From", "unknown")

                    # Extract body preview
                    body_preview = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() == "text/plain":
                                payload = part.get_payload(decode=True)
                                if payload:
                                    body_preview = payload.decode("utf-8", errors="replace")[:500]
                                    break
                    else:
                        payload = msg.get_payload(decode=True)
                        if payload:
                            body_preview = payload.decode("utf-8", errors="replace")[:500]

                    # Score and categorize
                    urgency = self._score_alert(subject, body_preview, sender)
                    category = self._categorize_alert(subject, body_preview)
                    deadline = self._extract_deadline(f"{subject} {body_preview}")

                    alert = AlertEntry(
                        id=f"email_{msg_id.decode()}",
                        source="email",
                        subject=subject,
                        sender=sender,
                        body_preview=body_preview[:200],
                        urgency_score=urgency,
                        category=category,
                        detected_deadline=deadline,
                        recommended_action=self._suggest_action(category, urgency),
                        status="new",
                    )
                    alerts.append(alert)

                except Exception as e:
                    logger.warning(f"Failed to parse email {msg_id}: {e}")
                    continue

            imap.logout()
            logger.info(f"Fetched {len(alerts)} alerts from IMAP")

        except imaplib.IMAP4.error as e:
            logger.error(f"IMAP connection/auth failed: {e}")
            raise RuntimeError(f"IMAP error: {e}")
        except Exception as e:
            logger.error(f"Email fetch failed: {e}")
            raise

        return alerts

    def _suggest_action(self, category: str, urgency: float) -> str:
        """Suggest an action based on category and urgency."""
        actions = {
            "financial": "Review and process payment or financial item",
            "scheduling": "Confirm availability and respond to scheduling request",
            "business": "Review business item and prepare response",
            "personal": "Review personal item and take action",
            "real_estate": "Review property-related item and respond",
        }
        base = actions.get(category, "Review and respond as needed")
        if urgency > 0.8:
            return f"URGENT: {base}"
        return base

    async def _monitor_sms(self) -> Dict[str, Any]:
        """Monitor SMS messages for time-sensitive communications."""
        try:
            twilio_sid = getattr(settings, 'twilio_account_sid', '') or ''
            twilio_token = getattr(settings, 'twilio_auth_token', '') or ''

            if not twilio_sid or not twilio_token:
                return {
                    "source": "sms",
                    "error": "SMS monitoring not configured. Set TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN environment variables to enable real SMS monitoring.",
                    "status": "not_configured",
                    "setup_hint": "Sign up at twilio.com and add your credentials to enable SMS monitoring.",
                }

            alerts = await self._fetch_sms_via_twilio()
            self._save_alerts(alerts)
            return {
                "source": "sms",
                "alerts_count": len(alerts),
                "alerts": [a.to_dict() for a in alerts],
                "status": "completed",
            }
        except Exception as e:
            logger.error(f"SMS monitoring failed: {str(e)}")
            return {"source": "sms", "error": str(e), "status": "failed"}

    async def _fetch_sms_via_twilio(self) -> List[AlertEntry]:
        """Fetch recent SMS via Twilio REST API and score for urgency."""
        import httpx

        twilio_sid = getattr(settings, 'twilio_account_sid', '') or ''
        twilio_token = getattr(settings, 'twilio_auth_token', '') or ''

        logger.info("Fetching SMS messages from Twilio API")
        alerts: List[AlertEntry] = []

        try:
            since_date = (datetime.utcnow() - timedelta(days=3)).strftime("%Y-%m-%d")
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    f"https://api.twilio.com/2010-04-01/Accounts/{twilio_sid}/Messages.json",
                    auth=(twilio_sid, twilio_token),
                    params={
                        "DateSent>": since_date,
                        "PageSize": 20,
                    },
                )
                resp.raise_for_status()
                data = resp.json()

            for msg in data.get("messages", []):
                # Only process inbound messages
                if msg.get("direction") not in ("inbound",):
                    continue

                body = msg.get("body", "")
                sender = msg.get("from", "unknown")
                sid = msg.get("sid", "")

                urgency = self._score_alert("", body, sender)
                category = self._categorize_alert("", body)
                deadline = self._extract_deadline(body)

                alert = AlertEntry(
                    id=f"sms_{sid[-8:]}",
                    source="sms",
                    subject=f"SMS from {sender}",
                    sender=sender,
                    body_preview=body[:200],
                    urgency_score=urgency,
                    category=category,
                    detected_deadline=deadline,
                    recommended_action=self._suggest_action(category, urgency),
                    status="new",
                )
                alerts.append(alert)

            logger.info(f"Fetched {len(alerts)} SMS alerts from Twilio")

        except Exception as e:
            logger.error(f"Twilio SMS fetch failed: {e}")
            raise RuntimeError(f"Twilio error: {e}")

        return alerts

    async def _predict_needs(self) -> Dict[str, Any]:
        """Analyze alert patterns to predict upcoming needs."""
        try:
            existing_alerts = self._load_alerts()
            predictions = []

            # Analyze patterns in existing alerts
            if len(existing_alerts) > 0:
                # Example: Look for recurring patterns (mock implementation)
                predictions = self._analyze_alert_patterns(existing_alerts)

            # Store predictions
            self._save_predictions(predictions)
            return {
                "predictions_count": len(predictions),
                "predictions": predictions,
                "forecast_window": "48 hours",
                "status": "completed",
            }
        except Exception as e:
            logger.error(f"Need prediction failed: {str(e)}")
            return {"error": str(e), "status": "failed"}

    def _analyze_alert_patterns(self, alerts: List[AlertEntry]) -> List[Dict[str, Any]]:
        """Analyze historical patterns to generate predictions."""
        predictions = []
        category_counts: Dict[str, int] = {}

        # Count alerts by category
        for alert in alerts:
            if alert.status != "resolved":
                category_counts[alert.category] = category_counts.get(alert.category, 0) + 1

        # Generate predictions for high-frequency categories
        for category, count in category_counts.items():
            if count >= 2:
                predictions.append({
                    "category": category,
                    "predicted_frequency": f"~{count} per monitoring cycle",
                    "confidence": min(0.95, 0.5 + (count * 0.15)),
                    "suggested_action": f"Prepare workflow for frequent {category} alerts",
                    "timeframe": "next 48 hours",
                })

        return predictions

    async def _alert_digest(self) -> Dict[str, Any]:
        """Generate prioritized alert digest with recommended actions."""
        try:
            alerts = self._load_alerts()
            digest = self._compile_digest(alerts)
            return {
                "total_alerts": len(alerts),
                "digest": digest,
                "generated_at": datetime.utcnow().isoformat(),
                "status": "completed",
            }
        except Exception as e:
            logger.error(f"Alert digest generation failed: {str(e)}")
            return {"error": str(e), "status": "failed"}

    def _compile_digest(self, alerts: List[AlertEntry]) -> Dict[str, Any]:
        """Compile alerts into prioritized, categorized digest."""
        # Filter to unresolved alerts
        unresolved = [a for a in alerts if a.status in ["new", "acknowledged"]]

        # Apply friction log to adjust scores
        friction_log = self._load_friction_log()
        for alert in unresolved:
            if alert.id in friction_log:
                alert.urgency_score *= 0.8  # Reduce by 20% if previously ignored

        # Sort by urgency score (descending)
        sorted_alerts = sorted(unresolved, key=lambda a: a.urgency_score, reverse=True)

        # Group by category
        categorized: Dict[str, List[AlertEntry]] = {}
        for alert in sorted_alerts:
            if alert.category not in categorized:
                categorized[alert.category] = []
            categorized[alert.category].append(alert)

        return {
            "by_category": {
                cat: [a.to_dict() for a in alerts]
                for cat, alerts in categorized.items()
            },
            "priority_order": [a.to_dict() for a in sorted_alerts[:10]],  # Top 10
            "total_unresolved": len(unresolved),
        }

    async def _auto_respond(self) -> Dict[str, Any]:
        """Draft preemptive responses for predictable situations."""
        try:
            alerts = self._load_alerts()
            drafts = self._generate_response_drafts(alerts)
            self._save_drafts(drafts)
            return {
                "drafts_count": len(drafts),
                "drafts": drafts,
                "note": "Drafts generated but NOT sent - require user approval",
                "status": "completed",
            }
        except Exception as e:
            logger.error(f"Auto-response generation failed: {str(e)}")
            return {"error": str(e), "status": "failed"}

    def _generate_response_drafts(self, alerts: List[AlertEntry]) -> List[Dict[str, Any]]:
        """Generate draft responses for predictable situations."""
        drafts = []

        for alert in alerts:
            if alert.status == "new" and alert.category == "scheduling":
                draft = {
                    "alert_id": alert.id,
                    "to": alert.sender,
                    "subject": f"Re: {alert.subject}",
                    "body": f"Thank you for the update. {alert.recommended_action}",
                    "type": "confirmation",
                    "requires_approval": True,
                }
                drafts.append(draft)

            elif alert.status == "new" and alert.category == "financial":
                draft = {
                    "alert_id": alert.id,
                    "to": alert.sender,
                    "subject": f"Re: {alert.subject}",
                    "body": f"Acknowledged. Processing: {alert.recommended_action}",
                    "type": "acknowledgment",
                    "requires_approval": True,
                }
                drafts.append(draft)

        return drafts

    def _score_alert(self, subject: str, body: str, sender: str) -> float:
        """Calculate urgency score for an alert (0-1.0)."""
        urgency_score = 0.0
        found_signals = 0

        # Check for urgency signals
        combined_text = f"{subject} {body}".lower()
        for pattern in URGENCY_SIGNALS:
            if re.search(pattern, combined_text, re.IGNORECASE):
                found_signals += 1
                urgency_score += 0.1

        # Cap at 1.0
        return min(1.0, urgency_score)

    def _categorize_alert(self, subject: str, body: str) -> str:
        """Determine alert category based on content."""
        combined_text = f"{subject} {body}".lower()

        for category, keywords in CATEGORY_RULES.items():
            for keyword in keywords:
                if keyword.lower() in combined_text:
                    return category

        return "general"

    def _extract_deadline(self, text: str) -> Optional[datetime]:
        """Extract deadline date/time from text."""
        # Placeholder: would use more sophisticated date parsing
        # This is a simplified pattern match
        if re.search(r"today", text, re.IGNORECASE):
            return datetime.utcnow()
        elif re.search(r"tomorrow", text, re.IGNORECASE):
            return datetime.utcnow() + timedelta(days=1)
        return None

    def _load_alerts(self) -> List[AlertEntry]:
        """Load alerts from disk."""
        if not self.alerts_file.exists():
            return []
        with open(self.alerts_file, "r") as f:
            data = json.load(f)
            return [AlertEntry.from_dict(item) for item in data]

    def _save_alerts(self, alerts: List[AlertEntry]) -> None:
        """Save alerts to disk."""
        with open(self.alerts_file, "w") as f:
            json.dump([a.to_dict() for a in alerts], f, indent=2)

    def _load_predictions(self) -> List[Dict[str, Any]]:
        """Load predictions from disk."""
        if not self.predictions_file.exists():
            return []
        with open(self.predictions_file, "r") as f:
            return json.load(f)

    def _save_predictions(self, predictions: List[Dict[str, Any]]) -> None:
        """Save predictions to disk."""
        with open(self.predictions_file, "w") as f:
            json.dump(predictions, f, indent=2)

    def _load_drafts(self) -> List[Dict[str, Any]]:
        """Load draft responses from disk."""
        if not self.drafts_file.exists():
            return []
        with open(self.drafts_file, "r") as f:
            return json.load(f)

    def _save_drafts(self, drafts: List[Dict[str, Any]]) -> None:
        """Save draft responses to disk."""
        with open(self.drafts_file, "w") as f:
            json.dump(drafts, f, indent=2)

    def _load_friction_log(self) -> Dict[str, int]:
        """Load friction log for previously ignored alerts."""
        if not self.friction_log_file.exists():
            return {}
        with open(self.friction_log_file, "r") as f:
            return json.load(f)

    def _save_friction_log(self, log: Dict[str, int]) -> None:
        """Save friction log for self-correction."""
        with open(self.friction_log_file, "w") as f:
            json.dump(log, f, indent=2)
