"""
Pydantic models for the agent execution framework.
Defines task, result, capability, signal, and status structures.

Architecture inspired by multi-agent consensus systems:
- Each agent produces a typed AgentSignal with confidence scoring
- Signals can be aggregated for multi-agent consensus decisions
- Risk validation gates check signals before execution
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class AgentStatus(str, Enum):
    """Execution status of an agent task."""
    PENDING = "pending"
    AWAITING_APPROVAL = "awaiting_approval"
    RUNNING = "running"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"


class SignalDirection(str, Enum):
    """Direction of an agent's signal (action recommendation)."""
    EXECUTE = "execute"       # Proceed with the action
    HOLD = "hold"             # Wait / gather more info before acting
    ABORT = "abort"           # Do not proceed — risk too high
    DELEGATE = "delegate"     # Route to a different agent


class RiskLevel(str, Enum):
    """Risk classification for agent actions."""
    LOW = "low"               # Safe to auto-execute
    MEDIUM = "medium"         # Execute with logging
    HIGH = "high"             # Requires confirmation or validation
    CRITICAL = "critical"     # Never auto-execute — always confirm


class AgentSignal(BaseModel):
    """
    Structured output from an agent's analysis — inspired by ai-hedge-fund's
    typed signal pattern (WarrenBuffettSignal, etc.).

    Every agent can produce a signal with confidence scoring, reasoning chain,
    and risk assessment. Signals can be aggregated across multiple agents
    for consensus-based decisions.
    """
    agent_name: str = Field(..., description="Which agent produced this signal")
    signal: SignalDirection = Field(default=SignalDirection.EXECUTE, description="Recommended action direction")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="Confidence in this signal (0.0-1.0)")
    reasoning: str = Field(default="", description="Chain-of-thought reasoning behind the signal")
    data: dict[str, Any] = Field(default_factory=dict, description="Structured data payload from the agent")
    risk_level: RiskLevel = Field(default=RiskLevel.LOW, description="Risk classification of the recommended action")
    sources: list[str] = Field(default_factory=list, description="Data sources used (URLs, APIs, databases)")
    warnings: list[str] = Field(default_factory=list, description="Caveats or concerns about this signal")
    suggested_followup: list[str] = Field(default_factory=list, description="Recommended next agents or actions")

    @property
    def is_high_confidence(self) -> bool:
        return self.confidence >= 0.8

    @property
    def is_actionable(self) -> bool:
        return self.signal == SignalDirection.EXECUTE and self.confidence >= 0.5


class ConsensusResult(BaseModel):
    """
    Aggregated result from multiple agent signals — inspired by ai-hedge-fund's
    portfolio manager pattern that weighs multiple analyst signals.
    """
    signals: list[AgentSignal] = Field(default_factory=list, description="All individual agent signals")
    consensus_direction: SignalDirection = Field(default=SignalDirection.HOLD, description="Weighted consensus direction")
    consensus_confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Confidence-weighted consensus score")
    reasoning: str = Field(default="", description="Synthesis of all agent reasoning")
    risk_level: RiskLevel = Field(default=RiskLevel.MEDIUM, description="Highest risk level from any signal")
    dissenting_agents: list[str] = Field(default_factory=list, description="Agents that disagreed with consensus")

    @classmethod
    def from_signals(cls, signals: list[AgentSignal]) -> "ConsensusResult":
        """
        Aggregate multiple agent signals into a consensus using confidence-weighted voting.
        Higher-confidence signals have more influence on the final decision.
        """
        if not signals:
            return cls(reasoning="No agent signals to aggregate")

        # Confidence-weighted voting
        direction_scores: dict[SignalDirection, float] = {}
        total_weight = 0.0
        for sig in signals:
            weight = sig.confidence
            direction_scores[sig.signal] = direction_scores.get(sig.signal, 0.0) + weight
            total_weight += weight

        # Winner takes all
        consensus_dir = max(direction_scores, key=direction_scores.get) if direction_scores else SignalDirection.HOLD
        consensus_conf = direction_scores.get(consensus_dir, 0.0) / total_weight if total_weight > 0 else 0.0

        # Highest risk from any signal (conservative)
        risk_order = [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL]
        max_risk = max(signals, key=lambda s: risk_order.index(s.risk_level)).risk_level

        # Identify dissent
        dissenting = [s.agent_name for s in signals if s.signal != consensus_dir]

        # Synthesize reasoning
        reasoning_parts = [f"[{s.agent_name}] ({s.confidence:.0%} conf): {s.reasoning}" for s in signals if s.reasoning]
        synthesis = " | ".join(reasoning_parts) if reasoning_parts else "No reasoning provided"

        return cls(
            signals=signals,
            consensus_direction=consensus_dir,
            consensus_confidence=round(consensus_conf, 3),
            reasoning=synthesis,
            risk_level=max_risk,
            dissenting_agents=dissenting,
        )


class AgentCapability(BaseModel):
    """Describes a capability that an agent can perform."""
    name: str = Field(..., description="Capability name (e.g., 'execute_shell')")
    description: str = Field(..., description="Human-readable description")
    category: str = Field(..., description="Category (e.g., 'execution', 'data', 'communication')")
    requires_approval: bool = Field(default=False, description="Whether this capability requires operator approval")
    timeout_seconds: int = Field(default=30, description="Default timeout for this capability")


class AgentTask(BaseModel):
    """A task to be executed by an agent."""
    task_id: str = Field(default_factory=lambda: __import__('uuid').uuid4().hex, description="Unique task ID")
    agent_name: str = Field(..., description="Name of the agent to execute (e.g., 'shell_agent')")
    instruction: str = Field(..., description="What the agent should do")
    params: dict[str, Any] = Field(default_factory=dict, description="Parameters for the task")
    timeout_seconds: int = Field(default=30, description="Task timeout in seconds")
    requires_approval: bool = Field(default=False, description="Whether this task needs operator approval")
    priority: int = Field(default=0, description="Task priority (higher = more important)")
    requested_at: datetime = Field(default_factory=lambda: datetime.utcnow())
    approved_at: Optional[datetime] = Field(default=None, description="When task was approved")
    approved_by: Optional[str] = Field(default=None, description="Who approved the task")

    class Config:
        json_schema_extra = {
            "example": {
                "task_id": "abc123",
                "agent_name": "shell_agent",
                "instruction": "List files in the project directory",
                "params": {"command": "ls -la ~/project"},
                "timeout_seconds": 30,
                "requires_approval": False,
                "priority": 0,
            }
        }


class AgentResult(BaseModel):
    """Result of an agent task execution."""
    task_id: str = Field(..., description="ID of the task that was executed")
    agent_name: str = Field(..., description="Name of the agent that executed it")
    success: bool = Field(..., description="Whether the task succeeded")
    output: Any = Field(default=None, description="Task output/result")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    execution_time_ms: float = Field(default=0.0, description="How long the task took to execute")
    verified: bool = Field(default=False, description="Whether the output was verified by the agent")
    verification_notes: Optional[str] = Field(default=None, description="Notes from verification step")
    signal: Optional[AgentSignal] = Field(default=None, description="Structured signal from the agent (confidence, reasoning, risk)")
    started_at: datetime = Field(default_factory=lambda: datetime.utcnow())
    completed_at: datetime = Field(default_factory=lambda: datetime.utcnow())

    class Config:
        json_schema_extra = {
            "example": {
                "task_id": "abc123",
                "agent_name": "shell_agent",
                "success": True,
                "output": "file1.txt\nfile2.txt\n",
                "error": None,
                "execution_time_ms": 125.5,
                "verified": True,
                "verification_notes": "Output matches expected command format",
            }
        }


class AgentTaskRequest(BaseModel):
    """API request to execute a task."""
    agent_name: str = Field(..., description="Name of the agent to use")
    instruction: str = Field(..., description="What to do")
    params: dict[str, Any] = Field(default_factory=dict, description="Task parameters")
    timeout_seconds: int = Field(default=30, ge=1, le=3600, description="Timeout in seconds")
    priority: int = Field(default=0, description="Task priority")


class ApprovalRequest(BaseModel):
    """Request to approve a pending task."""
    approved_by: str = Field(..., description="Username/ID of approver")
    notes: Optional[str] = Field(default=None, description="Optional approval notes")


class ExecutionHistoryEntry(BaseModel):
    """A single entry in the execution history."""
    task_id: str
    agent_name: str
    instruction: str
    status: AgentStatus
    success: Optional[bool]
    execution_time_ms: Optional[float]
    created_at: datetime
    completed_at: Optional[datetime]
    error: Optional[str]
