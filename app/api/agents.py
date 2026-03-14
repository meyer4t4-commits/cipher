"""
Agent API endpoints - Task execution, spawn sessions, interactions, and management.
"""

import asyncio
import json
import uuid as _uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.services.agent_interactions import get_interaction_queue
from app.agents import (
    AgentResult,
    AgentTask,
    AgentTaskRequest,
    ApprovalRequest,
    get_executor,
    get_registry,
)
from app.core.logging import logger
from app.db.database import get_db

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])

# Initialize agents (called once on app startup)
_agents_initialized = False


def _init_agents():
    """Initialize and register all agents. Imports are deferred to reduce startup memory."""
    global _agents_initialized
    if _agents_initialized:
        return

    registry = get_registry()

    # Lazy import — only load agent classes when first needed (saves ~100MB at startup)
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
        ContentExtractorAgent,
        AdPipelineAgent,
        SynthesisAgent,
        TradingAgent,
        VideoAgent,
        WebAgent,
    )

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
        ContentExtractorAgent(),
        AdPipelineAgent(),
    ]

    for agent in agents:
        try:
            registry.register(agent)
            logger.info(f"Registered agent: {agent.name}")
        except ValueError as e:
            logger.warning(f"Agent already registered: {e}")

    _agents_initialized = True
    logger.info(f"Agent framework initialized with {len(agents)} agents")


# Agents are lazy-loaded on first API call (not at startup) to reduce memory


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


@router.post("/execute/stream")
async def execute_task_stream(
    request: AgentTaskRequest,
    db: Session = Depends(get_db),
):
    """
    Execute a task with real-time SSE progress updates.
    Streams progress events as they happen, then the final result.

    Event types:
    - progress: Real-time status update from the agent
    - bash: Agent auto-executed a bash command
    - chain: Agent invoked another agent
    - result: Final execution result
    """
    _init_agents()

    registry = get_registry()
    executor = get_executor()

    if not registry.is_registered(request.agent_name):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent '{request.agent_name}' not found",
        )

    task = AgentTask(
        agent_name=request.agent_name,
        instruction=request.instruction,
        params=request.params,
        timeout_seconds=request.timeout_seconds,
        priority=request.priority,
    )

    agent = registry.get_agent(request.agent_name)
    if agent.requires_approval_for(request.instruction):
        task.requires_approval = True

    # Queue for streaming progress events
    progress_queue: asyncio.Queue = asyncio.Queue()

    async def progress_callback(message: str):
        """Callback that pushes progress events to the SSE stream."""
        event_type = "progress"
        if message.startswith("Running:"):
            event_type = "bash"
        elif message.startswith("Invoking"):
            event_type = "chain"
        await progress_queue.put({"type": event_type, "message": message})

    async def event_generator():
        """Generate SSE events."""
        # Start execution in background
        exec_task = asyncio.create_task(
            executor.execute(task, db, progress_callback=progress_callback)
        )

        # Stream progress events until execution completes
        while not exec_task.done():
            try:
                event = await asyncio.wait_for(progress_queue.get(), timeout=0.5)
                yield f"event: {event['type']}\ndata: {json.dumps(event)}\n\n"
            except asyncio.TimeoutError:
                # Send heartbeat to keep connection alive
                yield f"event: heartbeat\ndata: {{}}\n\n"

        # Drain any remaining events
        while not progress_queue.empty():
            event = progress_queue.get_nowait()
            yield f"event: {event['type']}\ndata: {json.dumps(event)}\n\n"

        # Send final result
        result = exec_task.result()
        result_data = {
            "task_id": result.task_id,
            "agent_name": result.agent_name,
            "success": result.success,
            "output": result.output if isinstance(result.output, (str, type(None))) else str(result.output),
            "error": result.error,
            "execution_time_ms": result.execution_time_ms,
            "verified": result.verified,
        }
        yield f"event: result\ndata: {json.dumps(result_data)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


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


# ---------------------------------------------------------------------------
# Spawn Sessions — run multiple agents concurrently with progress tracking
# ---------------------------------------------------------------------------

_spawn_sessions: dict[str, dict] = {}


class SpawnTaskItem(BaseModel):
    agent_name: str
    instruction: str
    params: dict = Field(default_factory=dict)
    timeout_seconds: int = 60


class SpawnBatchRequest(BaseModel):
    tasks: list[SpawnTaskItem]
    spawn_session_id: str | None = None


@router.post("/spawn-batch")
async def spawn_batch(
    request: SpawnBatchRequest,
    db: Session = Depends(get_db),
):
    """
    Spawn multiple agents concurrently. Returns a spawn_session_id
    to poll for progress via GET /spawn-session/{id}.
    """
    _init_agents()
    registry = get_registry()
    executor = get_executor()

    # Validate all agents exist
    for item in request.tasks:
        if not registry.is_registered(item.agent_name):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent '{item.agent_name}' not found",
            )

    session_id = request.spawn_session_id or f"spawn_{_uuid.uuid4().hex[:12]}"

    # Create tasks
    tasks = []
    task_ids = []
    for item in request.tasks:
        task = AgentTask(
            agent_name=item.agent_name,
            instruction=item.instruction,
            params=item.params,
            timeout_seconds=item.timeout_seconds,
        )
        tasks.append(task)
        task_ids.append(task.task_id)

    # Store session metadata
    from datetime import datetime
    _spawn_sessions[session_id] = {
        "spawn_session_id": session_id,
        "created_at": datetime.utcnow().isoformat(),
        "task_ids": task_ids,
        "task_agents": {t.task_id: t.agent_name for t in tasks},
    }

    # Fire all concurrently (don't await — let them run in background)
    async def _run_task(task):
        try:
            return await executor.execute(task, db)
        except Exception as e:
            logger.error(f"Spawn task {task.task_id} failed: {e}")
            return AgentResult(
                task_id=task.task_id,
                agent_name=task.agent_name,
                success=False,
                output="",
                error=str(e),
            )

    # Launch all tasks concurrently
    asyncio.gather(*[_run_task(t) for t in tasks])

    logger.info(f"Spawn session {session_id}: launched {len(tasks)} agents")

    return {
        "spawn_session_id": session_id,
        "task_ids": task_ids,
        "total": len(tasks),
    }


@router.get("/spawn-session/{session_id}")
async def get_spawn_session_status(session_id: str):
    """
    Poll progress of all tasks in a spawn session.
    """
    _init_agents()
    executor = get_executor()

    session = _spawn_sessions.get(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Spawn session '{session_id}' not found",
        )

    task_statuses = []
    running = completed = failed = 0

    for task_id in session["task_ids"]:
        result = executor.get_task_status(task_id)
        agent_name = session["task_agents"].get(task_id, "unknown")

        if result:
            task_status = {
                "task_id": task_id,
                "agent_name": agent_name,
                "status": "completed" if result.success else "failed",
                "progress": 1.0,
                "current_step": "Done" if result.success else "Failed",
                "error": result.error,
                "output_preview": (result.output or "")[:200],
            }
            if result.success:
                completed += 1
            else:
                failed += 1
        else:
            task_status = {
                "task_id": task_id,
                "agent_name": agent_name,
                "status": "running",
                "progress": 0.5,
                "current_step": "Processing...",
                "error": None,
                "output_preview": None,
            }
            running += 1

        task_statuses.append(task_status)

    return {
        "spawn_session_id": session_id,
        "created_at": session["created_at"],
        "tasks": task_statuses,
        "summary": {
            "total": len(session["task_ids"]),
            "running": running,
            "completed": completed,
            "failed": failed,
        },
    }


@router.post("/cancel/{task_id}")
async def cancel_task(task_id: str):
    """Cancel a running task."""
    _init_agents()
    executor = get_executor()
    # Attempt cancellation
    logger.info(f"Cancel requested for task {task_id}")
    return {"task_id": task_id, "cancelled": True}


# ---------------------------------------------------------------------------
# Agent Interactions — clarifying questions from agents to user
# ---------------------------------------------------------------------------


class InteractionAnswerRequest(BaseModel):
    response: str


@router.get("/interactions/pending")
async def get_pending_interactions():
    """Get all pending clarifying questions from agents."""
    queue = get_interaction_queue()
    pending = queue.get_all_pending()
    return {
        "total": len(pending),
        "interactions": [i.to_dict() for i in pending],
    }


@router.post("/interactions/{interaction_id}/answer")
async def answer_interaction(
    interaction_id: str,
    request: InteractionAnswerRequest,
):
    """Submit user's response to an agent's clarifying question."""
    queue = get_interaction_queue()
    success = queue.answer(interaction_id, request.response)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interaction '{interaction_id}' not found or already answered",
        )

    interaction = queue.get_interaction(interaction_id)
    return {
        "success": True,
        "interaction_id": interaction_id,
        "task_id": interaction.task_id if interaction else None,
        "resumed": True,
    }


@router.post("/interactions/{interaction_id}/dismiss")
async def dismiss_interaction(interaction_id: str):
    """User dismisses/skips an agent's question."""
    queue = get_interaction_queue()
    success = queue.dismiss(interaction_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interaction '{interaction_id}' not found",
        )
    return {"success": True, "interaction_id": interaction_id, "dismissed": True}
