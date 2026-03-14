"""
Telemetry — Lightweight, non-blocking performance tracking for Cipher.

Logs every agent/tool invocation to the database so Cipher can learn:
- Which agents fail most?
- What's slow?
- What does Mark use most?
- What's the cost distribution?

All writes are fire-and-forget. A failed telemetry write never blocks
the user response or causes an error.
"""

import asyncio
from datetime import datetime, timezone

from app.core.logging import logger


def log_telemetry(
    agent_or_tool: str,
    operation: str = "",
    success: bool = True,
    latency_ms: float = 0.0,
    error_message: str = "",
    query_snippet: str = "",
    model_used: str = "",
    tokens_used: int = 0,
    cost_usd: float = 0.0,
):
    """
    Fire-and-forget telemetry log. Never blocks, never throws.

    Usage:
        log_telemetry("self_improvement_agent", "audit", success=True, latency_ms=1234)
        log_telemetry("brave_search", "web_search", success=False, error_message="timeout")
    """
    try:
        asyncio.ensure_future(_persist_telemetry(
            agent_or_tool=agent_or_tool,
            operation=operation,
            success=success,
            latency_ms=latency_ms,
            error_message=error_message[:500] if error_message else "",
            query_snippet=query_snippet[:300] if query_snippet else "",
            model_used=model_used,
            tokens_used=tokens_used,
            cost_usd=cost_usd,
        ))
    except Exception:
        pass  # Never let telemetry break anything


async def _persist_telemetry(**kwargs):
    """Write telemetry to database (best-effort)."""
    try:
        from app.db.database import SessionLocal
        from app.db.models import TelemetryLog

        db = SessionLocal()
        record = TelemetryLog(**kwargs)
        db.add(record)
        db.commit()
        db.close()
    except Exception as e:
        logger.debug(f"Telemetry write failed (non-fatal): {e}")


async def get_telemetry_summary(hours: int = 24) -> dict:
    """Get telemetry summary for the last N hours. Used by self-improvement agent."""
    try:
        from sqlalchemy import func, text
        from app.db.database import SessionLocal
        from app.db.models import TelemetryLog

        db = SessionLocal()

        # Total requests
        total = db.query(func.count(TelemetryLog.id)).scalar() or 0

        # Success rate
        successes = db.query(func.count(TelemetryLog.id)).filter(
            TelemetryLog.success == True  # noqa: E712
        ).scalar() or 0

        # Top agents by usage
        top_agents = db.query(
            TelemetryLog.agent_or_tool,
            func.count(TelemetryLog.id).label("count"),
        ).group_by(TelemetryLog.agent_or_tool).order_by(
            func.count(TelemetryLog.id).desc()
        ).limit(10).all()

        # Top failing agents
        top_failures = db.query(
            TelemetryLog.agent_or_tool,
            func.count(TelemetryLog.id).label("count"),
        ).filter(
            TelemetryLog.success == False  # noqa: E712
        ).group_by(TelemetryLog.agent_or_tool).order_by(
            func.count(TelemetryLog.id).desc()
        ).limit(5).all()

        # Avg latency by agent
        avg_latency = db.query(
            TelemetryLog.agent_or_tool,
            func.avg(TelemetryLog.latency_ms).label("avg_ms"),
        ).group_by(TelemetryLog.agent_or_tool).order_by(
            func.avg(TelemetryLog.latency_ms).desc()
        ).limit(10).all()

        db.close()

        return {
            "total_requests": total,
            "success_rate": round(successes / total, 3) if total > 0 else 0.0,
            "top_agents": [{"agent": a, "count": c} for a, c in top_agents],
            "top_failures": [{"agent": a, "count": c} for a, c in top_failures],
            "avg_latency": [{"agent": a, "avg_ms": round(m, 1)} for a, m in avg_latency],
        }
    except Exception as e:
        logger.debug(f"Telemetry summary failed: {e}")
        return {"error": str(e)}
