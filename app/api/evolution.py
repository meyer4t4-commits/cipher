"""
Evolution API endpoints - comprehensive AI evolution tracking and proposals.

Provides endpoints for:
- Scanning 100+ AI/tech sources
- Managing feature proposals
- Approving/rejecting proposals
- Generating weekly briefings
- Monitoring sources
"""

from datetime import datetime
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.core.logging import logger
from app.services.scanner.evolution_scanner import (
    EvolutionScanner,
    FeatureProposal,
    ImplementationDifficulty,
    CompetitiveUrgency,
    MonitoredSource,
    SourceCategory,
    SourceType,
)
from app.services.scanner.evolution_proposals import (
    EvolutionProposalGenerator,
    ImplementationPlan,
    DecisionStatus,
    PhilosophyAlignment,
)

router = APIRouter(prefix="/api/v1/evolution", tags=["evolution"])

# Global instances
_scanner: Optional[EvolutionScanner] = None
_generator: Optional[EvolutionProposalGenerator] = None


def get_scanner() -> EvolutionScanner:
    """Get or create evolution scanner."""
    global _scanner
    if _scanner is None:
        _scanner = EvolutionScanner()
    return _scanner


def get_generator() -> EvolutionProposalGenerator:
    """Get or create proposal generator."""
    global _generator
    if _generator is None:
        _generator = EvolutionProposalGenerator()
    return _generator


# Request/Response Models

class MonitoredSourceResponse(BaseModel):
    """Monitored source response model."""
    name: str
    url: str
    category: str
    source_type: str
    scan_interval_minutes: int
    enabled: bool
    last_scan: Optional[str] = None
    last_scan_count: int = 0


class AddSourceRequest(BaseModel):
    """Request to add a new source."""
    name: str
    url: str
    category: str
    source_type: str
    scan_interval_minutes: int = 120
    enabled: bool = True


class FeatureProposalResponse(BaseModel):
    """Feature proposal response model."""
    id: str
    source: str
    feature_name: str
    description: str
    relevance_score: float
    implementation_difficulty: str
    affected_components: list[str]
    competitive_urgency: str
    detected_at: str
    url: str


class CostEstimateResponse(BaseModel):
    """Cost estimate response."""
    estimated_tokens_per_request: int
    monthly_api_cost_estimate: float
    development_hours: int
    infrastructure_overhead: str
    notes: str


class ComponentImpactResponse(BaseModel):
    """Component impact response."""
    component_name: str
    breaking_changes: bool
    estimated_changes: int
    dependencies_affected: list[str]
    migration_required: bool
    risk_level: str


class ImplementationPlanResponse(BaseModel):
    """Implementation plan response."""
    proposal_id: str
    feature_name: str
    source: str
    summary: str
    philosophy_alignment: str
    cost_estimate: CostEstimateResponse
    component_impacts: list[ComponentImpactResponse]
    conflicts: list[str]
    estimated_timeline: str
    risk_factors: list[str]
    recommended_action: str
    priority_score: float
    decision_status: str
    approval_notes: str
    rejection_reason: str
    created_at: str
    decided_at: Optional[str] = None


class ProposalDecision(BaseModel):
    """Decision on a proposal."""
    approved: bool
    notes: str = ""


class EvolutionScanStatus(BaseModel):
    """Status of evolution scan."""
    scanning: bool
    proposals_found: int
    results_count: int
    last_scan: Optional[str] = None
    next_scan: Optional[str] = None


class ProposalSummary(BaseModel):
    """Summary of proposals by status."""
    total: int
    pending: int
    approved: int
    rejected: int
    deferred: int


class EvolutionStats(BaseModel):
    """Evolution system statistics."""
    total_sources: int
    enabled_sources: int
    total_proposals: int
    pending_proposals: int
    approved_proposals: int
    rejected_proposals: int
    average_priority_score: float
    sources_by_category: dict[str, int]


class WeeklyRecapResponse(BaseModel):
    """Weekly recap response."""
    generated_at: str
    period: str
    summary: dict
    critical_items: list[dict]
    high_priority: list[dict]
    medium_priority: list[dict]
    by_category: dict[str, int]
    by_urgency: dict[str, int]


# Endpoints

@router.get("/scan")
async def trigger_evolution_scan() -> EvolutionScanStatus:
    """
    Trigger a manual evolution scan of all sources.

    This will:
    1. Scan 100+ AI/tech sources in parallel
    2. Deduplicate and parse results
    3. Generate implementation proposals
    4. Save findings to disk

    Returns:
        Status of the scan
    """
    try:
        scanner = get_scanner()
        generator = get_generator()

        logger.info("Starting manual evolution scan")

        # Run the scan
        results = await scanner.scan(full_scan=True)

        # Generate proposals from results
        proposals = scanner.propose_features(results)

        # Generate implementation plans
        plan_count = 0
        for proposal in proposals:
            if proposal.relevance_score >= 0.35:  # All relevant features
                plan = await generator.generate_plan(proposal)
                await generator.save_proposal(plan)
                plan_count += 1

        logger.info(f"Evolution scan completed: {len(results)} results, {plan_count} proposals")

        return EvolutionScanStatus(
            scanning=False,
            proposals_found=plan_count,
            results_count=len(results),
            last_scan=datetime.utcnow().isoformat(),
        )

    except Exception as e:
        logger.error(f"Error during evolution scan: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/proposals", response_model=list[ImplementationPlanResponse])
async def list_proposals(
    status: Optional[str] = Query(None, description="Filter by status: pending, approved, rejected"),
    priority_min: Optional[float] = Query(None, description="Minimum priority score (0-1)"),
    category: Optional[str] = Query(None, description="Filter by category"),
) -> list[ImplementationPlanResponse]:
    """
    List feature proposals with optional filtering.

    Args:
        status: Filter by decision status
        priority_min: Minimum priority score threshold
        category: Filter by source category

    Returns:
        List of proposals matching criteria
    """
    try:
        generator = get_generator()
        all_proposals = await generator.get_all_proposals()

        # Apply filters
        filtered = all_proposals

        if status:
            filtered = [p for p in filtered if p.get("decision_status") == status]

        if priority_min is not None:
            filtered = [p for p in filtered if p.get("priority_score", 0) >= priority_min]

        if category:
            filtered = [
                p for p in filtered
                if any(cat.lower() in str(p.get("summary", "")).lower() for cat in [category])
            ]

        # Convert to response models
        responses = []
        for proposal_dict in filtered:
            try:
                responses.append(ImplementationPlanResponse(**proposal_dict))
            except Exception as e:
                logger.warning(f"Failed to parse proposal: {e}")
                continue

        logger.info(f"Retrieved {len(responses)} proposals")
        return responses

    except Exception as e:
        logger.error(f"Error listing proposals: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/proposals/{proposal_id}", response_model=ImplementationPlanResponse)
async def get_proposal(proposal_id: str) -> ImplementationPlanResponse:
    """
    Get a specific proposal by ID.

    Args:
        proposal_id: The proposal ID

    Returns:
        Implementation plan for the proposal
    """
    try:
        generator = get_generator()
        all_proposals = await generator.get_all_proposals()

        for proposal_dict in all_proposals:
            if proposal_dict.get("proposal_id") == proposal_id:
                return ImplementationPlanResponse(**proposal_dict)

        raise HTTPException(status_code=404, detail="Proposal not found")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting proposal: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/proposals/{proposal_id}/approve")
async def approve_proposal(
    proposal_id: str,
    decision: ProposalDecision,
) -> dict:
    """
    Approve a feature proposal for implementation.

    Args:
        proposal_id: The proposal ID
        decision: Approval decision with optional notes

    Returns:
        Confirmation of approval
    """
    try:
        generator = get_generator()
        await generator.record_decision(proposal_id, approved=True, notes=decision.notes)

        logger.info(f"Approved proposal: {proposal_id}")
        return {
            "status": "approved",
            "proposal_id": proposal_id,
            "approved_at": datetime.utcnow().isoformat(),
            "notes": decision.notes,
        }

    except Exception as e:
        logger.error(f"Error approving proposal: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/proposals/{proposal_id}/reject")
async def reject_proposal(
    proposal_id: str,
    decision: ProposalDecision,
) -> dict:
    """
    Reject a feature proposal.

    Args:
        proposal_id: The proposal ID
        decision: Rejection decision with reason in notes

    Returns:
        Confirmation of rejection
    """
    try:
        generator = get_generator()
        await generator.record_decision(proposal_id, approved=False, notes=decision.notes)

        logger.info(f"Rejected proposal: {proposal_id}")
        return {
            "status": "rejected",
            "proposal_id": proposal_id,
            "rejected_at": datetime.utcnow().isoformat(),
            "reason": decision.notes,
        }

    except Exception as e:
        logger.error(f"Error rejecting proposal: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history")
async def get_evolution_history() -> dict:
    """
    Get history of evolution decisions.

    Returns:
        History of all decisions
    """
    try:
        generator = get_generator()
        history = await generator.get_decisions_history()

        # Categorize by decision
        approved = [
            (k, v) for k, v in history.items() if v.get("approved")
        ]
        rejected = [
            (k, v) for k, v in history.items() if not v.get("approved")
        ]

        logger.info(f"Retrieved evolution history: {len(approved)} approved, {len(rejected)} rejected")

        return {
            "total_decisions": len(history),
            "approved_count": len(approved),
            "rejected_count": len(rejected),
            "approved": [
                {
                    "proposal_id": k,
                    "decided_at": v.get("decided_at"),
                    "notes": v.get("notes"),
                }
                for k, v in approved
            ],
            "rejected": [
                {
                    "proposal_id": k,
                    "decided_at": v.get("decided_at"),
                    "reason": v.get("notes"),
                }
                for k, v in rejected
            ],
        }

    except Exception as e:
        logger.error(f"Error getting history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/weekly-recap", response_model=WeeklyRecapResponse)
async def get_weekly_recap() -> WeeklyRecapResponse:
    """
    Get the latest weekly recap of AI evolution findings.

    Returns:
        Structured weekly briefing
    """
    try:
        generator = get_generator()
        recap = await generator.generate_weekly_recap()

        if not recap:
            raise HTTPException(status_code=404, detail="No recap generated")

        return WeeklyRecapResponse(**recap)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting weekly recap: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/weekly-recap/markdown")
async def get_weekly_recap_markdown() -> dict:
    """
    Get the latest weekly recap as formatted markdown.

    Returns:
        Markdown-formatted briefing
    """
    try:
        generator = get_generator()
        markdown = await generator.generate_weekly_recap_markdown()

        return {
            "generated_at": datetime.utcnow().isoformat(),
            "format": "markdown",
            "content": markdown,
        }

    except Exception as e:
        logger.error(f"Error generating markdown recap: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sources", response_model=list[MonitoredSourceResponse])
async def list_sources() -> list[MonitoredSourceResponse]:
    """
    List all monitored sources.

    Returns:
        List of monitored sources with metadata
    """
    try:
        scanner = get_scanner()

        responses = []
        for source in scanner.sources:
            responses.append(MonitoredSourceResponse(**source.to_dict()))

        logger.info(f"Retrieved {len(responses)} monitored sources")
        return responses

    except Exception as e:
        logger.error(f"Error listing sources: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sources", response_model=MonitoredSourceResponse)
async def add_source(request: AddSourceRequest) -> MonitoredSourceResponse:
    """
    Add a new source to monitor.

    Args:
        request: Source details

    Returns:
        Created source
    """
    try:
        scanner = get_scanner()

        # Validate category and type
        try:
            category = SourceCategory(request.category)
            source_type = SourceType(request.source_type)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid category or type: {e}")

        # Create source
        source = MonitoredSource(
            name=request.name,
            url=request.url,
            category=category,
            source_type=source_type,
            scan_interval_minutes=request.scan_interval_minutes,
            enabled=request.enabled,
        )

        scanner.sources.append(source)
        await scanner.save_sources()

        logger.info(f"Added new source: {request.name}")
        return MonitoredSourceResponse(**source.to_dict())

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding source: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/sources/{source_name}")
async def remove_source(source_name: str) -> dict:
    """
    Remove a source from monitoring.

    Args:
        source_name: Name of source to remove

    Returns:
        Confirmation of removal
    """
    try:
        scanner = get_scanner()

        # Find and remove source
        original_count = len(scanner.sources)
        scanner.sources = [s for s in scanner.sources if s.name != source_name]

        if len(scanner.sources) == original_count:
            raise HTTPException(status_code=404, detail=f"Source not found: {source_name}")

        await scanner.save_sources()

        logger.info(f"Removed source: {source_name}")
        return {
            "status": "removed",
            "source_name": source_name,
            "remaining_sources": len(scanner.sources),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing source: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats", response_model=EvolutionStats)
async def get_evolution_stats() -> EvolutionStats:
    """
    Get comprehensive evolution system statistics.

    Returns:
        System statistics and metrics
    """
    try:
        scanner = get_scanner()
        generator = get_generator()

        all_proposals = await generator.get_all_proposals()
        pending = [p for p in all_proposals if p.get("decision_status") == "pending"]
        approved = [p for p in all_proposals if p.get("decision_status") == "approved"]
        rejected = [p for p in all_proposals if p.get("decision_status") == "rejected"]

        # Calculate average priority
        avg_priority = (
            sum(p.get("priority_score", 0) for p in all_proposals) / len(all_proposals)
            if all_proposals else 0.0
        )

        # Count sources by category
        sources_by_cat = {}
        for source in scanner.sources:
            cat = source.category.value
            sources_by_cat[cat] = sources_by_cat.get(cat, 0) + 1

        return EvolutionStats(
            total_sources=len(scanner.sources),
            enabled_sources=sum(1 for s in scanner.sources if s.enabled),
            total_proposals=len(all_proposals),
            pending_proposals=len(pending),
            approved_proposals=len(approved),
            rejected_proposals=len(rejected),
            average_priority_score=avg_priority,
            sources_by_category=sources_by_cat,
        )

    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status", response_model=EvolutionScanStatus)
async def get_evolution_status() -> EvolutionScanStatus:
    """
    Get current evolution scanner status.

    Returns:
        Current status of evolution tracking system
    """
    try:
        generator = get_generator()
        pending = await generator.get_pending_proposals()

        return EvolutionScanStatus(
            scanning=False,
            proposals_found=len(pending),
            results_count=0,
            last_scan=None,
        )

    except Exception as e:
        logger.error(f"Error getting status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def evolution_health() -> dict:
    """
    Check evolution system health and connectivity.

    Returns:
        Health status
    """
    try:
        scanner = get_scanner()
        generator = get_generator()
        pending = await generator.get_pending_proposals()

        return {
            "healthy": True,
            "scanner_active": True,
            "data_dir": str(generator.data_dir),
            "proposals_pending": len(pending),
            "sources_monitored": len(scanner.sources),
            "sources_enabled": sum(1 for s in scanner.sources if s.enabled),
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error checking health: {e}")
        return {
            "healthy": False,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
        }
