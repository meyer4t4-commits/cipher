"""
Model management API - inspect and test available LLM providers.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import UsageLog
from app.models.schemas import ModelTier
from app.services.llm_router import MODEL_MAP, check_model_availability, get_provider

router = APIRouter(prefix="/models", tags=["models"])


@router.get("/")
async def list_models():
    """List all configured models and their routing tiers."""
    models = []
    for tier, model_id in MODEL_MAP.items():
        models.append({
            "tier": tier.value,
            "model_id": model_id,
            "provider": get_provider(model_id),
        })
    return {"models": models}


@router.get("/available")
async def get_available_models():
    """Return the active model for each major tier (default, fast, reasoning).
    Used by the web dashboard to display current model configuration."""
    return {
        "default_model": MODEL_MAP.get(ModelTier.DEFAULT, "unknown"),
        "fast_model": MODEL_MAP.get(ModelTier.FAST, "unknown"),
        "reasoning_model": MODEL_MAP.get(ModelTier.REASONING, "unknown"),
    }


@router.get("/health")
async def check_health():
    """Test connectivity to all configured LLM providers."""
    results = await check_model_availability()
    return {"models": results}


@router.get("/usage")
async def get_usage(days: int = 30, db: Session = Depends(get_db)):
    """Get usage statistics across all models."""
    from datetime import datetime, timedelta, timezone

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    stats = (
        db.query(
            UsageLog.model,
            UsageLog.provider,
            func.count(UsageLog.id).label("request_count"),
            func.sum(UsageLog.total_tokens).label("total_tokens"),
            func.sum(UsageLog.cost_usd).label("total_cost"),
            func.avg(UsageLog.latency_ms).label("avg_latency_ms"),
        )
        .filter(UsageLog.created_at >= cutoff)
        .group_by(UsageLog.model, UsageLog.provider)
        .all()
    )

    return {
        "period_days": days,
        "models": [
            {
                "model": s.model,
                "provider": s.provider,
                "request_count": s.request_count,
                "total_tokens": s.total_tokens or 0,
                "total_cost_usd": round(s.total_cost or 0, 4),
                "avg_latency_ms": round(s.avg_latency_ms or 0, 1),
            }
            for s in stats
        ],
    }
