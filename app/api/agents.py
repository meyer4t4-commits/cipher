"""
Agent API endpoints - Task execution, management, and status.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.agents import (
    AgentResult,
    AgentTask,
    AgentTaskRequest,
    ApprovalRequest,
    get_executor,
    get_registry,
)
from app.agents.skills import (
    AnalystAgent,
    ApexArchitectAgent,
    ArchivistAgent,
    BraveSearchAgent,
    ChronosAgent,
    CommunicationAgent,
    CodeAgent,
    DataAgent,
    DealFlowAgent,
    DeployAgent,
    FileAgent,
    ImageAgent,
    LegalAgent,
    MarketPulseAgent,
    MonitorAgent,
    NeighborhoodGrowthAgent,
    OutreachAgent,
    ProfitabilityAnalystAgent,
    ProvisioningAgent,
    ResearchAgent,
    SchedulerAgent,
    ScoutAgent,
    SentinelAgent,
    ShellAgent,
    SkillCreatorAgent,
    SynthesisAgent,
    TradingAgent,
    VideoAgent,
    WebAgent,
)
from app.core.logging import logger
from app.db.database import get_db

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])

# Initialize agents (called once on app startup)
_agents_initialized = False


def _init_agents():
    """Initialize and register all agents."""
    global _agents_initialized
    if _agents_initialized:
        return

    registry = get_registry()

    # Register all skill agents
    agents = [
        ShellAgent(),
        WebAgent(),
        CodeAgent(),
        FileAgent(),
        TradingAgent(paper_trading=True),
        DeployAgent(),
        ResearchAgent(),
        CommunicationAgent(),
        SchedulerAgent(),
        DataAgent(),
        MonitorAgent(),
        SkillCreatorAgent(),
        BraveSearchAgent(),
        ImageAgent(),
        VideoAgent(),
        LegalAgent(),
        ApexArchitectAgent(),
        ScoutAgent(),
        AnalystAgent(),
        OutreachAgent(),
        ProvisioningAgent(),
        MarketPulseAgent(),
        ProfitabilityAnalystAgent(),
        NeighborhoodGrowthAgent(),
        DealFlowAgent(),
        ChronosAgent(),
        ArchivistAgent(),
        SentinelAgent(),
        SynthesisAgent(),
    ]

    for agent in agents:
        try:
            registry.register(agent)
            logger.info(f"Registered agent: {agent.name}")
        except ValueError as e:
            logger.warning(f"Agent already registered: {e}")

    _agents_initialized = True
    logger.info(f"Agent framework initialized with {len(agents)} agents")


@router.on_event("startup")
async def startup_event():
    """Initialize agents on startup."""
    _init_agents()


@router.post("/execute", response_model=AgentResult)
async def execute_task(
    request: AgentTaskRequest,
    db: Session = Depends(get_db),
) -> AgentResult:
    """
    Submit a task for execution by an agent.

    Args:
        request: Task request details
        db: Database session

    Returns:
        AgentResult with execution details
    """
    _init_agents()

    registry = get_registry()
    executor = get_executor()

    # Check if agent exists
    if not registry.is_registered(request.agent_name):
        logger.warning(f"Task execution requested for unknown agent: {request.agent_name}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{request.agent_name}' not found",
        )

    # Create task
    task = AgentTask(
        agent_name=request.agent_name,
        instruction=request.instruction,
        params=request.params,
        timeout_seconds=request.timeout_seconds,
        priority=request.priority,
    )

    # Check if agent requires approval
    agent = registry.get_agent(request.agent_name)
    if agent.requires_approval_for(request.instruction):
        task.requires_approval = True
        logger.info(f"Task {task.task_id} requires approval")

    # Execute the task
    result = await executor.execute(task, db)

    logger.info(f"Task {task.task_id} completed: success={result.success}, verified={result.verified}")

    return result


@router.get("/capabilities")
async def list_capabilities():
    """
    Get list of all agent capabilities.

    Returns:
        List of capabilities with descriptions
    """
    _init_agents()
    registry = get_registry()
    return {
        "agents": registry.count(),
        "capabilities": registry.list_capabilities(),
    }


@router.get("/agents")
async def list_agents():
    """
    Get list of all registered agents.

    Returns:
        Detailed information about each agent
    """
    _init_agents()
    registry = get_registry()
    return {
        "agents": registry.list_agents_detailed(),
        "total": registry.count(),
    }


@router.get("/capabilities/{category}")
async def list_capabilities_by_category(category: str):
    """
    Get capabilities filtered by category.

    Args:
        category: Capability category (e.g., 'data', 'execution', 'communication')

    Returns:
        Capabilities in that category
    """
    _init_agents()
    registry = get_registry()
    return {
        "category": category,
        "capabilities": registry.list_capabilities_by_category(category),
    }


@router.get("/status/{task_id}")
async def get_task_status(task_id: str):
    """
    Get the status and result of a task.

    Args:
        task_id: ID of the task to check

    Returns:
        Task result or error if not found
    """
    _init_agents()
    executor = get_executor()

    result = executor.get_task_status(task_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found",
        )

    return result.model_dump()


@router.get("/history")
async def get_execution_history(limit: int = 100):
    """
    Get recent execution history.

    Args:
        limit: Maximum number of entries to return

    Returns:
        List of recent task executions
    """
    _init_agents()
    executor = get_executor()

    history = executor.get_execution_history(limit)
    return {
        "total": len(history),
        "entries": [entry.model_dump() for entry in history],
    }


@router.get("/approvals")
async def get_pending_approvals():
    """
    Get all tasks awaiting approval.

    Returns:
        List of pending approval tasks
    """
    _init_agents()
    executor = get_executor()

    return {
        "pending": len(executor._pending_approvals),
        "tasks": executor.get_pending_approvals(),
    }


@router.post("/approve/{task_id}")
async def approve_task(
    task_id: str,
    request: ApprovalRequest,
) -> dict:
    """
    Approve a pending task.

    Args:
        task_id: ID of task to approve
        request: Approval details (who approved and optional notes)

    Returns:
        Approval confirmation
    """
    _init_agents()
    executor = get_executor()

    if not executor.approve_task(task_id, request.approved_by, request.notes):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found or not pending approval",
        )

    logger.info(f"Task {task_id} approved by {request.approved_by}")

    return {
        "task_id": task_id,
        "approved": True,
        "approved_by": request.approved_by,
    }


@router.post("/reject/{task_id}")
async def reject_task(
    task_id: str,
    approved_by: str,
    reason: str = "User request",
) -> dict:
    """
    Reject a pending task.

    Args:
        task_id: ID of task to reject
        approved_by: Who rejected it
        reason: Reason for rejection

    Returns:
        Rejection confirmation
    """
    _init_agents()
    executor = get_executor()

    if not executor.reject_task(task_id, approved_by, reason):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found or not pending approval",
        )

    logger.info(f"Task {task_id} rejected: {reason}")

    return {
        "task_id": task_id,
        "rejected": True,
        "rejected_by": approved_by,
        "reason": reason,
    }


@router.get("/status")
async def get_executor_status():
    """
    Get overall executor status.

    Returns:
        Current executor state
    """
    _init_agents()
    executor = get_executor()
    registry = get_registry()

    return {
        "executor": {
            "max_concurrent": executor.max_concurrent_tasks,
            "pending_approvals": len(executor._pending_approvals),
            "history_entries": len(executor._execution_history),
        },
        "registry": {
            "agents": registry.count(),
            "agent_names": registry.list_agents(),
        },
    }


@router.post("/batch")
async def execute_batch(
    requests: list[AgentTaskRequest],
    db: Session = Depends(get_db),
):
    """
    Execute multiple tasks concurrently.

    Args:
        requests: List of task requests
        db: Database session

    Returns:
        List of results in same order as requests
    """
    _init_agents()

    registry = get_registry()
    executor = get_executor()

    # Verify all agents exist
    for req in requests:
        if not registry.is_registered(req.agent_name):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent '{req.agent_name}' not found",
            )

    # Create tasks
    tasks = [
        AgentTask(
            agent_name=req.agent_name,
            instruction=req.instruction,
            params=req.params,
            timeout_seconds=req.timeout_seconds,
            priority=req.priority,
        )
        for req in requests
    ]

    # Execute concurrently
    results = await executor.execute_many(tasks, db)

    return {
        "total": len(results),
        "results": [r.model_dump() for r in results],
    }


@router.delete("/history")
async def clear_history():
    """
    Clear execution history. Use with caution!

    Returns:
        Number of entries cleared
    """
    _init_agents()
    executor = get_executor()

    count = executor.clear_history()

    logger.warning(f"Execution history cleared: {count} entries removed")

    return {
        "cleared": count,
        "message": "Execution history has been cleared",
    }
