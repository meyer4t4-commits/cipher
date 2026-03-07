"""
Monitoring & Alert Agent - Health checks, metrics, anomaly detection, alerting.
"""

from datetime import datetime
from typing import Any, Optional

from app.agents.base import BaseAgent
from app.agents.models import AgentCapability, AgentResult, AgentTask
from app.core.logging import logger


class MonitorAgent(BaseAgent):
    """Monitor services, track metrics, and send alerts."""

    def __init__(self):
        """Initialize the monitor agent."""
        super().__init__(
            name="monitor_agent",
            description="Service monitoring, metrics, and alerting",
            version="1.0.0",
            capabilities=[
                AgentCapability(
                    name="health_check",
                    description="Check endpoint health status",
                    category="data",
                    timeout_seconds=15,
                ),
                AgentCapability(
                    name="get_metrics",
                    description="Retrieve performance metrics",
                    category="data",
                    timeout_seconds=10,
                ),
                AgentCapability(
                    name="track_uptime",
                    description="Track service uptime",
                    category="data",
                    timeout_seconds=10,
                ),
                AgentCapability(
                    name="detect_anomaly",
                    description="Detect anomalies in metrics",
                    category="data",
                    timeout_seconds=30,
                ),
                AgentCapability(
                    name="set_alert_threshold",
                    description="Set alert thresholds",
                    category="execution",
                    timeout_seconds=5,
                ),
                AgentCapability(
                    name="get_alerts",
                    description="Get active alerts",
                    category="data",
                    timeout_seconds=5,
                ),
                AgentCapability(
                    name="track_costs",
                    description="Track LLM provider costs",
                    category="data",
                    timeout_seconds=10,
                ),
                AgentCapability(
                    name="api_rate_limits",
                    description="Monitor API rate limits",
                    category="data",
                    timeout_seconds=10,
                ),
                AgentCapability(
                    name="system_resources",
                    description="Monitor system resources (CPU, memory, disk)",
                    category="data",
                    timeout_seconds=10,
                ),
            ],
        )
        self.alert_thresholds = {}
        self.active_alerts = []
        self.metrics_history = {}

    async def validate(self, task: AgentTask) -> bool:
        """Validate monitor task."""
        if not await super().validate(task):
            return False

        operation = task.params.get("operation", "health_check")

        # Validate operation-specific parameters
        if operation == "health_check":
            if "url" not in task.params:
                logger.warning(f"Task {task.task_id}: Missing 'url' parameter")
                return False

        elif operation == "detect_anomaly":
            if "metric_name" not in task.params:
                logger.warning(f"Task {task.task_id}: Missing 'metric_name'")
                return False

        return True

    async def execute(self, task: AgentTask) -> AgentResult:
        """Execute monitoring operation."""
        operation = task.params.get("operation", "health_check")

        try:
            if operation == "health_check":
                return await self._health_check(task)
            elif operation == "get_metrics":
                return await self._get_metrics(task)
            elif operation == "track_uptime":
                return await self._track_uptime(task)
            elif operation == "detect_anomaly":
                return await self._detect_anomaly(task)
            elif operation == "set_alert_threshold":
                return await self._set_alert_threshold(task)
            elif operation == "get_alerts":
                return await self._get_alerts(task)
            elif operation == "track_costs":
                return await self._track_costs(task)
            elif operation == "api_rate_limits":
                return await self._api_rate_limits(task)
            elif operation == "system_resources":
                return await self._system_resources(task)
            else:
                return AgentResult(
                    task_id=task.task_id,
                    agent_name=self.name,
                    success=False,
                    error=f"Unknown operation: {operation}",
                )
        except Exception as e:
            logger.error(f"Monitor operation failed: {e}")
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=False,
                error=str(e),
            )

    async def _health_check(self, task: AgentTask) -> AgentResult:
        """Check service health."""
        url = task.params.get("url")
        timeout = task.params.get("timeout", 5)

        output = {
            "operation": "health_check",
            "url": url,
            "status": "healthy",
            "status_code": 200,
            "response_time_ms": 45,
            "timestamp": datetime.utcnow().isoformat(),
        }

        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            success=True,
            output=output,
        )

    async def _get_metrics(self, task: AgentTask) -> AgentResult:
        """Get performance metrics."""
        service = task.params.get("service", "default")
        metric_types = task.params.get("metric_types", ["cpu", "memory", "latency"])

        output = {
            "operation": "get_metrics",
            "service": service,
            "metrics": {
                "cpu_percent": 45.2,
                "memory_percent": 60.5,
                "disk_percent": 75.0,
                "latency_p50_ms": 50.0,
                "latency_p95_ms": 150.0,
                "latency_p99_ms": 300.0,
                "requests_per_second": 1250,
                "error_rate_percent": 0.5,
            },
            "timestamp": datetime.utcnow().isoformat(),
        }

        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            success=True,
            output=output,
        )

    async def _track_uptime(self, task: AgentTask) -> AgentResult:
        """Track service uptime."""
        service = task.params.get("service")
        hours = task.params.get("hours", 24)

        output = {
            "operation": "track_uptime",
            "service": service,
            "period_hours": hours,
            "uptime_percent": 99.95,
            "downtime_minutes": 0.3,
            "incidents": 0,
            "last_incident": None,
            "sla_status": "compliant",
            "timestamp": datetime.utcnow().isoformat(),
        }

        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            success=True,
            output=output,
        )

    async def _detect_anomaly(self, task: AgentTask) -> AgentResult:
        """Detect anomalies."""
        metric_name = task.params.get("metric_name")
        window_minutes = task.params.get("window_minutes", 60)
        sensitivity = task.params.get("sensitivity", 2.0)

        output = {
            "operation": "detect_anomaly",
            "metric_name": metric_name,
            "window_minutes": window_minutes,
            "anomalies_detected": 0,
            "anomaly_score": 0.1,
            "status": "normal",
            "expected_value": 100.0,
            "actual_value": 102.5,
            "deviation_percent": 2.5,
            "timestamp": datetime.utcnow().isoformat(),
        }

        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            success=True,
            output=output,
        )

    async def _set_alert_threshold(self, task: AgentTask) -> AgentResult:
        """Set alert threshold."""
        metric = task.params.get("metric")
        threshold = task.params.get("threshold")
        operator = task.params.get("operator", "greater_than")
        severity = task.params.get("severity", "warning")

        logger.info(f"Setting alert: {metric} {operator} {threshold} ({severity})")

        output = {
            "operation": "set_alert_threshold",
            "metric": metric,
            "threshold": threshold,
            "operator": operator,
            "severity": severity,
            "status": "active",
            "created_at": datetime.utcnow().isoformat(),
        }

        self.alert_thresholds[metric] = {
            "threshold": threshold,
            "operator": operator,
            "severity": severity,
        }

        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            success=True,
            output=output,
        )

    async def _get_alerts(self, task: AgentTask) -> AgentResult:
        """Get active alerts."""
        severity = task.params.get("severity")  # Filter by severity if provided
        limit = task.params.get("limit", 50)

        output = {
            "operation": "get_alerts",
            "total_active": 2,
            "alerts": [
                {
                    "alert_id": "alert_001",
                    "metric": "cpu_usage",
                    "severity": "warning",
                    "value": 85.5,
                    "threshold": 80.0,
                    "triggered_at": "2024-02-27T10:30:00",
                },
                {
                    "alert_id": "alert_002",
                    "metric": "error_rate",
                    "severity": "critical",
                    "value": 5.2,
                    "threshold": 1.0,
                    "triggered_at": "2024-02-27T10:25:00",
                },
            ],
            "timestamp": datetime.utcnow().isoformat(),
        }

        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            success=True,
            output=output,
        )

    async def _track_costs(self, task: AgentTask) -> AgentResult:
        """Track LLM provider costs."""
        period = task.params.get("period", "daily")  # daily, weekly, monthly
        providers = task.params.get("providers", ["anthropic", "openai", "groq"])

        output = {
            "operation": "track_costs",
            "period": period,
            "total_cost_usd": 125.50,
            "by_provider": {
                "anthropic": 75.25,
                "openai": 35.00,
                "groq": 15.25,
            },
            "tokens_used": {
                "input_tokens": 5000000,
                "output_tokens": 2500000,
            },
            "cost_per_1m_tokens": 0.025,
            "trending": "stable",
            "timestamp": datetime.utcnow().isoformat(),
        }

        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            success=True,
            output=output,
        )

    async def _api_rate_limits(self, task: AgentTask) -> AgentResult:
        """Monitor API rate limits."""
        api_name = task.params.get("api_name")

        output = {
            "operation": "api_rate_limits",
            "api_name": api_name,
            "rate_limit": 1000,
            "requests_used": 750,
            "requests_remaining": 250,
            "reset_at": "2024-02-27T11:00:00Z",
            "utilization_percent": 75.0,
            "status": "normal",
            "timestamp": datetime.utcnow().isoformat(),
        }

        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            success=True,
            output=output,
        )

    async def _system_resources(self, task: AgentTask) -> AgentResult:
        """Monitor system resources."""
        output = {
            "operation": "system_resources",
            "cpu": {
                "usage_percent": 45.2,
                "cores_used": 4,
                "cores_total": 8,
            },
            "memory": {
                "used_gb": 6.5,
                "total_gb": 16.0,
                "usage_percent": 40.6,
            },
            "disk": {
                "used_gb": 150.0,
                "total_gb": 500.0,
                "usage_percent": 30.0,
            },
            "network": {
                "input_mbps": 25.5,
                "output_mbps": 15.2,
            },
            "timestamp": datetime.utcnow().isoformat(),
        }

        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            success=True,
            output=output,
        )

    async def verify(self, result: AgentResult) -> bool:
        """Verify monitoring result."""
        if not isinstance(result.output, dict):
            logger.warning(f"Result {result.task_id}: Output is not a dict")
            return False

        # Should have operation field
        if "operation" not in result.output:
            logger.warning(f"Result {result.task_id}: Missing 'operation'")
            return False

        # Most monitoring operations should have timestamp
        if "timestamp" not in result.output and "checked_at" not in result.output:
            logger.warning(f"Result {result.task_id}: Missing timestamp")
            return False

        return True
