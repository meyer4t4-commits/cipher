"""
Communication Agent - Email, Slack, Telegram, SMS, and Push Notifications.
REAL API CALLS — uses actual SMTP, Telegram Bot API, Firebase Cloud Messaging, etc.
REQUIRES APPROVAL FOR: sending any message.
"""

import json
import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Optional

import httpx

from app.agents.base import BaseAgent
from app.agents.models import AgentCapability, AgentResult, AgentTask
from app.core.config import settings
from app.core.logging import logger


class CommunicationAgent(BaseAgent):
    """Send and receive messages across multiple channels — real API calls."""

    def __init__(self):
        """Initialize the communication agent."""
        super().__init__(
            name="communication_agent",
            description="Email, Slack, Telegram, SMS, and Push Notifications",
            version="3.0.0",
            capabilities=[
                AgentCapability(
                    name="send_email",
                    description="Send an email message",
                    category="communication",
                    requires_approval=True,
                    timeout_seconds=15,
                ),
                AgentCapability(
                    name="read_email",
                    description="Read incoming emails (requires IMAP config)",
                    category="data",
                    timeout_seconds=15,
                ),
                AgentCapability(
                    name="send_slack",
                    description="Send Slack message",
                    category="communication",
                    requires_approval=True,
                    timeout_seconds=10,
                ),
                AgentCapability(
                    name="send_telegram",
                    description="Send Telegram message",
                    category="communication",
                    requires_approval=True,
                    timeout_seconds=10,
                ),
                AgentCapability(
                    name="send_sms",
                    description="Send SMS message (requires Twilio config)",
                    category="communication",
                    requires_approval=True,
                    timeout_seconds=10,
                ),
                AgentCapability(
                    name="send_push",
                    description="Send push notification to user devices via FCM",
                    category="communication",
                    requires_approval=True,
                    timeout_seconds=10,
                ),
                AgentCapability(
                    name="send_push_topic",
                    description="Send push notification to a topic (broadcast to all subscribers)",
                    category="communication",
                    requires_approval=True,
                    timeout_seconds=10,
                ),
                AgentCapability(
                    name="register_device",
                    description="Register a device token for push notifications",
                    category="data",
                    timeout_seconds=5,
                ),
                AgentCapability(
                    name="unregister_device",
                    description="Unregister a device token",
                    category="data",
                    timeout_seconds=5,
                ),
                AgentCapability(
                    name="compose_template",
                    description="Compose message from template",
                    category="data",
                    timeout_seconds=5,
                ),
                AgentCapability(
                    name="list_templates",
                    description="List available message templates",
                    category="data",
                    timeout_seconds=5,
                ),
            ],
        )
        self.templates = {
            "alert": "ALERT: {message}",
            "notification": "Notification: {message}",
            "reminder": "Reminder: {message}",
            "summary": "Summary Report:\n{message}",
            "intel_brief": "Intelligence Update:\n\n{message}\n\n— Cipher",
        }
        # Device token storage for push notifications
        self._device_store_path = Path("./data/push/device_tokens.json")
        self._device_store_path.parent.mkdir(parents=True, exist_ok=True)
        self._fcm_token_cache: Optional[dict] = None
        self._fcm_token_expiry: Optional[datetime] = None

    def requires_approval_for(self, instruction: str) -> bool:
        """All message sending requires approval."""
        send_ops = ["send_email", "send_slack", "send_telegram", "send_sms", "send_push"]
        return any(op in instruction for op in send_ops)

    async def validate(self, task: AgentTask) -> bool:
        """Validate communication task."""
        if not await super().validate(task):
            return False

        operation = task.params.get("operation", "send_email")

        # All send operations require approval
        send_ops = ["send_email", "send_slack", "send_telegram", "send_sms", "send_push", "send_push_topic"]
        if operation in send_ops:
            if not task.approved_at:
                logger.warning(f"Task {task.task_id}: Message send requires approval")
                return False

        # Validate required parameters for each operation
        if operation == "send_email":
            if "to" not in task.params:
                logger.warning(f"Task {task.task_id}: Missing 'to' parameter")
                return False
            if "subject" not in task.params or "body" not in task.params:
                logger.warning(f"Task {task.task_id}: Missing 'subject' or 'body'")
                return False

        elif operation == "send_slack":
            if "channel" not in task.params and "user" not in task.params:
                logger.warning(f"Task {task.task_id}: Missing 'channel' or 'user'")
                return False
            if "message" not in task.params:
                logger.warning(f"Task {task.task_id}: Missing 'message'")
                return False

        elif operation == "send_telegram":
            if "chat_id" not in task.params:
                logger.warning(f"Task {task.task_id}: Missing 'chat_id'")
                return False
            if "message" not in task.params:
                logger.warning(f"Task {task.task_id}: Missing 'message'")
                return False

        elif operation == "send_sms":
            if "phone" not in task.params:
                logger.warning(f"Task {task.task_id}: Missing 'phone'")
                return False
            if "message" not in task.params:
                logger.warning(f"Task {task.task_id}: Missing 'message'")
                return False

        elif operation == "send_push":
            if "user_id" not in task.params and "device_token" not in task.params:
                logger.warning(f"Task {task.task_id}: Missing 'user_id' or 'device_token'")
                return False
            if "title" not in task.params or "body" not in task.params:
                logger.warning(f"Task {task.task_id}: Missing 'title' or 'body'")
                return False

        elif operation == "send_push_topic":
            if "topic" not in task.params:
                logger.warning(f"Task {task.task_id}: Missing 'topic'")
                return False
            if "title" not in task.params or "body" not in task.params:
                logger.warning(f"Task {task.task_id}: Missing 'title' or 'body'")
                return False

        elif operation == "register_device":
            if "user_id" not in task.params or "device_token" not in task.params:
                logger.warning(f"Task {task.task_id}: Missing 'user_id' or 'device_token'")
                return False

        return True

    async def execute(self, task: AgentTask) -> AgentResult:
        """Execute communication operation."""
        operation = task.params.get("operation", "send_email")

        try:
            if operation == "send_email":
                return await self._send_email(task)
            elif operation == "read_email":
                return await self._read_email(task)
            elif operation == "send_slack":
                return await self._send_slack(task)
            elif operation == "send_telegram":
                return await self._send_telegram(task)
            elif operation == "send_sms":
                return await self._send_sms(task)
            elif operation == "send_push":
                return await self._send_push(task)
            elif operation == "send_push_topic":
                return await self._send_push_topic(task)
            elif operation == "register_device":
                return await self._register_device(task)
            elif operation == "unregister_device":
                return await self._unregister_device(task)
            elif operation == "compose_template":
                return await self._compose_template(task)
            elif operation == "list_templates":
                return await self._list_templates(task)
            else:
                return AgentResult(
                    task_id=task.task_id,
                    agent_name=self.name,
                    success=False,
                    error=f"Unknown operation: {operation}",
                )
        except Exception as e:
            logger.error(f"Communication operation failed: {e}")
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error=str(e),
            )

    async def _send_email(self, task: AgentTask) -> AgentResult:
        """Send email — tries Resend API first, falls back to SMTP."""
        to = task.params.get("to")
        subject = task.params.get("subject")
        body = task.params.get("body")
        cc = task.params.get("cc", [])

        # Try Resend API first (easier setup, better deliverability)
        resend_key = getattr(settings, "resend_api_key", "")
        if resend_key:
            return await self._send_email_resend(task, to, subject, body, cc, resend_key)

        # Fall back to SMTP
        smtp_host = task.params.get("smtp_host", getattr(settings, "smtp_host", ""))
        smtp_port = task.params.get("smtp_port", getattr(settings, "smtp_port", 587))
        smtp_user = task.params.get("smtp_user", getattr(settings, "smtp_user", ""))
        smtp_pass = task.params.get("smtp_pass", getattr(settings, "smtp_pass", ""))
        from_email = task.params.get("from_email", smtp_user or "cipher@elysianprotocol.io")

        if not smtp_host or not smtp_user:
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error=(
                    "Email not configured. Set RESEND_API_KEY (recommended) or "
                    "SMTP_HOST + SMTP_USER + SMTP_PASS in Railway environment variables."
                ),
            )

        try:
            msg = MIMEMultipart()
            msg["From"] = from_email
            msg["To"] = to if isinstance(to, str) else ", ".join(to)
            msg["Subject"] = subject
            if cc:
                msg["Cc"] = ", ".join(cc) if isinstance(cc, list) else cc

            msg.attach(MIMEText(body, "html" if "<" in body else "plain"))

            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.ehlo()
                server.starttls()
                server.login(smtp_user, smtp_pass)
                recipients = [to] if isinstance(to, str) else to
                if cc:
                    recipients += cc if isinstance(cc, list) else [cc]
                server.send_message(msg)

            logger.info(f"Email sent to {to}: {subject}")

            output = {
                "operation": "send_email",
                "to": to,
                "subject": subject,
                "status": "sent",
                "from": from_email,
                "sent_at": datetime.utcnow().isoformat(),
            }

        except smtplib.SMTPAuthenticationError:
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error="SMTP authentication failed. Check SMTP_USER and SMTP_PASS.",
            )
        except Exception as e:
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error=f"Email send failed: {str(e)}",
            )

        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            success=True,
            output=output,
        )

    async def _send_email_resend(self, task, to, subject, body, cc, api_key) -> AgentResult:
        """Send email via Resend API — simpler setup, better deliverability than SMTP."""
        from_email = task.params.get("from_email", "cipher@elysianprotocol.io")

        try:
            payload = {
                "from": from_email,
                "to": [to] if isinstance(to, str) else to,
                "subject": subject,
            }
            # Detect HTML vs plain text
            if "<" in body and ">" in body:
                payload["html"] = body
            else:
                payload["text"] = body

            if cc:
                payload["cc"] = cc if isinstance(cc, list) else [cc]

            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    "https://api.resend.com/emails",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                data = resp.json()

            if resp.status_code >= 400:
                error_msg = data.get("message", data.get("error", str(data)))
                return AgentResult(
                    task_id=task.task_id,
                    agent_name=self.name,
                    success=False,
                    error=f"Resend API error: {error_msg}",
                )

            logger.info(f"Email sent via Resend to {to}: {subject}")

            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=True,
                output={
                    "operation": "send_email",
                    "provider": "resend",
                    "to": to,
                    "subject": subject,
                    "status": "sent",
                    "from": from_email,
                    "email_id": data.get("id", ""),
                    "sent_at": datetime.utcnow().isoformat(),
                },
            )

        except Exception as e:
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error=f"Resend email failed: {str(e)}",
            )

    async def _read_email(self, task: AgentTask) -> AgentResult:
        """Read emails — real IMAP. Requires IMAP config."""
        folder = task.params.get("folder", "INBOX")
        limit = task.params.get("limit", 10)

        imap_host = task.params.get("imap_host", getattr(settings, "imap_host", ""))
        imap_user = task.params.get("imap_user", getattr(settings, "imap_user", ""))
        imap_pass = task.params.get("imap_pass", getattr(settings, "imap_pass", ""))

        if not imap_host or not imap_user:
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error=(
                    "IMAP not configured. Set IMAP_HOST, IMAP_USER, IMAP_PASS "
                    "in .env to enable email reading."
                ),
            )

        try:
            import imaplib
            import email
            from email.header import decode_header

            mail = imaplib.IMAP4_SSL(imap_host)
            mail.login(imap_user, imap_pass)
            mail.select(folder)

            _, messages = mail.search(None, "ALL")
            message_ids = messages[0].split()

            emails = []
            # Get last N messages
            for msg_id in message_ids[-limit:]:
                _, msg_data = mail.fetch(msg_id, "(RFC822 FLAGS)")
                raw = msg_data[0][1]
                msg = email.message_from_bytes(raw)

                subject = ""
                decoded = decode_header(msg["Subject"] or "")
                for part, enc in decoded:
                    if isinstance(part, bytes):
                        subject += part.decode(enc or "utf-8", errors="replace")
                    else:
                        subject += part

                from_addr = msg["From"] or ""
                date = msg["Date"] or ""

                # Get body preview
                preview = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == "text/plain":
                            preview = part.get_payload(decode=True).decode("utf-8", errors="replace")[:200]
                            break
                else:
                    preview = msg.get_payload(decode=True).decode("utf-8", errors="replace")[:200]

                # Check flags for unread
                flags_data = msg_data[0][0] if msg_data[0][0] else b""
                unread = b"\\Seen" not in flags_data

                emails.append({
                    "from": from_addr,
                    "subject": subject,
                    "date": date,
                    "preview": preview.strip(),
                    "unread": unread,
                })

            mail.logout()

            output = {
                "operation": "read_email",
                "folder": folder,
                "emails": list(reversed(emails)),  # Newest first
                "total": len(emails),
                "unread": sum(1 for e in emails if e.get("unread")),
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error=f"Email read failed: {str(e)}",
            )

        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            success=True,
            output=output,
        )

    async def _send_slack(self, task: AgentTask) -> AgentResult:
        """Send Slack message — real Slack Web API call."""
        channel = task.params.get("channel")
        user = task.params.get("user")
        message = task.params.get("message")

        slack_token = task.params.get("slack_token", getattr(settings, "slack_bot_token", ""))

        if not slack_token:
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error="Slack not configured. Set SLACK_BOT_TOKEN in .env.",
            )

        target = channel or user

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://slack.com/api/chat.postMessage",
                    headers={"Authorization": f"Bearer {slack_token}"},
                    json={
                        "channel": target,
                        "text": message,
                    },
                )
                data = response.json()

            if not data.get("ok"):
                return AgentResult(
                    task_id=task.task_id,
                    agent_name=self.name,
                    success=False,
                    error=f"Slack API error: {data.get('error', 'unknown')}",
                )

            output = {
                "operation": "send_slack",
                "target": target,
                "target_type": "channel" if channel else "user",
                "status": "sent",
                "timestamp": data.get("ts", ""),
                "thread_ts": data.get("message", {}).get("ts", ""),
            }

        except Exception as e:
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error=f"Slack send failed: {str(e)}",
            )

        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            success=True,
            output=output,
        )

    async def _send_telegram(self, task: AgentTask) -> AgentResult:
        """Send Telegram message — real Telegram Bot API call."""
        chat_id = task.params.get("chat_id")
        message = task.params.get("message")
        parse_mode = task.params.get("parse_mode", "HTML")

        bot_token = settings.telegram_bot_token
        if not bot_token:
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error="Telegram not configured. Set TELEGRAM_BOT_TOKEN in .env.",
            )

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"https://api.telegram.org/bot{bot_token}/sendMessage",
                    json={
                        "chat_id": chat_id,
                        "text": message,
                        "parse_mode": parse_mode,
                    },
                )
                data = response.json()

            if not data.get("ok"):
                return AgentResult(
                    task_id=task.task_id,
                    agent_name=self.name,
                    success=False,
                    error=f"Telegram API error: {data.get('description', 'unknown')}",
                )

            result_msg = data.get("result", {})

            output = {
                "operation": "send_telegram",
                "chat_id": chat_id,
                "status": "sent",
                "message_id": result_msg.get("message_id"),
                "sent_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error=f"Telegram send failed: {str(e)}",
            )

        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            success=True,
            output=output,
        )

    async def _send_sms(self, task: AgentTask) -> AgentResult:
        """Send SMS — real Twilio API call."""
        phone = task.params.get("phone")
        message = task.params.get("message")

        twilio_sid = task.params.get("twilio_sid", getattr(settings, "twilio_account_sid", ""))
        twilio_token = task.params.get("twilio_token", getattr(settings, "twilio_auth_token", ""))
        twilio_from = task.params.get("twilio_from", getattr(settings, "twilio_phone_number", ""))

        if not twilio_sid or not twilio_token or not twilio_from:
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error=(
                    "Twilio not configured. Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, "
                    "TWILIO_PHONE_NUMBER in .env to enable SMS."
                ),
            )

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"https://api.twilio.com/2010-04-01/Accounts/{twilio_sid}/Messages.json",
                    auth=(twilio_sid, twilio_token),
                    data={
                        "To": phone,
                        "From": twilio_from,
                        "Body": message,
                    },
                )
                data = response.json()

            if response.status_code >= 400:
                return AgentResult(
                    task_id=task.task_id,
                    agent_name=self.name,
                    success=False,
                    error=f"Twilio error: {data.get('message', 'unknown')}",
                )

            output = {
                "operation": "send_sms",
                "phone": phone,
                "status": data.get("status", "queued"),
                "message_sid": data.get("sid", ""),
                "sent_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error=f"SMS send failed: {str(e)}",
            )

        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            success=True,
            output=output,
        )

    # ── Push Notification Helpers ──────────────────────────────────────────

    def _load_device_tokens(self) -> dict:
        """Load device token registry from disk. Format: {user_id: [tokens]}."""
        if self._device_store_path.exists():
            try:
                return json.loads(self._device_store_path.read_text())
            except Exception:
                return {}
        return {}

    def _save_device_tokens(self, store: dict) -> None:
        """Persist device token registry to disk."""
        self._device_store_path.parent.mkdir(parents=True, exist_ok=True)
        self._device_store_path.write_text(json.dumps(store, indent=2))

    async def _get_fcm_access_token(self) -> str:
        """
        Get OAuth2 access token for FCM v1 API using a service account JSON key.
        Uses google-auth library if available, otherwise falls back to manual JWT.
        """
        sa_path = getattr(settings, "fcm_service_account_path", "")
        if not sa_path or not Path(sa_path).exists():
            raise ValueError(
                "FCM not configured. Set FCM_SERVICE_ACCOUNT_PATH in .env "
                "pointing to your Firebase service account JSON file."
            )

        # Check cache
        if self._fcm_token_cache and self._fcm_token_expiry:
            if datetime.utcnow() < self._fcm_token_expiry:
                return self._fcm_token_cache["access_token"]

        try:
            # Try google-auth library first (preferred)
            from google.oauth2 import service_account
            from google.auth.transport.requests import Request

            credentials = service_account.Credentials.from_service_account_file(
                sa_path,
                scopes=["https://www.googleapis.com/auth/firebase.messaging"],
            )
            credentials.refresh(Request())

            self._fcm_token_cache = {"access_token": credentials.token}
            self._fcm_token_expiry = credentials.expiry
            return credentials.token

        except ImportError:
            # Fallback: manual JWT signing with PyJWT
            import time

            try:
                import jwt as pyjwt
            except ImportError:
                raise ImportError(
                    "Push notifications require either 'google-auth' or 'PyJWT' package. "
                    "Install with: pip install google-auth google-auth-httplib2"
                )

            sa_data = json.loads(Path(sa_path).read_text())
            now = int(time.time())

            payload = {
                "iss": sa_data["client_email"],
                "sub": sa_data["client_email"],
                "aud": "https://oauth2.googleapis.com/token",
                "iat": now,
                "exp": now + 3600,
                "scope": "https://www.googleapis.com/auth/firebase.messaging",
            }

            signed_jwt = pyjwt.encode(
                payload, sa_data["private_key"], algorithm="RS256"
            )

            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://oauth2.googleapis.com/token",
                    data={
                        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                        "assertion": signed_jwt,
                    },
                )
                token_data = resp.json()

            if "access_token" not in token_data:
                raise ValueError(f"FCM token exchange failed: {token_data}")

            self._fcm_token_cache = token_data
            from datetime import timedelta
            self._fcm_token_expiry = datetime.utcnow() + timedelta(seconds=3500)
            return token_data["access_token"]

    def _get_fcm_project_id(self) -> str:
        """Extract project ID from service account JSON."""
        sa_path = getattr(settings, "fcm_service_account_path", "")
        if sa_path and Path(sa_path).exists():
            sa_data = json.loads(Path(sa_path).read_text())
            return sa_data.get("project_id", "")
        return getattr(settings, "fcm_project_id", "")

    # ── Push Notification Operations ────────────────────────────────────────

    async def _send_push(self, task: AgentTask) -> AgentResult:
        """
        Send push notification to a specific user or device via Firebase Cloud Messaging v1 API.
        Supports: title, body, image, data payload, sound, badge, click action.
        """
        user_id = task.params.get("user_id")
        device_token = task.params.get("device_token")
        title = task.params.get("title")
        body = task.params.get("body")
        image_url = task.params.get("image_url")
        data = task.params.get("data", {})
        sound = task.params.get("sound", "default")
        badge = task.params.get("badge")
        click_action = task.params.get("click_action")
        priority = task.params.get("priority", "high")

        # Resolve device tokens
        tokens = []
        if device_token:
            tokens = [device_token]
        elif user_id:
            store = self._load_device_tokens()
            tokens = store.get(str(user_id), [])
            if not tokens:
                return AgentResult(
                    task_id=task.task_id,
                    agent_name=self.name,
                    success=False,
                    error=f"No registered devices for user '{user_id}'. "
                          f"Device must call /register_device first.",
                )

        try:
            access_token = await self._get_fcm_access_token()
            project_id = self._get_fcm_project_id()

            if not project_id:
                return AgentResult(
                    task_id=task.task_id,
                    agent_name=self.name,
                    success=False,
                    error="FCM project_id not found in service account.",
                )

            url = f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"

            results = []
            for token in tokens:
                # Build FCM v1 message
                notification = {"title": title, "body": body}
                if image_url:
                    notification["image"] = image_url

                android_config = {
                    "priority": priority,
                    "notification": {"sound": sound, "channel_id": "cipher_default"},
                }

                apns_config = {
                    "payload": {
                        "aps": {
                            "sound": sound,
                            "mutable-content": 1,
                        }
                    }
                }
                if badge is not None:
                    apns_config["payload"]["aps"]["badge"] = badge

                webpush_config = {}
                if click_action:
                    webpush_config["fcm_options"] = {"link": click_action}

                message = {
                    "message": {
                        "token": token,
                        "notification": notification,
                        "data": {k: str(v) for k, v in data.items()} if data else {},
                        "android": android_config,
                        "apns": apns_config,
                    }
                }
                if webpush_config:
                    message["message"]["webpush"] = webpush_config

                async with httpx.AsyncClient() as client:
                    resp = await client.post(
                        url,
                        headers={
                            "Authorization": f"Bearer {access_token}",
                            "Content-Type": "application/json",
                        },
                        json=message,
                    )
                    resp_data = resp.json()

                if resp.status_code == 200:
                    results.append({
                        "token": token[:20] + "...",
                        "status": "sent",
                        "message_name": resp_data.get("name", ""),
                    })
                else:
                    error_info = resp_data.get("error", {})
                    error_code = error_info.get("code", resp.status_code)
                    error_msg = error_info.get("message", "unknown")

                    # Auto-remove invalid tokens
                    if error_code in [404, "NOT_FOUND", "UNREGISTERED"]:
                        self._remove_token(token)
                        results.append({
                            "token": token[:20] + "...",
                            "status": "removed_invalid",
                            "error": error_msg,
                        })
                    else:
                        results.append({
                            "token": token[:20] + "...",
                            "status": "failed",
                            "error": f"{error_code}: {error_msg}",
                        })

            sent_count = sum(1 for r in results if r["status"] == "sent")

            output = {
                "operation": "send_push",
                "user_id": user_id,
                "title": title,
                "body": body,
                "devices_targeted": len(tokens),
                "sent": sent_count,
                "failed": len(tokens) - sent_count,
                "results": results,
                "sent_at": datetime.utcnow().isoformat(),
            }

        except ValueError as e:
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error=str(e),
            )
        except Exception as e:
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error=f"Push notification failed: {str(e)}",
            )

        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            success=sent_count > 0,
            output=output,
        )

    async def _send_push_topic(self, task: AgentTask) -> AgentResult:
        """
        Send push notification to an FCM topic — broadcasts to all subscribed devices.
        Topics: 'all_users', 'updates', 'alerts', custom topics.
        """
        topic = task.params.get("topic")
        title = task.params.get("title")
        body = task.params.get("body")
        image_url = task.params.get("image_url")
        data = task.params.get("data", {})

        try:
            access_token = await self._get_fcm_access_token()
            project_id = self._get_fcm_project_id()

            if not project_id:
                return AgentResult(
                    task_id=task.task_id,
                    agent_name=self.name,
                    success=False,
                    error="FCM project_id not found in service account.",
                )

            url = f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"

            notification = {"title": title, "body": body}
            if image_url:
                notification["image"] = image_url

            message = {
                "message": {
                    "topic": topic,
                    "notification": notification,
                    "data": {k: str(v) for k, v in data.items()} if data else {},
                    "android": {"priority": "high"},
                    "apns": {"payload": {"aps": {"sound": "default"}}},
                }
            }

            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json",
                    },
                    json=message,
                )
                resp_data = resp.json()

            if resp.status_code != 200:
                error_info = resp_data.get("error", {})
                return AgentResult(
                    task_id=task.task_id,
                    agent_name=self.name,
                    success=False,
                    error=f"FCM topic send failed: {error_info.get('message', 'unknown')}",
                )

            output = {
                "operation": "send_push_topic",
                "topic": topic,
                "title": title,
                "body": body,
                "status": "sent",
                "message_name": resp_data.get("name", ""),
                "sent_at": datetime.utcnow().isoformat(),
            }

        except ValueError as e:
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error=str(e),
            )
        except Exception as e:
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error=f"Push topic send failed: {str(e)}",
            )

        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            success=True,
            output=output,
        )

    async def _register_device(self, task: AgentTask) -> AgentResult:
        """
        Register a device token for a user. Called when the app starts on a device.
        Each user can have multiple devices (phone, tablet, web browser).
        """
        user_id = str(task.params.get("user_id"))
        device_token = task.params.get("device_token")
        device_type = task.params.get("device_type", "unknown")  # ios, android, web
        device_name = task.params.get("device_name", "")

        store = self._load_device_tokens()

        if user_id not in store:
            store[user_id] = []

        # Avoid duplicates
        existing_tokens = [t if isinstance(t, str) else t.get("token", "") for t in store[user_id]]
        if device_token in existing_tokens:
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=True,
                output={
                    "operation": "register_device",
                    "user_id": user_id,
                    "status": "already_registered",
                    "device_count": len(store[user_id]),
                },
            )

        # Store as structured entry
        store[user_id].append({
            "token": device_token,
            "type": device_type,
            "name": device_name,
            "registered_at": datetime.utcnow().isoformat(),
        })
        self._save_device_tokens(store)

        logger.info(f"Registered device for user {user_id}: {device_type} ({device_name})")

        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            success=True,
            output={
                "operation": "register_device",
                "user_id": user_id,
                "device_type": device_type,
                "status": "registered",
                "device_count": len(store[user_id]),
            },
        )

    async def _unregister_device(self, task: AgentTask) -> AgentResult:
        """Remove a device token (user logged out, uninstalled, etc.)."""
        user_id = str(task.params.get("user_id", ""))
        device_token = task.params.get("device_token")

        removed = self._remove_token(device_token, user_id)

        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            success=True,
            output={
                "operation": "unregister_device",
                "status": "removed" if removed else "not_found",
                "device_token": device_token[:20] + "..." if device_token else "",
            },
        )

    def _remove_token(self, token: str, user_id: str = "") -> bool:
        """Remove a device token from the store. Searches all users if user_id empty."""
        store = self._load_device_tokens()
        removed = False

        users_to_check = [user_id] if user_id else list(store.keys())

        for uid in users_to_check:
            if uid in store:
                original = len(store[uid])
                store[uid] = [
                    t for t in store[uid]
                    if (t if isinstance(t, str) else t.get("token", "")) != token
                ]
                if len(store[uid]) < original:
                    removed = True

        if removed:
            self._save_device_tokens(store)

        return removed

    async def _compose_template(self, task: AgentTask) -> AgentResult:
        """Compose message from template."""
        template_name = task.params.get("template")
        variables = task.params.get("variables", {})

        if template_name not in self.templates:
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error=f"Template '{template_name}' not found. Available: {list(self.templates.keys())}",
            )

        template = self.templates[template_name]
        try:
            message = template.format(**variables)
        except KeyError as e:
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error=f"Missing template variable: {e}",
            )

        output = {
            "operation": "compose_template",
            "template": template_name,
            "message": message,
            "variables_used": list(variables.keys()),
        }

        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            success=True,
            output=output,
        )

    async def _list_templates(self, task: AgentTask) -> AgentResult:
        """List available templates."""
        output = {
            "operation": "list_templates",
            "templates": [
                {"name": name, "template": template}
                for name, template in self.templates.items()
            ],
            "count": len(self.templates),
        }

        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            success=True,
            output=output,
        )

    async def verify(self, result: AgentResult) -> bool:
        """Verify communication result."""
        if not isinstance(result.output, dict):
            logger.warning(f"Result {result.task_id}: Output is not a dict")
            return False

        if "operation" not in result.output:
            logger.warning(f"Result {result.task_id}: Missing 'operation'")
            return False

        if "send_" in result.output.get("operation", ""):
            if "status" not in result.output:
                logger.warning(f"Result {result.task_id}: Missing 'status'")
                return False

        return True
