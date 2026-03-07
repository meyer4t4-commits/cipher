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
    version = "1.0.0"

    def __init__(self):
        """Initialize Sentinel Agent with capabilities."""
        super().__init__(
            name="sentinel",
            description="Proactive alerts — monitors email/SMS, predicts needs, generates prioritized action digests",
            version="1.0.0",
        )
        self.data_dir = Path("data/sentinel")
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

    async def validate(self, task: AgentTask) -> Tuple[bool, Optional[str]]:
        """Validate task before execution."""
        if task.operation not in [cap.name for cap in self.capabilities]:
            return False, f"Unknown operation: {task.operation}"
        return True, None

    async def execute(self, task: AgentTask) -> AgentResult:
        """Execute the specified operation."""
        try:
            valid, error = await self.validate(task)
            if not valid:
                return AgentResult(success=False, error=error, operation=task.operation)

            if task.operation == "monitor_email":
                result = await self._monitor_email()
            elif task.operation == "monitor_sms":
                result = await self._monitor_sms()
            elif task.operation == "predict_needs":
                result = await self._predict_needs()
            elif task.operation == "alert_digest":
                result = await self._alert_digest()
            elif task.operation == "auto_respond":
                result = await self._auto_respond()
            else:
                result = None

            return AgentResult(
                success=result is not None,
                data=result,
                operation=task.operation,
            )
        except Exception as e:
            logger.error(f"Sentinel Agent execution failed: {str(e)}")
            return AgentResult(success=False, error=str(e), operation=task.operation)

    async def verify(self, result: AgentResult) -> bool:
        """Verify the result of execution."""
        return result.success

    async def _monitor_email(self) -> Dict[str, Any]:
        """Monitor email inbox for urgent items and deadlines."""
        try:
            # Try to connect via IMAP if configured
            if hasattr(settings, 'imap_host') and settings.imap_host:
                alerts = await self._fetch_email_via_imap()
            else:
                logger.warning("IMAP not configured, using mock email data")
                alerts = self._generate_mock_email_data()

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
        # Placeholder: Real implementation would connect to IMAP server
        # This demonstrates the pattern; actual IMAP logic would go here
        logger.debug("Fetching emails via IMAP")
        alerts = []
        # Implementation would iterate through unread emails, score them, extract deadlines, categorize
        return alerts

    def _generate_mock_email_data(self) -> List[AlertEntry]:
        """Generate mock email data for testing."""
        return [
            AlertEntry(
                id="email_001",
                source="email",
                subject="Invoice #12345 - Payment Due Today",
                sender="billing@client.com",
                body_preview="Your invoice is due today. Please remit payment immediately.",
                urgency_score=0.95,
                category="financial",
                detected_deadline=datetime.utcnow(),
                recommended_action="Review invoice and process payment",
                status="new",
            ),
            AlertEntry(
                id="email_002",
                source="email",
                subject="Meeting Rescheduled - Confirm New Time",
                sender="colleague@company.com",
                body_preview="Can we move our Thursday meeting to Friday at 2pm?",
                urgency_score=0.65,
                category="scheduling",
                recommended_action="Confirm availability for new meeting time",
                status="new",
            ),
        ]

    async def _monitor_sms(self) -> Dict[str, Any]:
        """Monitor SMS messages for time-sensitive communications."""
        try:
            if hasattr(settings, 'twilio_account_sid') and settings.twilio_account_sid:
                alerts = await self._fetch_sms_via_twilio()
            else:
                logger.warning("Twilio not configured, using mock SMS data")
                alerts = self._generate_mock_sms_data()

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
        """Fetch SMS via Twilio API and parse for urgency."""
        logger.debug("Fetching SMS via Twilio")
        alerts = []
        # Implementation would connect to Twilio, fetch messages, parse for urgency signals
        return alerts

    def _generate_mock_sms_data(self) -> List[AlertEntry]:
        """Generate mock SMS data for testing."""
        return [
            AlertEntry(
                id="sms_001",
                source="sms",
                subject="Appointment Reminder",
                sender="+1234567890",
                body_preview="Reminder: Your appointment is tomorrow at 2pm. Reply to confirm.",
                urgency_score=0.70,
                category="personal",
                detected_deadline=datetime.utcnow() + timedelta(days=1),
                recommended_action="Confirm appointment attendance",
                status="new",
            ),
        ]

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
