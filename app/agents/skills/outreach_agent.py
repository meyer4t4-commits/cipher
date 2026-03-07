"""
Outreach Agent — Multi-channel engagement hand for the Global Expansion Pulse.

Takes audited/ranked targets from the Analyst Agent and handles:
- Hyper-personalized email outreach using audit data
- LinkedIn message drafts (connection request + follow-up sequence)
- Integration proposal generation (custom to each target's gaps)
- Follow-up sequence management (3-touch cadence)
- Response tracking and conversion metrics

Uses the existing Communication Agent's SMTP infrastructure for actual sending.

Capabilities:
1. draft_cold_email — Generate personalized cold outreach email
2. draft_linkedin_message — Generate LinkedIn connection + follow-up messages
3. draft_proposal — Generate a custom integration proposal document
4. create_sequence — Build a full 3-5 touch outreach sequence
5. track_engagement — Log and track outreach engagement metrics
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from app.agents.base import BaseAgent
from app.agents.models import AgentCapability, AgentResult, AgentTask
from app.core.logging import logger


class OutreachAgent(BaseAgent):
    """Multi-channel outreach and engagement for expansion targets."""

    def __init__(self):
        super().__init__(
            name="outreach_agent",
            description="Hyper-personalized outreach — drafts emails, LinkedIn messages, and integration proposals for expansion targets",
            version="1.0.0",
            capabilities=[
                AgentCapability(name="draft_cold_email", description="Generate personalized cold outreach email based on audit data", category="content", timeout_seconds=30),
                AgentCapability(name="draft_linkedin_message", description="Generate LinkedIn connection request and follow-up messages", category="content", timeout_seconds=30),
                AgentCapability(name="draft_proposal", description="Generate custom integration proposal for a target company", category="content", timeout_seconds=45),
                AgentCapability(name="create_sequence", description="Build a full 3-5 touch multi-channel outreach sequence", category="content", timeout_seconds=60),
                AgentCapability(name="track_engagement", description="Log outreach activity and track conversion metrics", category="data", timeout_seconds=15),
            ],
        )

        self._data_dir = Path("./data/expansion_pulse/outreach")
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._tracking_file = self._data_dir / "engagement_tracker.json"
        logger.info("OutreachAgent initialized")

    def requires_approval_for(self, instruction: str) -> bool:
        # Sending requires approval, drafting does not
        send_keywords = ["send", "post", "publish", "deliver", "execute"]
        return any(kw in instruction.lower() for kw in send_keywords)

    async def validate(self, task: AgentTask) -> bool:
        if not await super().validate(task):
            return False
        if not task.params.get("operation"):
            logger.warning(f"Task {task.task_id}: Missing operation parameter")
            return False
        return True

    async def execute(self, task: AgentTask) -> AgentResult:
        operation = task.params.get("operation", "")
        try:
            handler = {
                "draft_cold_email": self._draft_cold_email,
                "draft_linkedin_message": self._draft_linkedin_message,
                "draft_proposal": self._draft_proposal,
                "create_sequence": self._create_sequence,
                "track_engagement": self._track_engagement,
            }.get(operation)

            if not handler:
                return AgentResult(task_id=task.task_id, agent_name=self.name, success=False, error=f"Unknown operation: {operation}")

            await self.emit_progress(f"Running {operation}...")
            return await handler(task)
        except Exception as e:
            logger.error(f"Outreach operation failed: {e}")
            return AgentResult(task_id=task.task_id, agent_name=self.name, success=False, error=str(e))

    async def _draft_cold_email(self, task: AgentTask) -> AgentResult:
        """Generate personalized cold outreach email."""
        company = task.params.get("company", "")
        contact_name = task.params.get("contact_name", "")
        contact_title = task.params.get("contact_title", "")
        audit_data = task.params.get("audit_data", {})
        pain_points = task.params.get("pain_points", [])
        sender_name = task.params.get("sender_name", "Mark Meyer")

        if not company:
            return AgentResult(task_id=task.task_id, agent_name=self.name, success=False, error="Missing 'company' parameter")

        # Extract audit insights for personalization
        tech_gaps = audit_data.get("tech_audit", {}).get("missing_automation", [])
        social_gaps = audit_data.get("social_audit", {}).get("opportunities", [])
        recommended_agents = audit_data.get("recommended_cipher_agents", [])
        estimated_value = audit_data.get("estimated_monthly_value", "$1,000+")

        # Build personalized pain point if not provided
        if not pain_points and tech_gaps:
            pain_points = tech_gaps[:2]

        greeting = f"Hi {contact_name}," if contact_name else f"Hi {company} team,"

        # Build the email
        subject_lines = [
            f"Quick question about {company}'s automation strategy",
            f"I noticed something about {company}'s operations",
            f"Saving {company} 20+ hours/week with AI automation",
        ]

        pain_point_text = ""
        if pain_points:
            pain_point_text = f"I noticed {company} might be spending significant time on {pain_points[0].lower()}. "
        elif tech_gaps:
            pain_point_text = f"After looking at {company}'s online presence, I noticed some areas where automation could save your team significant time. "

        agent_pitch = ""
        if recommended_agents:
            agent_names = ", ".join(recommended_agents[:3])
            agent_pitch = f"Specifically, our {agent_names} capabilities could handle this automatically. "

        body = f"""{greeting}

{pain_point_text}{agent_pitch}

We built Elysian Protocol — a suite of 20+ specialized AI agents that plug directly into businesses like {company} to automate operations, content, customer communication, and market intelligence.

The result? Teams save 20-40 hours per week on tasks that don't need human judgment.

Would it make sense to show you a quick demo of how this would work for {company} specifically? I can have a custom integration plan ready in 24 hours.

Best,
{sender_name}
Elysian Protocol
elysianprotocol.io"""

        output = {
            "company": company,
            "contact_name": contact_name,
            "contact_title": contact_title,
            "subject_lines": subject_lines,
            "body": body,
            "personalization_data": {
                "pain_points_used": pain_points,
                "tech_gaps_referenced": tech_gaps[:3],
                "agents_pitched": recommended_agents[:3],
            },
            "status": "draft",
            "generated_at": datetime.utcnow().isoformat(),
        }

        filename = f"email_draft_{company.replace(' ', '_')[:20]}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        (self._data_dir / filename).write_text(json.dumps(output, indent=2))

        return AgentResult(task_id=task.task_id, agent_name=self.name, success=True, output=output)

    async def _draft_linkedin_message(self, task: AgentTask) -> AgentResult:
        """Generate LinkedIn connection request and follow-up messages."""
        company = task.params.get("company", "")
        contact_name = task.params.get("contact_name", "")
        contact_title = task.params.get("contact_title", "")
        audit_data = task.params.get("audit_data", {})

        if not company:
            return AgentResult(task_id=task.task_id, agent_name=self.name, success=False, error="Missing 'company'")

        composite_score = audit_data.get("composite_integration_score", 70)

        # Connection request (300 char limit)
        connection_request = f"Hi{' ' + contact_name.split()[0] if contact_name else ''}! I've been researching {company} and see major opportunities to automate operations with AI. Would love to connect and share some ideas. — Mark"

        # Follow-up message 1 (after connection accepted)
        followup_1 = f"""Thanks for connecting! I run Elysian Protocol — we build AI agent ecosystems that plug into businesses like {company}.

After analyzing your online presence, I identified {composite_score}% automation opportunity score. Our 20+ specialized agents handle everything from content creation to customer service to market intelligence.

Would a quick 15-min call make sense to explore this?"""

        # Follow-up message 2 (if no response after 5 days)
        followup_2 = f"""Hey{' ' + contact_name.split()[0] if contact_name else ''} — following up on my earlier message about {company}.

Just shipped a case study where we saved a similar-sized company 30+ hours/week. Happy to share if helpful.

No pressure either way — just thought it could be valuable."""

        output = {
            "company": company,
            "contact_name": contact_name,
            "contact_title": contact_title,
            "messages": {
                "connection_request": {"text": connection_request, "char_count": len(connection_request), "send_day": "Day 0"},
                "followup_1": {"text": followup_1, "send_day": "Day 1 (after accepted)"},
                "followup_2": {"text": followup_2, "send_day": "Day 6 (if no response)"},
            },
            "status": "draft",
            "generated_at": datetime.utcnow().isoformat(),
        }

        return AgentResult(task_id=task.task_id, agent_name=self.name, success=True, output=output)

    async def _draft_proposal(self, task: AgentTask) -> AgentResult:
        """Generate custom integration proposal."""
        company = task.params.get("company", "")
        audit_data = task.params.get("audit_data", {})
        contact_name = task.params.get("contact_name", "")

        if not company:
            return AgentResult(task_id=task.task_id, agent_name=self.name, success=False, error="Missing 'company'")

        recommended_agents = audit_data.get("recommended_cipher_agents", [
            "Communication Agent", "Research Agent", "Apex Architect",
            "Monitor Agent", "Data Agent",
        ])
        composite_score = audit_data.get("composite_integration_score", 65)
        tech_gaps = audit_data.get("tech_audit", {}).get("missing_automation", [])
        social_opps = audit_data.get("social_audit", {}).get("opportunities", [])
        estimated_value = audit_data.get("estimated_monthly_value", "$1,000+")

        # Agent descriptions for proposal
        agent_descriptions = {
            "Communication Agent": "Automated email management, customer response drafting, multi-channel messaging (email, SMS, Slack)",
            "Research Agent": "Market intelligence, competitor monitoring, trend analysis, automated report generation",
            "Apex Architect": "E-commerce optimization, social media content calendar, product listing generation, ad creative",
            "Monitor Agent": "Real-time uptime monitoring, cost tracking, alerting, performance dashboards",
            "Data Agent": "Data analysis, visualization, report generation, SQL automation, spreadsheet processing",
            "Image Agent": "AI image generation for marketing, product photos, social media graphics",
            "Video Agent": "AI video generation for ads, social content, product demos",
            "Trading Agent": "Market analysis, portfolio tracking, technical analysis (for finance-related businesses)",
            "Legal Agent": "Contract drafting, trademark search, compliance research, LLC formation docs",
            "Web Agent": "API integration, web scraping, data fetching, health checks",
        }

        agent_details = []
        for agent in recommended_agents:
            desc = agent_descriptions.get(agent, "Specialized automation capability")
            agent_details.append({"name": agent, "description": desc})

        # Build proposal document
        proposal = {
            "title": f"Elysian Protocol Integration Proposal for {company}",
            "prepared_for": contact_name or f"{company} Leadership",
            "prepared_by": "Mark Meyer, Elysian Protocol",
            "date": datetime.utcnow().strftime("%B %d, %Y"),
            "executive_summary": f"Based on our technical audit, {company} has a {composite_score}% automation opportunity score. We identified {len(tech_gaps)} technology gaps and {len(social_opps)} social/marketing opportunities that Elysian Protocol's AI agent ecosystem can address immediately.",
            "identified_gaps": tech_gaps + social_opps,
            "recommended_agents": agent_details,
            "total_agents_recommended": len(recommended_agents),
            "implementation_timeline": {
                "week_1": "Core agent deployment — Communication + Monitor + Data",
                "week_2": "Content & marketing agents — Apex Architect + Image + Video",
                "week_3": "Research & intelligence agents — Research + Web + Scout",
                "week_4": "Full integration testing + operator training",
            },
            "pricing": {
                "pro_tier": "$29/month — Up to 5 agents",
                "business_tier": "$79/month — Up to 15 agents (RECOMMENDED)",
                "enterprise_tier": "$199/month — Unlimited agents + priority support",
            },
            "estimated_roi": {
                "hours_saved_weekly": "20-40 hours",
                "estimated_monthly_value": estimated_value,
                "break_even": "Week 1",
            },
            "next_steps": [
                "15-minute demo call to showcase relevant agents",
                "Custom integration plan within 24 hours of approval",
                "Same-week deployment for core agents",
            ],
            "generated_at": datetime.utcnow().isoformat(),
        }

        filename = f"proposal_{company.replace(' ', '_')[:20]}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        (self._data_dir / filename).write_text(json.dumps(proposal, indent=2))

        return AgentResult(task_id=task.task_id, agent_name=self.name, success=True, output=proposal)

    async def _create_sequence(self, task: AgentTask) -> AgentResult:
        """Build a full multi-channel outreach sequence."""
        company = task.params.get("company", "")
        contact_name = task.params.get("contact_name", "")
        contact_email = task.params.get("contact_email", "")
        audit_data = task.params.get("audit_data", {})

        if not company:
            return AgentResult(task_id=task.task_id, agent_name=self.name, success=False, error="Missing 'company'")

        # Generate all touchpoints
        email_task = AgentTask(agent_name=self.name, instruction="draft email", params={
            "operation": "draft_cold_email", "company": company, "contact_name": contact_name, "audit_data": audit_data,
        })
        linkedin_task = AgentTask(agent_name=self.name, instruction="draft linkedin", params={
            "operation": "draft_linkedin_message", "company": company, "contact_name": contact_name, "audit_data": audit_data,
        })
        proposal_task = AgentTask(agent_name=self.name, instruction="draft proposal", params={
            "operation": "draft_proposal", "company": company, "contact_name": contact_name, "audit_data": audit_data,
        })

        email_result = await self._draft_cold_email(email_task)
        linkedin_result = await self._draft_linkedin_message(linkedin_task)
        proposal_result = await self._draft_proposal(proposal_task)

        base_date = datetime.utcnow()

        sequence = {
            "company": company,
            "contact_name": contact_name,
            "contact_email": contact_email,
            "sequence_name": f"Expansion Pulse — {company}",
            "total_touches": 5,
            "touches": [
                {
                    "touch": 1,
                    "channel": "linkedin",
                    "type": "connection_request",
                    "scheduled_date": base_date.strftime("%Y-%m-%d"),
                    "content": linkedin_result.output.get("messages", {}).get("connection_request", {}) if linkedin_result.success else {},
                    "status": "pending",
                },
                {
                    "touch": 2,
                    "channel": "email",
                    "type": "cold_email",
                    "scheduled_date": (base_date + timedelta(days=1)).strftime("%Y-%m-%d"),
                    "content": {"subject": email_result.output.get("subject_lines", [""])[0], "body": email_result.output.get("body", "")} if email_result.success else {},
                    "status": "pending",
                },
                {
                    "touch": 3,
                    "channel": "linkedin",
                    "type": "followup_message",
                    "scheduled_date": (base_date + timedelta(days=3)).strftime("%Y-%m-%d"),
                    "content": linkedin_result.output.get("messages", {}).get("followup_1", {}) if linkedin_result.success else {},
                    "status": "pending",
                },
                {
                    "touch": 4,
                    "channel": "email",
                    "type": "proposal_email",
                    "scheduled_date": (base_date + timedelta(days=7)).strftime("%Y-%m-%d"),
                    "content": {"subject": f"Integration proposal for {company}", "attachment": "proposal.json"},
                    "status": "pending",
                },
                {
                    "touch": 5,
                    "channel": "linkedin",
                    "type": "final_followup",
                    "scheduled_date": (base_date + timedelta(days=12)).strftime("%Y-%m-%d"),
                    "content": linkedin_result.output.get("messages", {}).get("followup_2", {}) if linkedin_result.success else {},
                    "status": "pending",
                },
            ],
            "proposal": proposal_result.output if proposal_result.success else None,
            "created_at": datetime.utcnow().isoformat(),
        }

        filename = f"sequence_{company.replace(' ', '_')[:20]}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        (self._data_dir / filename).write_text(json.dumps(sequence, indent=2))

        return AgentResult(task_id=task.task_id, agent_name=self.name, success=True, output=sequence)

    async def _track_engagement(self, task: AgentTask) -> AgentResult:
        """Log and track outreach engagement."""
        action = task.params.get("action", "log")  # log, report, or update
        company = task.params.get("company", "")
        event = task.params.get("event", "")  # sent, opened, replied, meeting_booked, closed

        # Load or create tracker
        tracker = {}
        if self._tracking_file.exists():
            try:
                tracker = json.loads(self._tracking_file.read_text())
            except Exception:
                tracker = {}

        if "companies" not in tracker:
            tracker["companies"] = {}
        if "metrics" not in tracker:
            tracker["metrics"] = {"total_sent": 0, "total_opened": 0, "total_replied": 0, "meetings_booked": 0, "deals_closed": 0}

        if action == "log" and company and event:
            if company not in tracker["companies"]:
                tracker["companies"][company] = {"events": [], "status": "active"}
            tracker["companies"][company]["events"].append({
                "event": event,
                "timestamp": datetime.utcnow().isoformat(),
            })
            tracker["companies"][company]["status"] = event

            # Update metrics
            metric_key = f"total_{event}" if f"total_{event}" in tracker["metrics"] else None
            if event == "meeting_booked":
                tracker["metrics"]["meetings_booked"] += 1
            elif event == "closed":
                tracker["metrics"]["deals_closed"] += 1
            elif metric_key:
                tracker["metrics"][metric_key] += 1

        # Save tracker
        self._tracking_file.write_text(json.dumps(tracker, indent=2))

        # Calculate conversion rates
        total_sent = max(1, tracker["metrics"]["total_sent"])
        conversion = {
            "open_rate": f"{(tracker['metrics']['total_opened'] / total_sent) * 100:.1f}%",
            "reply_rate": f"{(tracker['metrics']['total_replied'] / total_sent) * 100:.1f}%",
            "meeting_rate": f"{(tracker['metrics']['meetings_booked'] / total_sent) * 100:.1f}%",
            "close_rate": f"{(tracker['metrics']['deals_closed'] / total_sent) * 100:.1f}%",
        }

        output = {
            "action": action,
            "metrics": tracker["metrics"],
            "conversion_rates": conversion,
            "active_companies": len([c for c in tracker["companies"].values() if c.get("status") != "closed"]),
            "total_companies": len(tracker["companies"]),
        }

        return AgentResult(task_id=task.task_id, agent_name=self.name, success=True, output=output)

    async def verify(self, result: AgentResult) -> bool:
        if not isinstance(result.output, dict):
            return False
        if result.success and not result.output:
            return False
        return True
