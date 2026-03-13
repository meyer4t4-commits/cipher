"""
Provisioning Agent v3.0.0 — Agentic client onboarding + Shopify API + business automation.

Truly agentic: uses LLM to generate custom content, creates real documents,
connects to Shopify Admin API to read/modify stores, and executes multi-step workflows.

Capabilities:
1. provision_client — Full client provisioning (config + docs + activation plan)
2. generate_config — Generate client-specific configuration files
3. generate_onboarding — Create onboarding documentation and guides
4. generate_activation_plan — Build step-by-step agent activation plan
5. generate_training — Create training materials for client team
6. create_document — Generate real business documents (proposals, SOWs, contracts)
7. shopify_audit — Audit a Shopify store and generate improvement plan
8. llc_formation — Generate LLC formation documents and filing checklist
9. patent_draft — Draft provisional patent application outline
10. shopify_read — Read products, pages, blogs, metafields from a Shopify store
11. shopify_update — Update products, descriptions, SEO, pages on a Shopify store
12. shopify_fix — Full auto-fix: analyze + fix products, SEO, pages, navigation
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

import httpx

from app.agents.base import BaseAgent
from app.agents.models import AgentCapability, AgentResult, AgentTask
from app.core.logging import logger


class ProvisioningAgent(BaseAgent):
    """Agentic client onboarding, document generation, and business automation."""

    def __init__(self):
        super().__init__(
            name="provisioning_agent",
            description=(
                "Agentic provisioning — client onboarding, business document generation "
                "(LLC, patents, proposals, SOWs), Shopify store audits, and training materials. "
                "Uses LLM intelligence for customized outputs."
            ),
            version="3.0.0",
            capabilities=[
                AgentCapability(name="provision_client", description="Full client provisioning — config, docs, activation plan, training", category="execution", timeout_seconds=120),
                AgentCapability(name="generate_config", description="Generate client-specific daemon configuration", category="execution", timeout_seconds=30),
                AgentCapability(name="generate_onboarding", description="Create onboarding documentation and quick-start guide", category="content", timeout_seconds=60),
                AgentCapability(name="generate_activation_plan", description="Build step-by-step agent activation plan based on audit data", category="content", timeout_seconds=60),
                AgentCapability(name="generate_training", description="Create training materials for client team", category="content", timeout_seconds=60),
                AgentCapability(name="create_document", description="Generate business documents — proposals, SOWs, contracts, briefs", category="content", timeout_seconds=90),
                AgentCapability(name="shopify_audit", description="Audit Shopify store and generate optimization plan", category="analysis", timeout_seconds=120),
                AgentCapability(name="llc_formation", description="Generate LLC formation documents and state-specific filing checklist", category="content", timeout_seconds=90),
                AgentCapability(name="patent_draft", description="Draft provisional patent application outline with claims", category="content", timeout_seconds=120),
                AgentCapability(name="shopify_read", description="Read products, pages, blogs, metafields, themes from a Shopify store via Admin API", category="data", timeout_seconds=30),
                AgentCapability(name="shopify_update", description="Update products, descriptions, SEO meta, pages, navigation on a Shopify store", category="execution", timeout_seconds=60),
                AgentCapability(name="shopify_fix", description="Full auto-fix: analyze store, fix SEO, product descriptions, pages, navigation", category="execution", timeout_seconds=180),
            ],
        )

        self._data_dir = Path("./data/expansion_pulse/provisioning")
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._clients_dir = Path("./data/clients")
        self._clients_dir.mkdir(parents=True, exist_ok=True)
        self._docs_dir = Path("./data/documents")
        self._docs_dir.mkdir(parents=True, exist_ok=True)

        # Shopify API config
        self.shopify_store = os.getenv("SHOPIFY_STORE", "")  # e.g. "tallowroots" (without .myshopify.com)
        self.shopify_token = os.getenv("SHOPIFY_ACCESS_TOKEN", "")
        self.shopify_api_version = os.getenv("SHOPIFY_API_VERSION", "2024-01")

        logger.info(f"ProvisioningAgent v3.0.0 initialized — Shopify API {'configured' if self.shopify_token else 'NOT configured'}")

    def requires_approval_for(self, instruction: str) -> bool:
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
                "create_document": self._create_document,
                "shopify_audit": self._shopify_audit,
                "llc_formation": self._llc_formation,
                "patent_draft": self._patent_draft,
                "shopify_read": self._shopify_read,
                "shopify_update": self._shopify_update,
                "shopify_fix": self._shopify_fix,
            }.get(operation)

            if not handler:
                return AgentResult(
                    task_id=task.task_id, agent_name=self.name, success=False,
                    error=f"Unknown operation: {operation}. Available: {list(self.capabilities_map().keys())}",
                )

            await self.emit_progress(f"Running {operation}...")
            return await handler(task)
        except Exception as e:
            logger.error(f"Provisioning operation failed: {e}")
            return AgentResult(task_id=task.task_id, agent_name=self.name, success=False, error=str(e))

    # ─────────────────────────────────────────────────────────
    # LLM helper — generates intelligent content
    # ─────────────────────────────────────────────────────────
    async def _llm_generate(self, system_prompt: str, user_prompt: str, max_tokens: int = 4096) -> str:
        """Call LLM to generate intelligent, customized content."""
        try:
            from app.services.llm_router import chat_completion

            result = await chat_completion(
                messages=[{"role": "user", "content": user_prompt}],
                system_prompt=system_prompt,
                max_tokens=max_tokens,
                temperature=0.4,
                agent_name=self.name,
            )
            if result and hasattr(result, "choices") and result.choices:
                return result.choices[0].message.content
            return str(result) if result else ""
        except Exception as e:
            logger.warning(f"LLM generation failed, using template fallback: {e}")
            return ""

    # ─────────────────────────────────────────────────────────
    # Web research helper — fetches real data for audits
    # ─────────────────────────────────────────────────────────
    async def _web_search(self, query: str) -> list[dict]:
        """Search the web for real data to inform outputs."""
        try:
            from app.core.config import settings
            import httpx

            # Try Brave Search first
            if settings.brave_api_key:
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.get(
                        "https://api.search.brave.com/res/v1/web/search",
                        headers={"X-Subscription-Token": settings.brave_api_key, "Accept": "application/json"},
                        params={"q": query, "count": 5},
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        results = []
                        for r in data.get("web", {}).get("results", [])[:5]:
                            results.append({
                                "title": r.get("title", ""),
                                "url": r.get("url", ""),
                                "description": r.get("description", ""),
                            })
                        return results

            # Fallback to DuckDuckGo
            import httpx
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "https://api.duckduckgo.com/",
                    params={"q": query, "format": "json", "no_redirect": "1"},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    results = []
                    for r in data.get("RelatedTopics", [])[:5]:
                        if isinstance(r, dict) and "Text" in r:
                            results.append({
                                "title": r.get("Text", "")[:100],
                                "url": r.get("FirstURL", ""),
                                "description": r.get("Text", ""),
                            })
                    return results
        except Exception as e:
            logger.warning(f"Web search failed: {e}")
        return []

    def _save_document(self, filename: str, content: str, subfolder: str = "") -> Path:
        """Save a generated document to disk."""
        target_dir = self._docs_dir / subfolder if subfolder else self._docs_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        filepath = target_dir / filename
        filepath.write_text(content, encoding="utf-8")
        return filepath

    # ═══════════════════════════════════════════════════════════════
    # CLIENT PROVISIONING (existing, improved with LLM)
    # ═══════════════════════════════════════════════════════════════

    async def _provision_client(self, task: AgentTask) -> AgentResult:
        """Full client provisioning — runs all sub-tasks with LLM intelligence."""
        company = task.params.get("company", "")
        tier = task.params.get("tier", "business")
        audit_data = task.params.get("audit_data", {})
        contact_name = task.params.get("contact_name", "")
        contact_email = task.params.get("contact_email", "")

        if not company:
            return AgentResult(task_id=task.task_id, agent_name=self.name, success=False, error="Missing 'company'")

        client_id = f"ep-{company.lower().replace(' ', '-')[:20]}-{uuid4().hex[:6]}"
        client_dir = self._clients_dir / client_id
        client_dir.mkdir(parents=True, exist_ok=True)

        await self.emit_progress(f"Provisioning {company} — generating config...")

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
        await self.emit_progress("Config done — generating onboarding docs...")
        onboarding_result = await self._generate_onboarding(onboarding_task)
        await self.emit_progress("Onboarding done — building activation plan...")
        activation_result = await self._generate_activation_plan(activation_task)
        await self.emit_progress("Activation plan done — creating training materials...")
        training_result = await self._generate_training(training_task)

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

        tier_limits = {"free": 3, "pro": 5, "business": 15, "enterprise": 50}
        max_agents = tier_limits.get(tier, 15)

        all_agents = [
            "shell_agent", "web_agent", "code_agent", "file_agent",
            "research_agent", "communication_agent", "data_agent",
            "monitor_agent", "image_agent", "video_agent",
            "apex_architect_agent", "legal_agent", "trading_agent",
            "scout_agent", "analyst_agent", "outreach_agent",
        ]

        active_agents = []
        for agent in recommended_agents:
            agent_id = agent.lower().replace(" ", "_")
            if not agent_id.endswith("_agent"):
                agent_id += "_agent"
            if agent_id in all_agents:
                active_agents.append(agent_id)

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
                "default_model": "anthropic/claude-sonnet-4-20250514" if tier in ["business", "enterprise"] else "groq/llama-3.3-70b-versatile",
                "fast_model": "groq/llama-3.3-70b-versatile",
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
        """Create LLM-powered onboarding documentation."""
        company = task.params.get("company", "")
        client_id = task.params.get("client_id", "")
        contact_name = task.params.get("contact_name", "")
        tier = task.params.get("tier", "business")

        # Use LLM to generate customized onboarding guide
        llm_content = await self._llm_generate(
            system_prompt=(
                "You are Cipher, an AI daemon. Generate a concise, professional onboarding guide "
                "for a new client. Include: welcome message, 5 quick-start steps, top 10 commands "
                "to try, and what to expect in week 1. Be specific and actionable. Output as markdown."
            ),
            user_prompt=(
                f"Company: {company}\nContact: {contact_name}\nTier: {tier}\n"
                f"Client ID: {client_id}\n\n"
                "Generate a personalized onboarding guide."
            ),
            max_tokens=2048,
        )

        onboarding = {
            "title": f"Elysian Protocol — Onboarding Guide for {company}",
            "client_id": client_id,
            "tier": tier,
            "generated_at": datetime.utcnow().isoformat(),
        }

        if llm_content:
            onboarding["content_markdown"] = llm_content
            filepath = self._save_document(
                f"onboarding_{client_id}.md", llm_content, subfolder="onboarding"
            )
            onboarding["file_path"] = str(filepath)
        else:
            # Template fallback
            greeting = f"Welcome {contact_name}!" if contact_name else f"Welcome, {company} team!"
            onboarding["content_markdown"] = (
                f"# {onboarding['title']}\n\n{greeting}\n\n"
                f"## Quick Start\n1. Access dashboard at https://elysianprotocol.io/dashboard\n"
                f"2. Your daemon is pre-configured for {tier} tier\n"
                f"3. Start a conversation — just type naturally\n"
                f"4. Try: 'Research my competitors' or 'Draft a social media post'\n"
                f"5. Check the /help command for full capability list\n"
            )

        return AgentResult(task_id=task.task_id, agent_name=self.name, success=True, output=onboarding)

    async def _generate_activation_plan(self, task: AgentTask) -> AgentResult:
        """Build LLM-powered activation plan tailored to client's audit data."""
        company = task.params.get("company", "")
        audit_data = task.params.get("audit_data", {})
        tier = task.params.get("tier", "business")

        recommended_agents = audit_data.get("recommended_cipher_agents", [
            "Communication Agent", "Research Agent", "Apex Architect",
            "Monitor Agent", "Data Agent",
        ])

        llm_content = await self._llm_generate(
            system_prompt=(
                "You are Cipher, an AI daemon platform. Generate a detailed 4-week agent activation plan "
                "for a new client. Break it into 3 phases: Core Infrastructure (Week 1), Growth & Content "
                "(Week 2), Full Intelligence Suite (Weeks 3-4). Include specific agent names, objectives, "
                "success criteria, and KPIs. Output as markdown."
            ),
            user_prompt=(
                f"Company: {company}\nTier: {tier}\n"
                f"Recommended agents: {', '.join(recommended_agents)}\n"
                f"Audit data: {json.dumps(audit_data, default=str)[:1000]}\n\n"
                "Generate a phased activation plan."
            ),
            max_tokens=2048,
        )

        plan = {
            "company": company,
            "tier": tier,
            "total_agents": len(recommended_agents),
            "recommended_agents": recommended_agents,
            "generated_at": datetime.utcnow().isoformat(),
        }

        if llm_content:
            plan["content_markdown"] = llm_content
            filepath = self._save_document(
                f"activation_{company.lower().replace(' ', '_')}.md",
                llm_content, subfolder="activation_plans",
            )
            plan["file_path"] = str(filepath)
        else:
            # Template fallback — same as v1
            base_date = datetime.utcnow()
            plan["phases"] = [
                {"phase": 1, "name": "Core Infrastructure", "timeline": "Week 1", "agents": recommended_agents[:2]},
                {"phase": 2, "name": "Content & Marketing", "timeline": "Week 2", "agents": recommended_agents[2:4]},
                {"phase": 3, "name": "Full Suite", "timeline": "Weeks 3-4", "agents": recommended_agents[4:]},
            ]

        return AgentResult(task_id=task.task_id, agent_name=self.name, success=True, output=plan)

    async def _generate_training(self, task: AgentTask) -> AgentResult:
        """Create LLM-powered training materials."""
        company = task.params.get("company", "")
        tier = task.params.get("tier", "business")

        llm_content = await self._llm_generate(
            system_prompt=(
                "You are Cipher, an AI daemon platform. Generate a comprehensive training guide "
                "with 4 modules: Getting Started (15 min), Power User Commands (20 min), "
                "Agent Deep Dives (30 min), Advanced Workflows (20 min). Include real examples "
                "and exercises. Output as markdown."
            ),
            user_prompt=f"Company: {company}\nTier: {tier}\n\nGenerate training materials.",
            max_tokens=3000,
        )

        training = {
            "title": f"Cipher Training Guide — {company}",
            "tier": tier,
            "total_duration": "~85 minutes",
            "generated_at": datetime.utcnow().isoformat(),
        }

        if llm_content:
            training["content_markdown"] = llm_content
            filepath = self._save_document(
                f"training_{company.lower().replace(' ', '_')}.md",
                llm_content, subfolder="training",
            )
            training["file_path"] = str(filepath)
        else:
            training["modules"] = [
                {"module": 1, "title": "Getting Started with Cipher", "duration": "15 minutes"},
                {"module": 2, "title": "Power User Commands", "duration": "20 minutes"},
                {"module": 3, "title": "Agent Deep Dives", "duration": "30 minutes"},
                {"module": 4, "title": "Advanced Workflows", "duration": "20 minutes"},
            ]

        return AgentResult(task_id=task.task_id, agent_name=self.name, success=True, output=training)

    # ═══════════════════════════════════════════════════════════════
    # NEW AGENTIC CAPABILITIES
    # ═══════════════════════════════════════════════════════════════

    async def _create_document(self, task: AgentTask) -> AgentResult:
        """Generate real business documents — proposals, SOWs, contracts, briefs."""
        doc_type = task.params.get("doc_type", "proposal")
        company = task.params.get("company", "")
        details = task.params.get("details", "")
        recipient = task.params.get("recipient", "")

        doc_prompts = {
            "proposal": (
                "Generate a professional business proposal. Include: executive summary, "
                "scope of work, deliverables, timeline, pricing structure, terms. "
                "Make it compelling and specific."
            ),
            "sow": (
                "Generate a detailed Statement of Work (SOW). Include: project overview, "
                "objectives, scope, deliverables with acceptance criteria, timeline with milestones, "
                "resource requirements, assumptions, constraints, and sign-off section."
            ),
            "contract": (
                "Generate a professional services contract. Include: parties, scope of services, "
                "payment terms, intellectual property, confidentiality, termination, liability, "
                "dispute resolution. NOTE: Include disclaimer that this is a template and should "
                "be reviewed by legal counsel."
            ),
            "brief": (
                "Generate a project brief. Include: background, objectives, target audience, "
                "key messages, deliverables, timeline, budget, success metrics."
            ),
            "pitch_deck_outline": (
                "Generate a pitch deck outline with slide-by-slide content. Include: "
                "title, problem, solution, market size, business model, traction, team, "
                "financials, ask. Provide specific talking points for each slide."
            ),
            "onepage": (
                "Generate a one-page business overview. Include: company description, "
                "value proposition, target market, revenue model, competitive advantage, "
                "key metrics, team, contact info. Keep it to one page."
            ),
        }

        system = doc_prompts.get(doc_type, doc_prompts["proposal"])

        llm_content = await self._llm_generate(
            system_prompt=f"You are a professional business document generator. {system} Output as markdown.",
            user_prompt=(
                f"Document type: {doc_type}\n"
                f"Company/From: Elysian Protocol (AI automation platform)\n"
                f"Client/To: {recipient or company}\n"
                f"Details: {details}\n\n"
                "Generate the document now."
            ),
            max_tokens=4096,
        )

        if not llm_content:
            return AgentResult(
                task_id=task.task_id, agent_name=self.name, success=False,
                error="LLM generation failed — unable to create document. Check API keys.",
            )

        filename = f"{doc_type}_{company.lower().replace(' ', '_') if company else 'draft'}_{datetime.utcnow().strftime('%Y%m%d')}.md"
        filepath = self._save_document(filename, llm_content, subfolder="generated_docs")

        return AgentResult(
            task_id=task.task_id, agent_name=self.name, success=True,
            output={
                "doc_type": doc_type,
                "company": company,
                "file_path": str(filepath),
                "content_preview": llm_content[:500] + "..." if len(llm_content) > 500 else llm_content,
                "full_content": llm_content,
                "generated_at": datetime.utcnow().isoformat(),
            },
        )

    async def _shopify_audit(self, task: AgentTask) -> AgentResult:
        """Audit a Shopify store — real web research + LLM analysis."""
        store_url = task.params.get("store_url", "")
        store_name = task.params.get("store_name", "")
        industry = task.params.get("industry", "e-commerce")

        if not store_url and not store_name:
            return AgentResult(
                task_id=task.task_id, agent_name=self.name, success=False,
                error="Provide 'store_url' (e.g., mystore.myshopify.com) or 'store_name'",
            )

        await self.emit_progress("Researching Shopify best practices...")

        # Research top stores in the industry for benchmarking
        benchmark_results = await self._web_search(
            f"best Shopify stores {industry} 2024 2025 design conversion optimization"
        )

        # Research common Shopify optimization strategies
        optimization_results = await self._web_search(
            "Shopify store optimization checklist conversion rate speed SEO"
        )

        # Build research context
        research_context = ""
        if benchmark_results:
            research_context += "Top stores found:\n"
            for r in benchmark_results:
                research_context += f"- {r['title']}: {r['description'][:150]}\n"
        if optimization_results:
            research_context += "\nOptimization best practices:\n"
            for r in optimization_results:
                research_context += f"- {r['title']}: {r['description'][:150]}\n"

        await self.emit_progress("Generating audit report with LLM analysis...")

        llm_content = await self._llm_generate(
            system_prompt=(
                "You are an expert Shopify store consultant. Generate a detailed store audit report. "
                "Cover: 1) Store Overview & First Impressions, 2) Design & UX (layout, mobile, navigation), "
                "3) Product Pages (images, descriptions, trust signals), 4) SEO Analysis, "
                "5) Conversion Optimization (checkout, cart abandonment), 6) Speed & Performance, "
                "7) Competitive Positioning, 8) Action Plan (prioritized improvements with estimated impact). "
                "Be specific and actionable. Reference real best practices."
            ),
            user_prompt=(
                f"Store: {store_url or store_name}\n"
                f"Industry: {industry}\n\n"
                f"Research context:\n{research_context}\n\n"
                "Generate a comprehensive Shopify store audit."
            ),
            max_tokens=4096,
        )

        if not llm_content:
            return AgentResult(
                task_id=task.task_id, agent_name=self.name, success=False,
                error="LLM generation failed for Shopify audit.",
            )

        filename = f"shopify_audit_{(store_name or 'store').lower().replace(' ', '_')}_{datetime.utcnow().strftime('%Y%m%d')}.md"
        filepath = self._save_document(filename, llm_content, subfolder="shopify_audits")

        return AgentResult(
            task_id=task.task_id, agent_name=self.name, success=True,
            output={
                "store": store_url or store_name,
                "industry": industry,
                "benchmarks_found": len(benchmark_results),
                "file_path": str(filepath),
                "content_preview": llm_content[:500] + "...",
                "full_content": llm_content,
                "generated_at": datetime.utcnow().isoformat(),
            },
        )

    async def _llc_formation(self, task: AgentTask) -> AgentResult:
        """Generate LLC formation documents and state-specific filing checklist."""
        company_name = task.params.get("company_name", "")
        state = task.params.get("state", "")
        members = task.params.get("members", [])
        business_purpose = task.params.get("business_purpose", "")
        registered_agent = task.params.get("registered_agent", "")

        if not company_name:
            return AgentResult(
                task_id=task.task_id, agent_name=self.name, success=False,
                error="Missing 'company_name'. Also provide: state, members, business_purpose",
            )

        if not state:
            return AgentResult(
                task_id=task.task_id, agent_name=self.name, success=False,
                error="Missing 'state' — needed for state-specific filing requirements",
            )

        await self.emit_progress(f"Researching {state} LLC requirements...")

        # Research state-specific requirements
        state_research = await self._web_search(
            f"{state} LLC formation requirements filing fee articles of organization 2024 2025"
        )

        research_context = ""
        if state_research:
            for r in state_research:
                research_context += f"- {r['title']}: {r['description'][:200]}\n"

        await self.emit_progress("Generating LLC formation documents...")

        # Generate Articles of Organization
        articles_content = await self._llm_generate(
            system_prompt=(
                "You are a business formation specialist. Generate Articles of Organization for an LLC. "
                "Include all standard sections: company name, registered agent, business purpose, "
                "management structure, member information, duration, dissolution terms. "
                "Make it state-specific. Include a DISCLAIMER that this is a template and should "
                "be reviewed by an attorney before filing. Output as markdown."
            ),
            user_prompt=(
                f"LLC Name: {company_name} LLC\n"
                f"State: {state}\n"
                f"Members: {json.dumps(members) if members else 'To be specified'}\n"
                f"Business Purpose: {business_purpose or 'General business purposes'}\n"
                f"Registered Agent: {registered_agent or 'To be designated'}\n\n"
                f"State research:\n{research_context}\n\n"
                "Generate the Articles of Organization."
            ),
            max_tokens=3000,
        )

        # Generate Operating Agreement
        operating_agreement = await self._llm_generate(
            system_prompt=(
                "You are a business formation specialist. Generate an LLC Operating Agreement. "
                "Include: members and ownership percentages, management structure, capital contributions, "
                "profit/loss distribution, voting rights, transfer of interest, dissolution provisions, "
                "amendment process. Include DISCLAIMER to consult an attorney. Output as markdown."
            ),
            user_prompt=(
                f"LLC Name: {company_name} LLC\n"
                f"State: {state}\n"
                f"Members: {json.dumps(members) if members else 'Single member'}\n"
                f"Business Purpose: {business_purpose}\n\n"
                "Generate the Operating Agreement."
            ),
            max_tokens=3000,
        )

        # Generate filing checklist
        checklist_content = await self._llm_generate(
            system_prompt=(
                "Generate a step-by-step LLC formation checklist specific to the given state. "
                "Include: 1) Name availability check, 2) Articles of Organization filing, "
                "3) EIN application (IRS), 4) Operating Agreement, 5) Business licenses, "
                "6) Bank account, 7) State tax registration, 8) Annual report requirements. "
                "Include estimated costs and links where possible. Output as markdown."
            ),
            user_prompt=(
                f"State: {state}\nLLC Name: {company_name}\n\n"
                f"State research:\n{research_context}\n\n"
                "Generate the filing checklist."
            ),
            max_tokens=2000,
        )

        # Save all documents
        docs = {}
        if articles_content:
            fp = self._save_document(
                f"articles_of_organization_{company_name.lower().replace(' ', '_')}.md",
                articles_content, subfolder=f"llc/{company_name.lower().replace(' ', '_')}",
            )
            docs["articles_of_organization"] = {"file_path": str(fp), "preview": articles_content[:300]}

        if operating_agreement:
            fp = self._save_document(
                f"operating_agreement_{company_name.lower().replace(' ', '_')}.md",
                operating_agreement, subfolder=f"llc/{company_name.lower().replace(' ', '_')}",
            )
            docs["operating_agreement"] = {"file_path": str(fp), "preview": operating_agreement[:300]}

        if checklist_content:
            fp = self._save_document(
                f"filing_checklist_{state.lower().replace(' ', '_')}.md",
                checklist_content, subfolder=f"llc/{company_name.lower().replace(' ', '_')}",
            )
            docs["filing_checklist"] = {"file_path": str(fp), "preview": checklist_content[:300]}

        if not docs:
            return AgentResult(
                task_id=task.task_id, agent_name=self.name, success=False,
                error="LLM generation failed for LLC documents. Check API keys.",
            )

        return AgentResult(
            task_id=task.task_id, agent_name=self.name, success=True,
            output={
                "company_name": f"{company_name} LLC",
                "state": state,
                "documents_generated": list(docs.keys()),
                "documents": docs,
                "disclaimer": "These are template documents. Consult a licensed attorney before filing.",
                "generated_at": datetime.utcnow().isoformat(),
            },
        )

    async def _patent_draft(self, task: AgentTask) -> AgentResult:
        """Draft provisional patent application outline with claims."""
        invention_title = task.params.get("title", "")
        description = task.params.get("description", "")
        inventor_name = task.params.get("inventor", "")
        field = task.params.get("field", "technology")
        prior_art = task.params.get("prior_art", "")

        if not invention_title or not description:
            return AgentResult(
                task_id=task.task_id, agent_name=self.name, success=False,
                error="Provide 'title' (invention name) and 'description' (what it does, how it works)",
            )

        await self.emit_progress("Researching prior art...")

        # Search for prior art
        prior_art_results = await self._web_search(
            f"patent prior art {field} {invention_title} site:patents.google.com OR site:uspto.gov"
        )

        research_context = ""
        if prior_art_results:
            for r in prior_art_results:
                research_context += f"- {r['title']}: {r['url']}\n"
        if prior_art:
            research_context += f"\nUser-provided prior art notes: {prior_art}\n"

        await self.emit_progress("Drafting provisional patent application...")

        patent_content = await self._llm_generate(
            system_prompt=(
                "You are a patent drafting specialist. Generate a provisional patent application outline. "
                "Include all required sections: Title, Field of Invention, Background (prior art analysis), "
                "Summary of Invention, Detailed Description, Claims (independent + dependent), "
                "Abstract. Write claims in proper patent language. "
                "Include DISCLAIMER that this is a draft outline and should be reviewed by a patent attorney. "
                "Output as markdown."
            ),
            user_prompt=(
                f"Invention Title: {invention_title}\n"
                f"Inventor: {inventor_name or 'To be specified'}\n"
                f"Field: {field}\n"
                f"Description: {description}\n\n"
                f"Prior Art Research:\n{research_context}\n\n"
                "Generate the provisional patent application draft."
            ),
            max_tokens=4096,
        )

        if not patent_content:
            return AgentResult(
                task_id=task.task_id, agent_name=self.name, success=False,
                error="LLM generation failed for patent draft.",
            )

        filename = f"patent_draft_{invention_title.lower().replace(' ', '_')[:30]}_{datetime.utcnow().strftime('%Y%m%d')}.md"
        filepath = self._save_document(filename, patent_content, subfolder="patents")

        return AgentResult(
            task_id=task.task_id, agent_name=self.name, success=True,
            output={
                "title": invention_title,
                "inventor": inventor_name,
                "field": field,
                "prior_art_found": len(prior_art_results),
                "file_path": str(filepath),
                "content_preview": patent_content[:500] + "...",
                "full_content": patent_content,
                "disclaimer": "This is a draft outline. Consult a registered patent attorney before filing with the USPTO.",
                "generated_at": datetime.utcnow().isoformat(),
            },
        )

    # ═══════════════════════════════════════════════════════════════
    # SHOPIFY ADMIN API — Real store access
    # ═══════════════════════════════════════════════════════════════

    def _shopify_base_url(self, store: str = "") -> str:
        """Build Shopify Admin API base URL."""
        s = store or self.shopify_store
        if not s:
            return ""
        # Handle both "tallowroots" and "tallowroots.myshopify.com"
        if ".myshopify.com" not in s:
            s = f"{s}.myshopify.com"
        return f"https://{s}/admin/api/{self.shopify_api_version}"

    def _shopify_headers(self, token: str = "") -> dict:
        """Build Shopify API headers."""
        t = token or self.shopify_token
        return {
            "X-Shopify-Access-Token": t,
            "Content-Type": "application/json",
        }

    async def _shopify_api(self, method: str, endpoint: str, data: dict = None,
                            store: str = "", token: str = "") -> dict:
        """Make a Shopify Admin API call. Returns {"ok": bool, "data": ..., "error": ...}"""
        base = self._shopify_base_url(store)
        t = token or self.shopify_token
        if not base or not t:
            return {"ok": False, "error": "Shopify not configured. Set SHOPIFY_STORE and SHOPIFY_ACCESS_TOKEN in .env"}

        url = f"{base}/{endpoint}.json"
        headers = self._shopify_headers(t)

        try:
            async with httpx.AsyncClient(timeout=20) as client:
                if method == "GET":
                    resp = await client.get(url, headers=headers)
                elif method == "PUT":
                    resp = await client.put(url, headers=headers, json=data)
                elif method == "POST":
                    resp = await client.post(url, headers=headers, json=data)
                elif method == "DELETE":
                    resp = await client.delete(url, headers=headers)
                else:
                    return {"ok": False, "error": f"Unknown method: {method}"}

                if resp.status_code in (200, 201):
                    return {"ok": True, "data": resp.json()}
                else:
                    return {"ok": False, "error": f"HTTP {resp.status_code}: {resp.text[:500]}"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    async def _shopify_read(self, task: AgentTask) -> AgentResult:
        """Read data from Shopify store — products, pages, blogs, metafields, themes."""
        resource = task.params.get("resource", "products")  # products, pages, blogs, themes, smart_collections, custom_collections
        store = task.params.get("store", "")
        token = task.params.get("token", "")
        resource_id = task.params.get("resource_id", "")  # Optional: specific ID
        limit = task.params.get("limit", 50)

        endpoint_map = {
            "products": "products",
            "pages": "pages",
            "blogs": "blogs",
            "themes": "themes",
            "collections": "smart_collections",
            "custom_collections": "custom_collections",
            "orders": "orders",
            "customers": "customers",
        }

        endpoint = endpoint_map.get(resource, resource)
        if resource_id:
            endpoint = f"{endpoint}/{resource_id}"
        else:
            endpoint = f"{endpoint}?limit={limit}"

        result = await self._shopify_api("GET", endpoint, store=store, token=token)

        if not result["ok"]:
            return AgentResult(
                task_id=task.task_id, agent_name=self.name, success=False,
                error=f"Shopify API error: {result['error']}",
            )

        return AgentResult(
            task_id=task.task_id, agent_name=self.name, success=True,
            output={
                "resource": resource,
                "data": result["data"],
                "store": store or self.shopify_store,
                "read_at": datetime.utcnow().isoformat(),
            },
        )

    async def _shopify_update(self, task: AgentTask) -> AgentResult:
        """Update a Shopify resource — product, page, blog post, metafield."""
        resource = task.params.get("resource", "")  # "product", "page"
        resource_id = task.params.get("resource_id", "")
        updates = task.params.get("updates", {})
        store = task.params.get("store", "")
        token = task.params.get("token", "")

        if not resource or not resource_id or not updates:
            return AgentResult(
                task_id=task.task_id, agent_name=self.name, success=False,
                error="Provide 'resource' (product/page), 'resource_id', and 'updates' dict.",
            )

        # Map singular to endpoint
        endpoint = f"{resource}s/{resource_id}"

        # Wrap updates in the resource key Shopify expects
        payload = {resource: updates}

        result = await self._shopify_api("PUT", endpoint, data=payload, store=store, token=token)

        if not result["ok"]:
            return AgentResult(
                task_id=task.task_id, agent_name=self.name, success=False,
                error=f"Shopify update failed: {result['error']}",
            )

        return AgentResult(
            task_id=task.task_id, agent_name=self.name, success=True,
            output={
                "resource": resource,
                "resource_id": resource_id,
                "updates_applied": list(updates.keys()),
                "result": result["data"],
                "updated_at": datetime.utcnow().isoformat(),
            },
        )

    async def _shopify_fix(self, task: AgentTask) -> AgentResult:
        """Full auto-fix: read store → analyze with LLM → apply fixes."""
        store = task.params.get("store", "")
        token = task.params.get("token", "")
        fix_scope = task.params.get("scope", "all")  # "seo", "products", "pages", "all"

        # Step 1: Read products
        await self.emit_progress("Reading store products...")
        products_result = await self._shopify_api("GET", "products?limit=50", store=store, token=token)
        if not products_result["ok"]:
            return AgentResult(
                task_id=task.task_id, agent_name=self.name, success=False,
                error=f"Cannot access Shopify store: {products_result['error']}",
            )

        products = products_result["data"].get("products", [])

        # Step 2: Read pages
        await self.emit_progress("Reading store pages...")
        pages_result = await self._shopify_api("GET", "pages?limit=50", store=store, token=token)
        pages = pages_result["data"].get("pages", []) if pages_result["ok"] else []

        # Step 3: Analyze with LLM
        await self.emit_progress(f"Analyzing {len(products)} products and {len(pages)} pages...")

        product_summary = []
        for p in products[:20]:  # Cap at 20 for LLM context
            product_summary.append({
                "id": p["id"],
                "title": p.get("title", ""),
                "body_html_preview": (p.get("body_html", "") or "")[:200],
                "seo_title": p.get("metafields_global_title_tag", "") or "",
                "seo_description": p.get("metafields_global_description_tag", "") or "",
                "tags": p.get("tags", ""),
                "vendor": p.get("vendor", ""),
                "product_type": p.get("product_type", ""),
                "images_count": len(p.get("images", [])),
                "variants_count": len(p.get("variants", [])),
            })

        page_summary = []
        for pg in pages[:10]:
            page_summary.append({
                "id": pg["id"],
                "title": pg.get("title", ""),
                "body_html_preview": (pg.get("body_html", "") or "")[:200],
            })

        analysis = await self._llm_generate(
            system_prompt=(
                "You are a Shopify store optimization expert. Analyze this store data and output "
                "a JSON object with specific fixes. Format:\n"
                '{"product_fixes": [{"id": 123, "title": "new title", "body_html": "new description", '
                '"seo_title": "...", "seo_description": "..."}], '
                '"page_fixes": [{"id": 456, "title": "...", "body_html": "..."}], '
                '"missing_pages": [{"title": "FAQ", "body_html": "..."}], '
                '"summary": "what was fixed and why"}\n'
                "Focus on: SEO titles/descriptions, compelling product descriptions, "
                "missing pages (FAQ, About, Shipping, Returns), and weak content. "
                "Output ONLY valid JSON."
            ),
            user_prompt=(
                f"Store products:\n{json.dumps(product_summary, indent=2)}\n\n"
                f"Store pages:\n{json.dumps(page_summary, indent=2)}\n\n"
                f"Fix scope: {fix_scope}\n"
                "Analyze and output the fix plan as JSON."
            ),
            max_tokens=4096,
        )

        # Parse LLM fix plan
        fix_plan = {}
        if analysis:
            try:
                # Try to extract JSON from the response
                import re
                json_match = re.search(r'\{[\s\S]*\}', analysis)
                if json_match:
                    fix_plan = json.loads(json_match.group())
            except Exception as e:
                logger.warning(f"Could not parse LLM fix plan as JSON: {e}")

        if not fix_plan:
            return AgentResult(
                task_id=task.task_id, agent_name=self.name, success=False,
                error="LLM analysis did not produce a valid fix plan.",
            )

        # Step 4: Apply fixes
        applied_fixes = []
        errors = []

        # Fix products
        for pfix in fix_plan.get("product_fixes", []):
            pid = pfix.get("id")
            if not pid:
                continue
            updates = {}
            if pfix.get("title"):
                updates["title"] = pfix["title"]
            if pfix.get("body_html"):
                updates["body_html"] = pfix["body_html"]
            if pfix.get("seo_title"):
                updates["metafields_global_title_tag"] = pfix["seo_title"]
            if pfix.get("seo_description"):
                updates["metafields_global_description_tag"] = pfix["seo_description"]
            if pfix.get("tags"):
                updates["tags"] = pfix["tags"]

            if updates:
                await self.emit_progress(f"Fixing product {pid}...")
                result = await self._shopify_api("PUT", f"products/{pid}", data={"product": updates}, store=store, token=token)
                if result["ok"]:
                    applied_fixes.append({"type": "product", "id": pid, "fields": list(updates.keys())})
                else:
                    errors.append({"type": "product", "id": pid, "error": result["error"]})

        # Fix pages
        for pgfix in fix_plan.get("page_fixes", []):
            pgid = pgfix.get("id")
            if not pgid:
                continue
            updates = {}
            if pgfix.get("title"):
                updates["title"] = pgfix["title"]
            if pgfix.get("body_html"):
                updates["body_html"] = pgfix["body_html"]

            if updates:
                await self.emit_progress(f"Fixing page {pgid}...")
                result = await self._shopify_api("PUT", f"pages/{pgid}", data={"page": updates}, store=store, token=token)
                if result["ok"]:
                    applied_fixes.append({"type": "page", "id": pgid, "fields": list(updates.keys())})
                else:
                    errors.append({"type": "page", "id": pgid, "error": result["error"]})

        # Create missing pages
        for new_page in fix_plan.get("missing_pages", []):
            title = new_page.get("title", "")
            body = new_page.get("body_html", "")
            if title and body:
                await self.emit_progress(f"Creating page: {title}...")
                result = await self._shopify_api(
                    "POST", "pages",
                    data={"page": {"title": title, "body_html": body, "published": True}},
                    store=store, token=token,
                )
                if result["ok"]:
                    applied_fixes.append({"type": "new_page", "title": title})
                else:
                    errors.append({"type": "new_page", "title": title, "error": result["error"]})

        output = {
            "store": store or self.shopify_store,
            "products_analyzed": len(products),
            "pages_analyzed": len(pages),
            "fixes_applied": len(applied_fixes),
            "errors": len(errors),
            "applied": applied_fixes,
            "error_details": errors,
            "summary": fix_plan.get("summary", "Fixes applied"),
            "fix_scope": fix_scope,
            "fixed_at": datetime.utcnow().isoformat(),
        }

        # Save fix report
        filename = f"shopify_fix_{(store or self.shopify_store).replace('.', '_')}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        (self._data_dir / filename).write_text(json.dumps(output, indent=2))

        return AgentResult(task_id=task.task_id, agent_name=self.name, success=True, output=output)

    async def verify(self, result: AgentResult) -> bool:
        if not isinstance(result.output, dict):
            return False
        if result.success and not result.output:
            return False
        return True
