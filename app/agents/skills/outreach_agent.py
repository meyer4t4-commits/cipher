"""
Outreach Agent v2.0.0 — LLM-powered multi-channel engagement for the Global Expansion Pulse.

Takes audited/ranked targets from the Analyst Agent and handles:
- LLM-generated hyper-personalized email outreach using audit data
- LLM-generated LinkedIn messages (connection request + follow-up sequence)
- LLM-generated integration proposals customized to each target's gaps
- Follow-up sequence management (3-5 touch cadence)
- Response tracking and conversion metrics

Uses LLM intelligence for content generation. Uses Communication Agent's
SMTP infrastructure for actual sending.

Capabilities:
1. draft_cold_email — Generate personalized cold outreach email via LLM
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
    """LLM-powered multi-channel outreach and engagement for expansion targets."""

    def __init__(self):
        super().__init__(
            name="outreach_agent",
            description="LLM-powered outreach — drafts personalized emails, LinkedIn messages, and integration proposals for expansion targets",
            version="2.0.0",
            capabilities=[
                AgentCapability(name="draft_cold_email", description="Generate personalized cold outreach email via LLM based on audit data", category="content", timeout_seconds=45),
                AgentCapability(name="draft_linkedin_message", description="Generate LinkedIn connection request and follow-up messages", category="content", timeout_seconds=45),
                AgentCapability(name="draft_proposal", description="Generate custom integration proposal for a target company", category="content", timeout_seconds=60),
                AgentCapability(name="create_sequence", description="Build a full 3-5 touch multi-channel outreach sequence", category="content", timeout_seconds=90),
                AgentCapability(name="track_engagement", description="Log outreach activity and track conversion metrics", category="data", timeout_seconds=15),
            ],
        )

        self._data_dir = Path("/tmp/cipher_data/expansion_pulse/outreach")
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._tracking_file = self._data_dir / "engagement_tracker.json"
        logger.info("OutreachAgent v2.0.0 initialized — LLM-powered content generation")

    def requires_approval_for(self, instruction: str) -> bool:
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

    async def _llm_generate(self, system_prompt: str, user_prompt: str, max_tokens: int = 2048) -> str:
        """Call LLM for intelligent, personalized content generation."""
        try:
            from app.services.llm_router import chat_completion
            result = await chat_completion(
                messages=[{"role": "user", "content": user_prompt}],
                system_prompt=system_prompt,
                max_tokens=max_tokens,
                temperature=0.6,
                agent_name=self.name,
            )
            if result and hasattr(result, "choices") and result.choices:
                return result.choices[0].message.content
            return str(result) if result else ""
        except Exception as e:
            logger.warning(f"LLM generation failed in outreach: {e}")
            return ""

    async def _draft_cold_email(self, task: AgentTask) -> AgentResult:
        """Generate LLM-personalized cold outreach email."""
        company = task.params.get("company", "")
        contact_name = task.params.get("contact_name", "")
        contact_title = task.params.get("contact_title", "")
        audit_data = task.params.get("audit_data", {})
        pain_points = task.params.get("pain_points", [])
        sender_name = task.params.get("sender_name", "Mark Meyer")
        tone = task.params.get("tone", "professional but conversational")

        if not company:
            return AgentResult(task_id=task.task_id, agent_name=self.name, success=False, error="Missing 'company'")

        # Extract audit context
        tech_gaps = audit_data.get("tech_audit", {}).get("missing_automation", [])
        social_gaps = audit_data.get("social_audit", {}).get("opportunities", [])
        recommended_agents = audit_data.get("recommended_cipher_agents", [])
        composite_score = audit_data.get("composite_integration_score", "")

        llm_content = await self._llm_generate(
            system_prompt=(
                f"You are a world-class B2B sales copywriter. Write a cold outreach email that is {tone}. "
                "The email must be concise (under 150 words), personalized to the company's specific gaps, "
                "and end with a clear, low-friction CTA. Do NOT use generic sales speak. "
                "Reference specific data points about the company. "
                "Output format: First line = subject line, then blank line, then email body. "
                "Generate 3 subject line variations separated by | on the first line."
            ),
            user_prompt=(
                f"Company: {company}\n"
                f"Contact: {contact_name or 'Unknown'} ({contact_title or 'Decision maker'})\n"
                f"Sender: {sender_name}, Elysian Protocol\n"
                f"Tech gaps found: {', '.join(tech_gaps) if tech_gaps else 'General automation opportunities'}\n"
                f"Social gaps: {', '.join(social_gaps[:3]) if social_gaps else 'None identified'}\n"
                f"Recommended AI agents: {', '.join(recommended_agents[:4]) if recommended_agents else 'Full suite'}\n"
                f"Integration score: {composite_score or 'High'}\n"
                f"Pain points: {', '.join(pain_points) if pain_points else 'Not specified'}\n\n"
                "Write the cold email now."
            ),
            max_tokens=1024,
        )

        if llm_content:
            lines = llm_content.strip().split("\n", 1)
            subject_line_raw = lines[0].strip()
            subject_lines = [s.strip() for s in subject_line_raw.split("|") if s.strip()]
            body = lines[1].strip() if len(lines) > 1 else llm_content
        else:
            # Template fallback
            greeting = f"Hi {contact_name}," if contact_name else f"Hi {company} team,"
            pain = f"I noticed {company} might benefit from automation in {tech_gaps[0].lower()}. " if tech_gaps else ""
            subject_lines = [f"Quick question about {company}'s automation strategy"]
            body = f"""{greeting}\n\n{pain}We built Elysian Protocol — 20+ specialized AI agents that plug directly into businesses like {company}.\n\nWould a quick demo make sense?\n\nBest,\n{sender_name}\nElysian Protocol"""

        output = {
            "company": company,
            "contact_name": contact_name,
            "contact_title": contact_title,
            "subject_lines": subject_lines[:3],
            "body": body,
            "personalization_data": {
                "pain_points_used": pain_points or tech_gaps[:2],
                "tech_gaps_referenced": tech_gaps[:3],
                "agents_pitched": recommended_agents[:3],
            },
            "llm_generated": bool(llm_content),
            "status": "draft",
            "generated_at": datetime.utcnow().isoformat(),
        }

        filename = f"email_draft_{company.replace(' ', '_')[:20]}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        (self._data_dir / filename).write_text(json.dumps(output, indent=2))

        return AgentResult(task_id=task.task_id, agent_name=self.name, success=True, output=output)

    async def _draft_linkedin_message(self, task: AgentTask) -> AgentResult:
        """Generate LLM-powered LinkedIn messages."""
        company = task.params.get("company", "")
        contact_name = task.params.get("contact_name", "")
        contact_title = task.params.get("contact_title", "")
        audit_data = task.params.get("audit_data", {})

        if not company:
            return AgentResult(task_id=task.task_id, agent_name=self.name, success=False, error="Missing 'company'")

        composite_score = audit_data.get("composite_integration_score", 70)
        tech_gaps = audit_data.get("tech_audit", {}).get("missing_automation", [])

        llm_content = await self._llm_generate(
            system_prompt=(
                "You are a LinkedIn outreach expert. Generate 3 messages for a B2B outreach sequence:\n"
                "1. Connection request (MUST be under 280 characters)\n"
                "2. Follow-up after connection accepted (2-3 short paragraphs)\n"
                "3. Final follow-up if no response after 5 days (casual, short)\n\n"
                "Output format:\n"
                "---CONNECTION---\n[message]\n---FOLLOWUP1---\n[message]\n---FOLLOWUP2---\n[message]\n"
                "Be genuine, not salesy. Reference specific company data."
            ),
            user_prompt=(
                f"Company: {company}\n"
                f"Contact: {contact_name or 'Unknown'} ({contact_title or 'Decision maker'})\n"
                f"Integration score: {composite_score}%\n"
                f"Tech gaps: {', '.join(tech_gaps[:3]) if tech_gaps else 'General automation'}\n"
                f"Sender: Mark Meyer, Elysian Protocol (AI automation platform)\n\n"
                "Write the 3 LinkedIn messages."
            ),
            max_tokens=1024,
        )

        if llm_content:
            # Parse structured output
            parts = {"connection": "", "followup_1": "", "followup_2": ""}
            if "---CONNECTION---" in llm_content:
                sections = llm_content.split("---")
                for i, section in enumerate(sections):
                    s = section.strip()
                    if s == "CONNECTION" and i + 1 < len(sections):
                        parts["connection"] = sections[i + 1].strip()
                    elif s == "FOLLOWUP1" and i + 1 < len(sections):
                        parts["followup_1"] = sections[i + 1].strip()
                    elif s == "FOLLOWUP2" and i + 1 < len(sections):
                        parts["followup_2"] = sections[i + 1].strip()
            else:
                # LLM didn't follow format — split by double newlines
                chunks = [c.strip() for c in llm_content.split("\n\n") if c.strip()]
                if len(chunks) >= 3:
                    parts["connection"] = chunks[0]
                    parts["followup_1"] = "\n\n".join(chunks[1:3])
                    parts["followup_2"] = chunks[-1] if len(chunks) > 3 else chunks[2]
                elif chunks:
                    parts["connection"] = chunks[0][:280]
        else:
            # Template fallback
            first_name = contact_name.split()[0] if contact_name else ""
            parts = {
                "connection": f"Hi{' ' + first_name if first_name else ''}! Researching {company} and see major AI automation opportunities. Would love to connect. — Mark",
                "followup_1": f"Thanks for connecting! I run Elysian Protocol — 20+ AI agents for businesses like {company}. Found a {composite_score}% automation opportunity. Quick 15-min call?",
                "followup_2": f"Hey{' ' + first_name if first_name else ''} — following up. Just shipped a case study saving 30+ hrs/week for a similar company. Happy to share.",
            }

        output = {
            "company": company,
            "contact_name": contact_name,
            "contact_title": contact_title,
            "messages": {
                "connection_request": {"text": parts["connection"][:300], "char_count": len(parts["connection"][:300]), "send_day": "Day 0"},
                "followup_1": {"text": parts["followup_1"], "send_day": "Day 1 (after accepted)"},
                "followup_2": {"text": parts["followup_2"], "send_day": "Day 6 (if no response)"},
            },
            "llm_generated": bool(llm_content),
            "status": "draft",
            "generated_at": datetime.utcnow().isoformat(),
        }

        return AgentResult(task_id=task.task_id, agent_name=self.name, success=True, output=output)

    async def _draft_proposal(self, task: AgentTask) -> AgentResult:
        """Generate LLM-powered custom integration proposal."""
        company = task.params.get("company", "")
        audit_data = task.params.get("audit_data", {})
        contact_name = task.params.get("contact_name", "")

        if not company:
            return AgentResult(task_id=task.task_id, agent_name=self.name, success=False, error="Missing 'company'")

        recommended_agents = audit_data.get("recommended_cipher_agents", [])
        composite_score = audit_data.get("composite_integration_score", 65)
        tech_gaps = audit_data.get("tech_audit", {}).get("missing_automation", [])
        social_opps = audit_data.get("social_audit", {}).get("opportunities", [])
        estimated_value = audit_data.get("estimated_monthly_value", "$1,000+")

        llm_content = await self._llm_generate(
            system_prompt=(
                "You are a business proposal writer for Elysian Protocol, an AI automation platform "
                "with 20+ specialized agents. Generate a professional integration proposal in markdown. "
                "Include: Executive Summary, Identified Gaps, Recommended Solution (specific agents), "
                "Implementation Timeline (4 weeks), Pricing (Pro $29/mo, Business $79/mo recommended, "
                "Enterprise $199/mo), Expected ROI, and Next Steps. Be specific to the company's actual gaps."
            ),
            user_prompt=(
                f"Company: {company}\n"
                f"Prepared for: {contact_name or f'{company} Leadership'}\n"
                f"Integration score: {composite_score}%\n"
                f"Tech gaps: {json.dumps(tech_gaps)}\n"
                f"Social opportunities: {json.dumps(social_opps[:3])}\n"
                f"Recommended agents: {json.dumps(recommended_agents)}\n"
                f"Estimated monthly value: {estimated_value}\n\n"
                "Write the full proposal."
            ),
            max_tokens=3000,
        )

        proposal = {
            "title": f"Elysian Protocol Integration Proposal for {company}",
            "prepared_for": contact_name or f"{company} Leadership",
            "prepared_by": "Mark Meyer, Elysian Protocol",
            "date": datetime.utcnow().strftime("%B %d, %Y"),
            "composite_score": composite_score,
            "recommended_agents": recommended_agents,
            "estimated_monthly_value": estimated_value,
            "generated_at": datetime.utcnow().isoformat(),
        }

        if llm_content:
            proposal["content_markdown"] = llm_content
            # Save as markdown file
            md_filename = f"proposal_{company.replace(' ', '_')[:20]}_{datetime.utcnow().strftime('%Y%m%d')}.md"
            md_path = self._data_dir / md_filename
            md_path.write_text(llm_content, encoding="utf-8")
            proposal["file_path"] = str(md_path)
            proposal["llm_generated"] = True
        else:
            # Template fallback
            proposal["executive_summary"] = f"Based on our audit, {company} has a {composite_score}% automation opportunity score with {len(tech_gaps)} technology gaps."
            proposal["identified_gaps"] = tech_gaps + social_opps
            proposal["implementation_timeline"] = {
                "week_1": "Core agent deployment",
                "week_2": "Content & marketing agents",
                "week_3": "Research & intelligence agents",
                "week_4": "Full integration testing + training",
            }
            proposal["pricing"] = {
                "pro_tier": "$29/month — Up to 5 agents",
                "business_tier": "$79/month — Up to 15 agents (RECOMMENDED)",
                "enterprise_tier": "$199/month — Unlimited agents + priority support",
            }
            proposal["llm_generated"] = False

        filename = f"proposal_{company.replace(' ', '_')[:20]}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        (self._data_dir / filename).write_text(json.dumps(proposal, indent=2))

        return AgentResult(task_id=task.task_id, agent_name=self.name, success=True, output=proposal)

    async def _create_sequence(self, task: AgentTask) -> AgentResult:
        """Build a full multi-channel outreach sequence using LLM for each touch."""
        company = task.params.get("company", "")
        contact_name = task.params.get("contact_name", "")
        contact_email = task.params.get("contact_email", "")
        audit_data = task.params.get("audit_data", {})

        if not company:
            return AgentResult(task_id=task.task_id, agent_name=self.name, success=False, error="Missing 'company'")

        await self.emit_progress("Generating email draft...")
        email_task = AgentTask(agent_name=self.name, instruction="draft email", params={
            "operation": "draft_cold_email", "company": company, "contact_name": contact_name, "audit_data": audit_data,
        })
        email_result = await self._draft_cold_email(email_task)

        await self.emit_progress("Generating LinkedIn messages...")
        linkedin_task = AgentTask(agent_name=self.name, instruction="draft linkedin", params={
            "operation": "draft_linkedin_message", "company": company, "contact_name": contact_name, "audit_data": audit_data,
        })
        linkedin_result = await self._draft_linkedin_message(linkedin_task)

        await self.emit_progress("Generating proposal...")
        proposal_task = AgentTask(agent_name=self.name, instruction="draft proposal", params={
            "operation": "draft_proposal", "company": company, "contact_name": contact_name, "audit_data": audit_data,
        })
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
                    "touch": 1, "channel": "linkedin", "type": "connection_request",
                    "scheduled_date": base_date.strftime("%Y-%m-%d"),
                    "content": linkedin_result.output.get("messages", {}).get("connection_request", {}) if linkedin_result.success else {},
                    "status": "pending",
                },
                {
                    "touch": 2, "channel": "email", "type": "cold_email",
                    "scheduled_date": (base_date + timedelta(days=1)).strftime("%Y-%m-%d"),
                    "content": {"subject": email_result.output.get("subject_lines", [""])[0], "body": email_result.output.get("body", "")} if email_result.success else {},
                    "status": "pending",
                },
                {
                    "touch": 3, "channel": "linkedin", "type": "followup_message",
                    "scheduled_date": (base_date + timedelta(days=3)).strftime("%Y-%m-%d"),
                    "content": linkedin_result.output.get("messages", {}).get("followup_1", {}) if linkedin_result.success else {},
                    "status": "pending",
                },
                {
                    "touch": 4, "channel": "email", "type": "proposal_email",
                    "scheduled_date": (base_date + timedelta(days=7)).strftime("%Y-%m-%d"),
                    "content": {"subject": f"Integration proposal for {company}", "has_proposal": bool(proposal_result.success)},
                    "status": "pending",
                },
                {
                    "touch": 5, "channel": "linkedin", "type": "final_followup",
                    "scheduled_date": (base_date + timedelta(days=12)).strftime("%Y-%m-%d"),
                    "content": linkedin_result.output.get("messages", {}).get("followup_2", {}) if linkedin_result.success else {},
                    "status": "pending",
                },
            ],
            "proposal": proposal_result.output if proposal_result.success else None,
            "all_llm_generated": all([
                email_result.success and email_result.output.get("llm_generated"),
                linkedin_result.success and linkedin_result.output.get("llm_generated"),
                proposal_result.success and proposal_result.output.get("llm_generated"),
            ]),
            "created_at": datetime.utcnow().isoformat(),
        }

        filename = f"sequence_{company.replace(' ', '_')[:20]}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        (self._data_dir / filename).write_text(json.dumps(sequence, indent=2))

        return AgentResult(task_id=task.task_id, agent_name=self.name, success=True, output=sequence)

    async def _track_engagement(self, task: AgentTask) -> AgentResult:
        """Log and track outreach engagement."""
        action = task.params.get("action", "log")
        company = task.params.get("company", "")
        event = task.params.get("event", "")

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

            if event == "meeting_booked":
                tracker["metrics"]["meetings_booked"] += 1
            elif event == "closed":
                tracker["metrics"]["deals_closed"] += 1
            elif f"total_{event}" in tracker["metrics"]:
                tracker["metrics"][f"total_{event}"] += 1

        self._tracking_file.write_text(json.dumps(tracker, indent=2))

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
