"""
Evolution proposal generation and weekly briefing system.

Converts detected features into implementation proposals with:
- Cost estimates
- Component impact analysis
- Philosophy alignment checks
- Weekly recap compilation
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Optional

from app.core.config import settings
from app.core.logging import logger
from .evolution_scanner import (
    FeatureProposal,
    ImplementationDifficulty,
    CompetitiveUrgency,
    SourceCategory,
)


class DecisionStatus(str, Enum):
    """Proposal decision status."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    DEFERRED = "deferred"


class PhilosophyAlignment(str, Enum):
    """How well a feature aligns with Cipher's philosophy."""
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    CONFLICTING = "conflicting"


@dataclass
class CostEstimate:
    """Estimated costs for feature implementation."""

    estimated_tokens_per_request: int
    monthly_api_cost_estimate: float
    development_hours: int
    infrastructure_overhead: str  # low, medium, high, critical
    notes: str = ""


@dataclass
class ComponentImpact:
    """Impact analysis for affected components."""

    component_name: str
    breaking_changes: bool
    estimated_changes: int
    dependencies_affected: list[str] = field(default_factory=list)
    migration_required: bool = False
    risk_level: str = "low"  # low, medium, high


@dataclass
class ImplementationPlan:
    """Detailed implementation plan for a feature."""

    proposal_id: str
    feature_name: str
    source: str
    summary: str
    philosophy_alignment: PhilosophyAlignment
    cost_estimate: CostEstimate
    component_impacts: list[ComponentImpact]
    conflicts: list[str]  # Philosophy conflicts if any
    estimated_timeline: str
    risk_factors: list[str]
    recommended_action: str
    priority_score: float  # 0-1
    decision_status: DecisionStatus = DecisionStatus.PENDING
    approval_notes: str = ""
    rejection_reason: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    decided_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "proposal_id": self.proposal_id,
            "feature_name": self.feature_name,
            "source": self.source,
            "summary": self.summary,
            "philosophy_alignment": self.philosophy_alignment.value,
            "cost_estimate": {
                "estimated_tokens_per_request": self.cost_estimate.estimated_tokens_per_request,
                "monthly_api_cost_estimate": self.cost_estimate.monthly_api_cost_estimate,
                "development_hours": self.cost_estimate.development_hours,
                "infrastructure_overhead": self.cost_estimate.infrastructure_overhead,
                "notes": self.cost_estimate.notes,
            },
            "component_impacts": [
                {
                    "component_name": impact.component_name,
                    "breaking_changes": impact.breaking_changes,
                    "estimated_changes": impact.estimated_changes,
                    "dependencies_affected": impact.dependencies_affected,
                    "migration_required": impact.migration_required,
                    "risk_level": impact.risk_level,
                }
                for impact in self.component_impacts
            ],
            "conflicts": self.conflicts,
            "estimated_timeline": self.estimated_timeline,
            "risk_factors": self.risk_factors,
            "recommended_action": self.recommended_action,
            "priority_score": self.priority_score,
            "decision_status": self.decision_status.value,
            "approval_notes": self.approval_notes,
            "rejection_reason": self.rejection_reason,
            "created_at": self.created_at.isoformat(),
            "decided_at": self.decided_at.isoformat() if self.decided_at else None,
        }


class EvolutionProposalGenerator:
    """Generate implementation plans from feature proposals and compile weekly recaps."""

    # Cipher philosophy principles
    PHILOSOPHY_KEYWORDS = {
        "sovereign": ["sovereign", "independent", "private", "self-hosted", "on-premise"],
        "privacy": ["privacy", "encrypted", "confidential", "no tracking", "local"],
        "efficiency": ["efficient", "optimized", "fast", "lightweight", "minimal"],
        "openness": ["open", "transparent", "decentralized", "community"],
    }

    # Cost estimate defaults (in USD)
    COST_ESTIMATES = {
        ImplementationDifficulty.EASY: {
            "tokens": 100,
            "monthly_cost": 50,
            "dev_hours": 16,
        },
        ImplementationDifficulty.MEDIUM: {
            "tokens": 500,
            "monthly_cost": 200,
            "dev_hours": 64,
        },
        ImplementationDifficulty.HARD: {
            "tokens": 2000,
            "monthly_cost": 800,
            "dev_hours": 160,
        },
        ImplementationDifficulty.EPIC: {
            "tokens": 5000,
            "monthly_cost": 2000,
            "dev_hours": 320,
        },
    }

    def __init__(self, data_dir: str = "/data/evolution"):
        """Initialize proposal generator."""
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.proposals_file = self.data_dir / "proposals.json"
        self.decisions_file = self.data_dir / "decisions.json"
        self.recaps_dir = self.data_dir / "recaps"
        self.recaps_dir.mkdir(exist_ok=True)

    async def generate_plan(self, feature_proposal: FeatureProposal) -> ImplementationPlan:
        """
        Generate a complete implementation plan from a feature proposal.

        Args:
            feature_proposal: The feature proposal to analyze

        Returns:
            Complete implementation plan
        """
        # Assess philosophy alignment
        alignment = self._assess_philosophy_alignment(feature_proposal.description)

        # Estimate costs
        cost_estimate = self._estimate_costs(feature_proposal.implementation_difficulty)

        # Analyze component impacts
        component_impacts = self._analyze_component_impacts(
            feature_proposal.affected_components
        )

        # Identify conflicts
        conflicts = self._identify_philosophy_conflicts(
            feature_proposal.description, alignment
        )

        # Estimate timeline
        timeline = self._estimate_timeline(feature_proposal.implementation_difficulty)

        # Identify risk factors
        risk_factors = self._identify_risks(
            feature_proposal.implementation_difficulty,
            len(component_impacts),
            bool(conflicts),
        )

        # Calculate priority score
        priority_score = self._calculate_priority(
            feature_proposal.relevance_score,
            feature_proposal.competitive_urgency,
            feature_proposal.implementation_difficulty,
            alignment,
        )

        # Generate summary
        summary = self._generate_summary(feature_proposal, alignment)

        # Determine recommended action
        recommended_action = self._determine_action(
            priority_score, alignment, conflicts
        )

        plan = ImplementationPlan(
            proposal_id=feature_proposal.id,
            feature_name=feature_proposal.feature_name,
            source=feature_proposal.source,
            summary=summary,
            philosophy_alignment=alignment,
            cost_estimate=cost_estimate,
            component_impacts=component_impacts,
            conflicts=conflicts,
            estimated_timeline=timeline,
            risk_factors=risk_factors,
            recommended_action=recommended_action,
            priority_score=priority_score,
        )

        return plan

    def _assess_philosophy_alignment(self, description: str) -> PhilosophyAlignment:
        """Assess how well the feature aligns with Cipher's philosophy."""
        description_lower = description.lower()

        # Check for philosophy conflicts
        conflicting_terms = [
            "cloud-only", "proprietary", "vendor-lock", "closed",
            "tracking", "surveillance", "telemetry required"
        ]
        if any(term in description_lower for term in conflicting_terms):
            return PhilosophyAlignment.CONFLICTING

        # Check for strong alignment
        strong_terms = self.PHILOSOPHY_KEYWORDS.get("sovereign", []) + \
                       self.PHILOSOPHY_KEYWORDS.get("privacy", [])
        strong_matches = sum(
            1 for term in strong_terms if term in description_lower
        )
        if strong_matches >= 2:
            return PhilosophyAlignment.STRONG

        # Check for moderate alignment
        moderate_terms = self.PHILOSOPHY_KEYWORDS.get("efficiency", []) + \
                        self.PHILOSOPHY_KEYWORDS.get("openness", [])
        moderate_matches = sum(
            1 for term in moderate_terms if term in description_lower
        )
        if moderate_matches >= 1:
            return PhilosophyAlignment.MODERATE

        return PhilosophyAlignment.WEAK

    def _estimate_costs(self, difficulty: ImplementationDifficulty) -> CostEstimate:
        """Estimate implementation costs."""
        est = self.COST_ESTIMATES.get(difficulty, self.COST_ESTIMATES[ImplementationDifficulty.MEDIUM])

        overhead = "low"
        if difficulty == ImplementationDifficulty.EPIC:
            overhead = "critical"
        elif difficulty == ImplementationDifficulty.HARD:
            overhead = "high"
        elif difficulty == ImplementationDifficulty.MEDIUM:
            overhead = "medium"

        return CostEstimate(
            estimated_tokens_per_request=est["tokens"],
            monthly_api_cost_estimate=est["monthly_cost"],
            development_hours=est["dev_hours"],
            infrastructure_overhead=overhead,
            notes=f"Estimate for {difficulty.value} difficulty feature"
        )

    def _analyze_component_impacts(self, components: list[str]) -> list[ComponentImpact]:
        """Analyze impact on affected components."""
        impacts = []

        # Component-specific impact analysis
        component_data = {
            "llm_router": {
                "breaking_changes": False,
                "changes": 15,
                "migration": False,
                "risk": "low"
            },
            "voice": {
                "breaking_changes": False,
                "changes": 20,
                "migration": False,
                "risk": "medium"
            },
            "memory": {
                "breaking_changes": False,
                "changes": 10,
                "migration": True,
                "risk": "medium"
            },
            "orchestrator": {
                "breaking_changes": True,
                "changes": 25,
                "migration": True,
                "risk": "high"
            },
            "scanner": {
                "breaking_changes": False,
                "changes": 8,
                "migration": False,
                "risk": "low"
            },
            "ios_app": {
                "breaking_changes": False,
                "changes": 30,
                "migration": False,
                "risk": "medium"
            },
            "api": {
                "breaking_changes": False,
                "changes": 12,
                "migration": False,
                "risk": "low"
            },
        }

        for component in components:
            if component in component_data:
                data = component_data[component]
                impacts.append(
                    ComponentImpact(
                        component_name=component,
                        breaking_changes=data["breaking_changes"],
                        estimated_changes=data["changes"],
                        migration_required=data["migration"],
                        risk_level=data["risk"],
                    )
                )

        return impacts

    def _identify_philosophy_conflicts(
        self, description: str, alignment: PhilosophyAlignment
    ) -> list[str]:
        """Identify potential philosophy conflicts."""
        conflicts = []

        if alignment == PhilosophyAlignment.CONFLICTING:
            conflicts.append(
                "Feature may require cloud-only infrastructure, "
                "conflicting with sovereign/privacy-first philosophy"
            )

        description_lower = description.lower()

        if any(term in description_lower for term in ["tracking", "analytics", "telemetry"]):
            conflicts.append(
                "Feature includes telemetry/tracking, "
                "conflicts with privacy-first approach"
            )

        if any(term in description_lower for term in ["proprietary", "closed", "vendor"]):
            conflicts.append(
                "Feature relies on proprietary/closed components, "
                "conflicts with openness principle"
            )

        return conflicts

    def _estimate_timeline(self, difficulty: ImplementationDifficulty) -> str:
        """Estimate development timeline."""
        timelines = {
            ImplementationDifficulty.EASY: "1-2 weeks",
            ImplementationDifficulty.MEDIUM: "2-4 weeks",
            ImplementationDifficulty.HARD: "1-2 months",
            ImplementationDifficulty.EPIC: "2-3+ months",
        }
        return timelines.get(difficulty, "Unknown")

    def _identify_risks(
        self,
        difficulty: ImplementationDifficulty,
        component_count: int,
        has_conflicts: bool,
    ) -> list[str]:
        """Identify risk factors."""
        risks = []

        if difficulty == ImplementationDifficulty.EPIC:
            risks.append("Large scope increases risk of scope creep")
            risks.append("Multiple moving parts, integration complexity")

        if difficulty in [ImplementationDifficulty.HARD, ImplementationDifficulty.EPIC]:
            risks.append("Significant refactoring may be required")

        if component_count > 3:
            risks.append(f"Affects {component_count} components, high integration risk")

        if has_conflicts:
            risks.append("Philosophy conflicts require careful architectural decisions")

        if component_count > 0:
            risks.append("Risk of breaking existing functionality")

        return risks

    def _calculate_priority(
        self,
        relevance: float,
        urgency: CompetitiveUrgency,
        difficulty: ImplementationDifficulty,
        alignment: PhilosophyAlignment,
    ) -> float:
        """Calculate overall priority score (0-1)."""
        # Base score from urgency
        urgency_scores = {
            CompetitiveUrgency.CRITICAL: 1.0,
            CompetitiveUrgency.HIGH: 0.8,
            CompetitiveUrgency.MEDIUM: 0.5,
            CompetitiveUrgency.LOW: 0.3,
        }
        score = urgency_scores.get(urgency, 0.5)

        # Adjust by relevance
        score *= relevance

        # Adjust by difficulty (easier is better)
        difficulty_factors = {
            ImplementationDifficulty.EASY: 1.2,
            ImplementationDifficulty.MEDIUM: 1.0,
            ImplementationDifficulty.HARD: 0.7,
            ImplementationDifficulty.EPIC: 0.5,
        }
        score *= difficulty_factors.get(difficulty, 1.0)

        # Adjust by philosophy alignment
        alignment_factors = {
            PhilosophyAlignment.STRONG: 1.2,
            PhilosophyAlignment.MODERATE: 1.0,
            PhilosophyAlignment.WEAK: 0.7,
            PhilosophyAlignment.CONFLICTING: 0.2,
        }
        score *= alignment_factors.get(alignment, 1.0)

        return min(1.0, max(0.0, score))

    def _generate_summary(
        self, proposal: FeatureProposal, alignment: PhilosophyAlignment
    ) -> str:
        """Generate a human-readable summary."""
        return (
            f"Feature: {proposal.feature_name}\n"
            f"Source: {proposal.source}\n"
            f"Relevance: {proposal.relevance_score:.1%}\n"
            f"Urgency: {proposal.competitive_urgency.value}\n"
            f"Difficulty: {proposal.implementation_difficulty.value}\n"
            f"Philosophy Alignment: {alignment.value}\n\n"
            f"Description:\n{proposal.description}\n\n"
            f"Affected Components: {', '.join(proposal.affected_components)}"
        )

    def _determine_action(
        self, priority: float, alignment: PhilosophyAlignment, conflicts: list[str]
    ) -> str:
        """Determine recommended action."""
        if alignment == PhilosophyAlignment.CONFLICTING:
            return "REJECT - Conflicts with Cipher philosophy"

        if conflicts and priority < 0.6:
            return "REVIEW - Philosophy concerns but may be worthwhile"

        if priority >= 0.8:
            return "STRONG RECOMMEND - High priority, good alignment"

        if priority >= 0.6:
            return "RECOMMEND - Consider for next sprint"

        if priority >= 0.4:
            return "MONITOR - Keep on radar, review later"

        return "LOW PRIORITY - Consider in future planning"

    async def save_proposal(self, plan: ImplementationPlan) -> None:
        """Save proposal to file."""
        try:
            # Load existing proposals
            proposals = []
            if self.proposals_file.exists():
                with open(self.proposals_file, 'r') as f:
                    proposals = json.load(f)

            # Add new proposal
            proposals.append(plan.to_dict())

            # Save
            with open(self.proposals_file, 'w') as f:
                json.dump(proposals, f, indent=2)

            logger.info(f"Saved proposal: {plan.proposal_id}")
        except Exception as e:
            logger.error(f"Failed to save proposal: {e}")

    async def record_decision(
        self,
        proposal_id: str,
        approved: bool,
        notes: str = "",
    ) -> None:
        """Record a decision on a proposal."""
        try:
            # Load existing decisions
            decisions = {}
            if self.decisions_file.exists():
                with open(self.decisions_file, 'r') as f:
                    decisions = json.load(f)

            # Add decision
            decisions[proposal_id] = {
                "approved": approved,
                "notes": notes,
                "decided_at": datetime.utcnow().isoformat(),
            }

            # Save
            with open(self.decisions_file, 'w') as f:
                json.dump(decisions, f, indent=2)

            logger.info(
                f"Recorded decision for {proposal_id}: "
                f"{'APPROVED' if approved else 'REJECTED'}"
            )
        except Exception as e:
            logger.error(f"Failed to record decision: {e}")

    async def get_pending_proposals(self) -> list[dict]:
        """Get all pending proposals."""
        try:
            if self.proposals_file.exists():
                with open(self.proposals_file, 'r') as f:
                    proposals = json.load(f)
                    return [
                        p for p in proposals
                        if p.get("decision_status") == DecisionStatus.PENDING.value
                    ]
        except Exception as e:
            logger.error(f"Failed to load proposals: {e}")

        return []

    async def get_all_proposals(self) -> list[dict]:
        """Get all proposals."""
        try:
            if self.proposals_file.exists():
                with open(self.proposals_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load proposals: {e}")

        return []

    async def get_decisions_history(self) -> dict:
        """Get history of decisions."""
        try:
            if self.decisions_file.exists():
                with open(self.decisions_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load decisions: {e}")

        return {}

    async def generate_weekly_recap(self) -> dict:
        """
        Generate a comprehensive weekly recap of AI evolution findings.

        Returns:
            Dictionary containing formatted weekly briefing
        """
        try:
            # Get last 7 days of proposals
            all_proposals = await self.get_all_proposals()
            now = datetime.utcnow()
            week_ago = now - timedelta(days=7)

            recent_proposals = [
                p for p in all_proposals
                if datetime.fromisoformat(p.get("created_at", "")) > week_ago
            ]

            # Categorize by status
            pending = [p for p in recent_proposals if p.get("decision_status") == "pending"]
            approved = [p for p in recent_proposals if p.get("decision_status") == "approved"]
            rejected = [p for p in recent_proposals if p.get("decision_status") == "rejected"]

            # Sort by priority score
            recent_proposals.sort(key=lambda x: x.get("priority_score", 0), reverse=True)

            # Generate recap
            recap = {
                "generated_at": now.isoformat(),
                "period": f"{(week_ago).isoformat()} to {now.isoformat()}",
                "summary": {
                    "total_findings": len(recent_proposals),
                    "pending_review": len(pending),
                    "approved": len(approved),
                    "rejected": len(rejected),
                },
                "critical_items": [
                    self._format_proposal_for_recap(p)
                    for p in recent_proposals
                    if p.get("priority_score", 0) >= 0.8
                ][:10],
                "high_priority": [
                    self._format_proposal_for_recap(p)
                    for p in recent_proposals
                    if 0.6 <= p.get("priority_score", 0) < 0.8
                ][:10],
                "medium_priority": [
                    self._format_proposal_for_recap(p)
                    for p in recent_proposals
                    if 0.4 <= p.get("priority_score", 0) < 0.6
                ][:10],
                "by_category": self._group_by_category(recent_proposals),
                "by_urgency": self._group_by_urgency(recent_proposals),
            }

            # Save recap
            recap_file = self.recaps_dir / f"weekly_recap_{now.strftime('%Y%m%d_%H%M%S')}.json"
            with open(recap_file, 'w') as f:
                json.dump(recap, f, indent=2)

            logger.info(f"Generated weekly recap with {len(recent_proposals)} findings")
            return recap

        except Exception as e:
            logger.error(f"Failed to generate weekly recap: {e}")
            return {}

    async def generate_weekly_recap_markdown(self) -> str:
        """
        Generate a formatted markdown weekly briefing.

        Returns:
            Markdown-formatted briefing text
        """
        recap = await self.generate_weekly_recap()

        md = f"""# AI Evolution Weekly Briefing

**Generated:** {recap.get('generated_at', '')}
**Period:** {recap.get('period', '')}

## Executive Summary

- **Total Findings:** {recap.get('summary', {}).get('total_findings', 0)}
- **Pending Review:** {recap.get('summary', {}).get('pending_review', 0)}
- **Approved:** {recap.get('summary', {}).get('approved', 0)}
- **Rejected:** {recap.get('summary', {}).get('rejected', 0)}

## Critical Items (Priority ≥ 0.8)

"""
        for item in recap.get('critical_items', []):
            md += f"""### {item.get('feature_name', '')}

**Source:** {item.get('source', '')}
**Priority:** {item.get('priority_score', 0):.1%}
**Difficulty:** {item.get('difficulty', 'unknown')}
**Action:** {item.get('action', '')}

{item.get('summary', '')[:200]}...

---

"""

        # Add high priority section
        md += f"""## High Priority Items (0.6 - 0.8)

"""
        for item in recap.get('high_priority', [])[:5]:
            md += f"""- **{item.get('feature_name', '')}** ({item.get('source', '')}) - {item.get('priority_score', 0):.1%} priority\n"""

        # Add categories section
        md += f"""

## Findings by Category

"""
        for category, count in recap.get('by_category', {}).items():
            md += f"- {category}: {count} findings\n"

        # Add urgency section
        md += f"""

## Findings by Urgency

"""
        for urgency, count in recap.get('by_urgency', {}).items():
            md += f"- {urgency}: {count} findings\n"

        return md

    def _format_proposal_for_recap(self, proposal: dict) -> dict:
        """Format proposal for recap display."""
        return {
            "feature_name": proposal.get("feature_name", ""),
            "source": proposal.get("source", ""),
            "priority_score": proposal.get("priority_score", 0),
            "difficulty": proposal.get("recommended_action", "").split("-")[0].strip(),
            "action": proposal.get("recommended_action", ""),
            "summary": proposal.get("summary", ""),
            "alignment": proposal.get("philosophy_alignment", ""),
        }

    def _group_by_category(self, proposals: list[dict]) -> dict:
        """Group proposals by source category."""
        grouped = {}
        for proposal in proposals:
            # Try to extract category from summary or use default
            category = "Other"
            for cat in ["LLM", "Voice", "Image/Video", "Research", "Community"]:
                if cat.lower() in proposal.get("summary", "").lower():
                    category = cat
                    break

            grouped[category] = grouped.get(category, 0) + 1

        return grouped

    def _group_by_urgency(self, proposals: list[dict]) -> dict:
        """Group proposals by competitive urgency."""
        grouped = {}

        # Extract urgency from summary
        for proposal in proposals:
            summary = proposal.get("summary", "")
            if "Urgency: critical" in summary:
                urgency = "CRITICAL"
            elif "Urgency: high" in summary:
                urgency = "HIGH"
            elif "Urgency: medium" in summary:
                urgency = "MEDIUM"
            else:
                urgency = "LOW"

            grouped[urgency] = grouped.get(urgency, 0) + 1

        return grouped
