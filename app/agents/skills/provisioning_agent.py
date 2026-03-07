"""
Provisioning Agent — Client onboarding automation for the Global Expansion Pulse.

When a target says "Yes", this agent automatically prepares their integration:
- Generates client configuration files
- Creates onboarding documentation
- Builds custom agent activation plans
- Prepares API access and environment setup
- Generates training materials for the client's team

Capabilities:
1. provision_client — Full client provisioning (config + docs + activation plan)
2. generate_config — Generate client-specific configuration files
3. generate_onboarding — Create onboarding documentation and guides
4. generate_activation_plan — Build step-by-step agent activation plan
5. generate_training — Create training materials for client team
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from app.agents.base import BaseAgent
from app.agents.models import AgentCapability, AgentResult, AgentTask
from app.core.logging import logger


class ProvisioningAgent(BaseAgent):
    """Client onboarding and integration environment preparation."""

    def __init__(self):
        super().__init__(
            name="provisioning_agent",
            description="Client provisioning — auto-prepares integration environments, configs, onboarding docs, and training for new clients",
            version="1.0.0",
            capabilities=[
                AgentCapability(name="provision_client", description="Full client provisioning — config, docs, activation plan, training", category="execution", timeout_seconds=90),
                AgentCapability(name="generate_config", description="Generate client-specific daemon configuration", category="execution", timeout_seconds=30),
                AgentCapability(name="generate_onboarding", description="Create onboarding documentation and quick-start guide", category="content", timeout_seconds=45),
                AgentCapability(name="generate_activation_plan", description="Build step-by-step agent activation plan based on audit data", category="content", timeout_seconds=30),
                AgentCapability(name="generate_training", description="Create training materials for client team", category="content", timeout_seconds=45),
            ],
        )

        self._data_dir = Path("./data/expansion_pulse/provisioning")
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._clients_dir = Path("./data/clients")
        self._clients_dir.mkdir(parents=True, exist_ok=True)
        logger.info("ProvisioningAgent initialized")

    def requires_approval_for(self, instruction: str) -> bool:
        # Provisioning creates configs — always needs approval
        return True

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
                "provision_client": self._provision_client,
                "generate_config": self._generate_config,
                "generate_onboarding": self._generate_onboarding,
                "generate_activation_plan": self._generate_activation_plan,
                "generate_training": self._generate_training,
            }.get(operation)

            if not handler:
                return AgentResult(task_id=task.task_id, agent_name=self.name, success=False, error=f"Unknown operation: {operation}")

            await self.emit_progress(f"Running {operation}...")
            return await handler(task)
        except Exception as e:
            logger.error(f"Provisioning operation failed: {e}")
            return AgentResult(task_id=task.task_id, agent_name=self.name, success=False, error=str(e))

    async def _provision_client(self, task: AgentTask) -> AgentResult:
        """Full client provisioning — runs all sub-tasks."""
        company = task.params.get("company", "")
        tier = task.params.get("tier", "business")
        audit_data = task.params.get("audit_data", {})
        contact_name = task.params.get("contact_name", "")
        contact_email = task.params.get("contact_email", "")

        if not company:
            return AgentResult(task_id=task.task_id, agent_name=self.name, success=False, error="Missing 'company'")

        # Generate client ID
        client_id = f"ep-{company.lower().replace(' ', '-')[:20]}-{uuid4().hex[:6]}"
        client_dir = self._clients_dir / client_id
        client_dir.mkdir(parents=True, exist_ok=True)

        # Run all provisioning sub-tasks
        config_task = AgentTask(agent_name=self.name, instruction="config", params={
            "operation": "generate_config", "company": company, "client_id": client_id,
            "tier": tier, "audit_data": audit_data,
        })
        onboarding_task = AgentTask(agent_name=self.name, instruction="onboarding", params={
            "operation": "generate_onboarding", "company": company, "client_id": client_id,
            "contact_name": contact_name, "tier": tier,
        })
        activation_task = AgentTask(agent_name=self.name, instruction="activation", params={
            "operation": "generate_activation_plan", "company": company, "client_id": client_id,
            "audit_data": audit_data, "tier": tier,
        })
        training_task = AgentTask(agent_name=self.name, instruction="training", params={
            "operation": "generate_training", "company": company, "client_id": client_id, "tier": tier,
        })

        config_result = await self._generate_config(config_task)
        onboarding_result = await self._generate_onboarding(onboarding_task)
        activation_result = await self._generate_activation_plan(activation_task)
        training_result = await self._generate_training(training_task)

        # Master provisioning record
        provision_record = {
            "client_id": client_id,
            "company": company,
            "contact_name": contact_name,
            "contact_email": contact_email,
            "tier": tier,
            "provisioned_at": datetime.utcnow().isoformat(),
            "status": "provisioned",
            "config": config_result.output if config_result.success else {"error": config_result.error},
            "onboarding": onboarding_result.output if onboarding_result.success else {"error": onboarding_result.error},
            "activation_plan": activation_result.output if activation_result.success else {"error": activation_result.error},
            "training": training_result.output if training_result.success else {"error": training_result.error},
            "next_steps": [
                f"Send onboarding email to {contact_email or contact_name}",
                "Schedule kickoff call within 48 hours",
                "Begin Week 1 agent deployment per activation plan",
                "Set up monitoring dashboard for client",
            ],
        }

        # Save to client directory and provisioning log
        (client_dir / "provision_record.json").write_text(json.dumps(provision_record, indent=2))
        filename = f"provision_{client_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        (self._data_dir / filename).write_text(json.dumps(provision_record, indent=2))

        return AgentResult(task_id=task.task_id, agent_name=self.name, success=True, output=provision_record)

    async def _generate_config(self, task: AgentTask) -> AgentResult:
        """Generate client-specific daemon configuration."""
        company = task.params.get("company", "")
        client_id = task.params.get("client_id", f"ep-{uuid4().hex[:8]}")
        tier = task.params.get("tier", "business")
        audit_data = task.params.get("audit_data", {})

        recommended_agents = audit_data.get("recommended_cipher_agents", [])

        # Tier-based agent limits
        tier_limits = {"free": 3, "pro": 5, "business": 15, "enterprise": 50}
        max_agents = tier_limits.get(tier, 15)

        # Build agent activation list
        all_agents = [
            "shell_agent", "web_agent", "code_agent", "file_agent",
            "research_agent", "communication_agent", "data_agent",
            "monitor_agent", "image_agent", "video_agent",
            "apex_architect_agent", "legal_agent", "trading_agent",
            "scout_agent", "analyst_agent", "outreach_agent",
        ]

        # Prioritize recommended agents, fill with defaults
        active_agents = []
        for agent in recommended_agents:
            agent_id = agent.lower().replace(" ", "_")
            if not agent_id.endswith("_agent"):
                agent_id += "_agent"
            if agent_id in all_agents:
                active_agents.append(agent_id)

        # Fill remaining slots
        for agent in all_agents:
            if agent not in active_agents and len(active_agents) < max_agents:
                active_agents.append(agent)

        config = {
            "client_id": client_id,
            "company": company,
            "tier": tier,
            "daemon_name": f"cipher-{company.lower().replace(' ', '-')[:15]}",
            "max_agents": max_agents,
            "active_agents": active_agents[:max_agents],
            "model_routing": {
                "default_model": "anthropic/claude-sonnet-4-20250514" if tier in ["business", "enterprise"] else "dashscope/qwen3.5-27b",
                "fast_model": "groq/llama-3.3-70b-versatile",
                "budget_model": "dashscope/qwen3.5-27b",
                "cascade_enabled": True,
            },
            "rate_limits": {
                "free": {"requests_per_hour": 50, "max_tokens_per_day": 100000},
                "pro": {"requests_per_hour": 200, "max_tokens_per_day": 500000},
                "business": {"requests_per_hour": 1000, "max_tokens_per_day": 2000000},
                "enterprise": {"requests_per_hour": 5000, "max_tokens_per_day": 10000000},
            }.get(tier, {}),
            "features": {
                "voice_enabled": tier in ["business", "enterprise"],
                "streaming": True,
                "memory": True,
                "agent_spawning": tier in ["business", "enterprise"],
                "cron_jobs": tier in ["pro", "business", "enterprise"],
                "custom_agents": tier == "enterprise",
            },
            "generated_at": datetime.utcnow().isoformat(),
        }

        return AgentResult(task_id=task.task_id, agent_name=self.name, success=True, output=config)

    async def _generate_onboarding(self, task: AgentTask) -> AgentResult:
        """Create onboarding documentation."""
        company = task.params.get("company", "")
        client_id = task.params.get("client_id", "")
        contact_name = task.params.get("contact_name", "")
        tier = task.params.get("tier", "business")

        greeting = f"Welcome {contact_name}!" if contact_name else f"Welcome, {company} team!"

        onboarding = {
            "title": f"Elysian Protocol — Onboarding Guide for {company}",
            "client_id": client_id,
            "greeting": greeting,
            "quick_start": {
                "step_1": "Access your daemon dashboard at https://elysianprotocol.io/dashboard",
                "step_2": "Your daemon is pre-configured with agents tailored to your needs",
                "step_3": "Start a conversation — just type naturally, Cipher understands intent",
                "step_4": "Try: 'Research my competitors' or 'Draft a social media post'",
            },
            "key_commands": {
                "research": "'Research [topic]' — triggers Research Agent",
                "content": "'Create a content calendar' — triggers Apex Architect",
                "email": "'Draft an email to [contact]' — triggers Communication Agent",
                "monitor": "'Monitor [url]' — triggers Monitor Agent",
                "analyze": "'Analyze this data' — triggers Data Agent",
            },
            "support": {
                "email": "support@elysianprotocol.io",
                "response_time": "Within 24 hours",
                "documentation": "https://docs.elysianprotocol.io",
            },
            "tier": tier,
            "generated_at": datetime.utcnow().isoformat(),
        }

        return AgentResult(task_id=task.task_id, agent_name=self.name, success=True, output=onboarding)

    async def _generate_activation_plan(self, task: AgentTask) -> AgentResult:
        """Build step-by-step agent activation plan."""
        company = task.params.get("company", "")
        audit_data = task.params.get("audit_data", {})
        tier = task.params.get("tier", "business")

        recommended_agents = audit_data.get("recommended_cipher_agents", [
            "Communication Agent", "Research Agent", "Apex Architect",
            "Monitor Agent", "Data Agent",
        ])

        # Build phased activation
        phases = []
        base_date = datetime.utcnow()

        # Phase 1: Core (Week 1)
        phase_1_agents = [a for a in recommended_agents if a in ["Communication Agent", "Monitor Agent", "Data Agent", "Web Agent"]]
        if not phase_1_agents:
            phase_1_agents = recommended_agents[:2]
        phases.append({
            "phase": 1,
            "name": "Core Infrastructure",
            "timeline": f"{base_date.strftime('%b %d')} — {(base_date + timedelta(days=7)).strftime('%b %d')}",
            "agents": phase_1_agents,
            "objectives": ["Establish monitoring and alerting", "Connect communication channels", "Set up data pipelines"],
            "success_criteria": "All core agents responding to commands within 24 hours",
        })

        # Phase 2: Growth (Week 2)
        phase_2_agents = [a for a in recommended_agents if a in ["Apex Architect", "Image Agent", "Video Agent", "Research Agent"]]
        if not phase_2_agents:
            phase_2_agents = recommended_agents[2:4]
        phases.append({
            "phase": 2,
            "name": "Content & Marketing",
            "timeline": f"{(base_date + timedelta(days=7)).strftime('%b %d')} — {(base_date + timedelta(days=14)).strftime('%b %d')}",
            "agents": phase_2_agents,
            "objectives": ["Launch content calendar", "Set up social media automation", "Begin competitor monitoring"],
            "success_criteria": "First automated content published, research reports generating",
        })

        # Phase 3: Intelligence (Week 3-4)
        remaining = [a for a in recommended_agents if a not in phase_1_agents and a not in phase_2_agents]
        phases.append({
            "phase": 3,
            "name": "Full Intelligence Suite",
            "timeline": f"{(base_date + timedelta(days=14)).strftime('%b %d')} — {(base_date + timedelta(days=28)).strftime('%b %d')}",
            "agents": remaining or ["All remaining agents"],
            "objectives": ["Full agent ecosystem active", "Cron jobs configured", "Operator trained on all capabilities"],
            "success_criteria": "20+ hours/week saved, all agents operational",
        })

        plan = {
            "company": company,
            "tier": tier,
            "total_agents": len(recommended_agents),
            "total_phases": len(phases),
            "total_timeline": "4 weeks",
            "phases": phases,
            "kpis": {
                "hours_saved_target": "20-40/week by Week 4",
                "agent_utilization": "80%+ of activated agents used weekly",
                "satisfaction": "NPS 8+ at 30-day review",
            },
            "generated_at": datetime.utcnow().isoformat(),
        }

        return AgentResult(task_id=task.task_id, agent_name=self.name, success=True, output=plan)

    async def _generate_training(self, task: AgentTask) -> AgentResult:
        """Create training materials."""
        company = task.params.get("company", "")
        tier = task.params.get("tier", "business")

        training = {
            "title": f"Cipher Training Guide — {company}",
            "modules": [
                {
                    "module": 1,
                    "title": "Getting Started with Cipher",
                    "duration": "15 minutes",
                    "topics": [
                        "What is a daemon vs a chatbot",
                        "Natural language commands — just talk normally",
                        "Understanding agent routing — how Cipher picks the right hand",
                        "Your first 5 commands to try",
                    ],
                },
                {
                    "module": 2,
                    "title": "Power User Commands",
                    "duration": "20 minutes",
                    "topics": [
                        "Chaining commands for complex workflows",
                        "Using memory — Cipher remembers everything",
                        "Scheduling recurring tasks (cron jobs)",
                        "Agent spawning for parallel work",
                    ],
                },
                {
                    "module": 3,
                    "title": "Agent Deep Dives",
                    "duration": "30 minutes",
                    "topics": [
                        "Research Agent — market intelligence on autopilot",
                        "Apex Architect — content and marketing automation",
                        "Communication Agent — email and messaging at scale",
                        "Monitor Agent — never miss an outage or anomaly",
                    ],
                },
                {
                    "module": 4,
                    "title": "Advanced Workflows",
                    "duration": "20 minutes",
                    "topics": [
                        "Building custom cron jobs for your business",
                        "Integrating with existing tools (API endpoints)",
                        "Training Cipher on your business context",
                        "Feedback loops — making Cipher smarter over time",
                    ],
                },
            ],
            "total_duration": "~85 minutes",
            "delivery": "Self-paced documentation + optional 30-min live session",
            "generated_at": datetime.utcnow().isoformat(),
        }

        return AgentResult(task_id=task.task_id, agent_name=self.name, success=True, output=training)

    async def verify(self, result: AgentResult) -> bool:
        if not isinstance(result.output, dict):
            return False
        if result.success and not result.output:
            return False
        return True
