"""
Monitoring & Alert Agent - Real health checks, system metrics, anomaly detection, alerting.
v2.0.0 — All methods use real data (httpx for health checks, psutil for system metrics,
          LiteLLM token tracking for costs).
"""

import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from app.agents.base import BaseAgent
from app.agents.models import AgentCapability, AgentResult, AgentTask
from app.core.logging import logger


class MonitorAgent(BaseAgent):
    """Monitor services, track metrics, and send alerts — all real data."""

    def __init__(self):
        """Initialize the monitor agent."""
        super().__init__(
            name="monitor_agent",
            description="Service monitoring, metrics, and alerting",
            version="2.0.0",
            capabilities=[
                AgentCapability(
                    name="health_check",
                    description="Check endpoint health status via real HTTP request",
                    category="data",
                    timeout_seconds=15,
                ),
                AgentCapability(
                    name="get_metrics",
                    description="Retrieve real system performance metrics",
                    category="data",
                    timeout_seconds=10,
                ),
                AgentCapability(
                    name="track_uptime",
                    description="Track service uptime via HTTP ping",
                    category="data",
                    timeout_seconds=10,
                ),
                AgentCapability(
                    name="detect_anomaly",
                    description="Detect anomalies in collected metrics",
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
                    description="Get active alerts based on thresholds",
                    category="data",
                    timeout_seconds=5,
                ),
                AgentCapability(
                    name="track_costs",
                    description="Track real LLM provider costs from token logs",
                    category="data",
                    timeout_seconds=10,
                ),
                AgentCapability(
                    name="api_rate_limits",
                    description="Monitor API rate limit status",
                    category="data",
                    timeout_seconds=10,
                ),
                AgentCapability(
                    name="system_resources",
                    description="Monitor real system resources (CPU, memory, disk)",
                    category="data",
                    timeout_seconds=10,
                ),
            ],
        )
        self.alert_thresholds: dict[str, dict] = {}
        self.active_alerts: list[dict] = []
        self.metrics_history: dict[str, list] = {}
        self.data_dir = Path("data/monitor")
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            self.data_dir = Path("/tmp/cipher_data/monitor")
            self.data_dir.mkdir(parents=True, exist_ok=True)
        self._uptime_file = self.data_dir / "uptime_log.json"
        self._alerts_file = self.data_dir / "thresholds.json"
        self._load_thresholds()

    def _load_thresholds(self):
        """Load saved alert thresholds from disk."""
        if self._alerts_file.exists():
            try:
                self.alert_thresholds = json.loads(self._alerts_file.read_text())
            except Exception:
                self.alert_thresholds = {}

    def _save_thresholds(self):
        """Persist alert thresholds to disk."""
        self._alerts_file.write_text(json.dumps(self.alert_thresholds, indent=2))

    async def validate(self, task: AgentTask) -> bool:
        """Validate monitor task."""
        if not await super().validate(task):
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
        """Real HTTP health check against a URL."""
        import httpx

        url = task.params.get("url")
        timeout = task.params.get("timeout", 10)

        if not url:
            # Default: check our own backend
            from app.core.config import settings
            url = f"https://cipher-elysian-production-b6a8.up.railway.app/health"

        try:
            start = time.time()
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.get(url)
            elapsed_ms = round((time.time() - start) * 1000, 1)

            status = "healthy" if resp.status_code < 400 else "unhealthy"
            output = {
                "operation": "health_check",
                "url": url,
                "status": status,
                "status_code": resp.status_code,
                "response_time_ms": elapsed_ms,
                "content_length": len(resp.content),
                "timestamp": datetime.utcnow().isoformat(),
            }
        except httpx.TimeoutException:
            output = {
                "operation": "health_check",
                "url": url,
                "status": "timeout",
                "status_code": None,
                "response_time_ms": timeout * 1000,
                "error": f"Request timed out after {timeout}s",
                "timestamp": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            output = {
                "operation": "health_check",
                "url": url,
                "status": "unreachable",
                "status_code": None,
                "response_time_ms": None,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }

        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            success=True,
            output=output,
        )

    async def _get_metrics(self, task: AgentTask) -> AgentResult:
        """Get real system performance metrics using psutil."""
        try:
            import psutil

            cpu = psutil.cpu_percent(interval=1)
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage("/")

            metrics = {
                "cpu_percent": cpu,
                "memory_percent": mem.percent,
                "memory_used_gb": round(mem.used / (1024 ** 3), 2),
                "memory_total_gb": round(mem.total / (1024 ** 3), 2),
                "disk_percent": disk.percent,
                "disk_used_gb": round(disk.used / (1024 ** 3), 2),
                "disk_total_gb": round(disk.total / (1024 ** 3), 2),
            }

            # Try to get network I/O
            try:
                net = psutil.net_io_counters()
                metrics["net_bytes_sent"] = net.bytes_sent
                metrics["net_bytes_recv"] = net.bytes_recv
            except Exception:
                pass

            # Store in history for anomaly detection
            ts = datetime.utcnow().isoformat()
            for key, val in metrics.items():
                if key not in self.metrics_history:
                    self.metrics_history[key] = []
                self.metrics_history[key].append({"value": val, "ts": ts})
                # Keep last 100 data points
                self.metrics_history[key] = self.metrics_history[key][-100:]

            output = {
                "operation": "get_metrics",
                "metrics": metrics,
                "timestamp": ts,
            }

        except ImportError:
            output = {
                "operation": "get_metrics",
                "error": "psutil not installed. Install with: pip install psutil",
                "status": "not_available",
                "timestamp": datetime.utcnow().isoformat(),
            }

        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            success=True,
            output=output,
        )

    async def _track_uptime(self, task: AgentTask) -> AgentResult:
        """Track service uptime by pinging the URL and logging results."""
        import httpx

        url = task.params.get("url") or task.params.get("service")
        if not url:
            url = "https://cipher-elysian-production-b6a8.up.railway.app/health"

        # Load existing uptime log
        log: list[dict] = []
        if self._uptime_file.exists():
            try:
                log = json.loads(self._uptime_file.read_text())
            except Exception:
                log = []

        # Ping the service
        try:
            start = time.time()
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url)
            elapsed_ms = round((time.time() - start) * 1000, 1)
            is_up = resp.status_code < 500
        except Exception:
            elapsed_ms = 0
            is_up = False

        # Record this check
        log.append({
            "url": url,
            "is_up": is_up,
            "response_time_ms": elapsed_ms,
            "checked_at": datetime.utcnow().isoformat(),
        })
        # Keep last 1000 entries
        log = log[-1000:]
        self._uptime_file.write_text(json.dumps(log, indent=2))

        # Calculate uptime from log
        relevant = [e for e in log if e.get("url") == url]
        total_checks = len(relevant)
        up_checks = sum(1 for e in relevant if e.get("is_up"))
        uptime_pct = round((up_checks / total_checks * 100), 2) if total_checks > 0 else 0
        down_checks = total_checks - up_checks

        output = {
            "operation": "track_uptime",
            "url": url,
            "current_status": "up" if is_up else "down",
            "response_time_ms": elapsed_ms,
            "uptime_percent": uptime_pct,
            "total_checks": total_checks,
            "up_count": up_checks,
            "down_count": down_checks,
            "timestamp": datetime.utcnow().isoformat(),
        }

        return AgentResult(
            task_id=task.task_id,
            agent_name=self.name,
            success=True,
            output=output,
        )

    async def _detect_anomaly(self, task: AgentTask) -> AgentResult:
        """Detect anomalies using z-score on collected metrics history."""
        metric_name = task.params.get("metric_name", "cpu_percent")
        sensitivity = task.params.get("sensitivity", 2.0)

        history = self.metrics_history.get(metric_name, [])

        if len(history) < 5:
            # Not enough data — collect fresh metrics first
            await self._get_metrics(task)
            history = self.metrics_history.get(metric_name, [])

        if len(history) < 3:
            output = {
                "operation": "detect_anomaly",
                "metric_name": metric_name,
                "status": "insufficient_data",
                "error": f"Need at least 3 data points for '{metric_name}'. Currently have {len(history)}. Call get_metrics a few times first.",
                "timestamp": datetime.utcnow().isoformat(),
            }
            return AgentResult(task_id=task.task_id, agent_name=self.name, success=True, output=output)

        values = [h["value"] for h in history if isinstance(h.get("value"), (int, float))]
        if not values:
            return AgentResult(task_id=task.task_id, agent_name=self.name, success=False, error="No numeric values found")

        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        std = variance ** 0.5

        latest = values[-1]
        z_score = abs((latest - mean) / std) if std > 0 else 0
        is_anomaly = z_score > sensitivity

        output = {
            "operation": "detect_anomaly",
            "metric_name": metric_name,
            "latest_value": latest,
            "mean": round(mean, 2),
            "std": round(std, 2),
            "z_score": round(z_score, 2),
            "sensitivity_threshold": sensitivity,
            "is_anomaly": is_anomaly,
            "status": "anomaly_detected" if is_anomaly else "normal",
            "data_points": len(values),
            "timestamp": datetime.utcnow().isoformat(),
        }

        return AgentResult(task_id=task.task_id, agent_name=self.name, success=True, output=output)

    async def _set_alert_threshold(self, task: AgentTask) -> AgentResult:
        """Set alert threshold — persisted to disk."""
        metric = task.params.get("metric")
        threshold = task.params.get("threshold")
        operator = task.params.get("operator", "greater_than")
        severity = task.params.get("severity", "warning")

        if not metric or threshold is None:
            return AgentResult(task_id=task.task_id, agent_name=self.name, success=False, error="Need 'metric' and 'threshold' params")

        self.alert_thresholds[metric] = {
            "threshold": threshold,
            "operator": operator,
            "severity": severity,
            "created_at": datetime.utcnow().isoformat(),
        }
        self._save_thresholds()

        output = {
            "operation": "set_alert_threshold",
            "metric": metric,
            "threshold": threshold,
            "operator": operator,
            "severity": severity,
            "status": "active",
            "total_thresholds": len(self.alert_thresholds),
        }

        return AgentResult(task_id=task.task_id, agent_name=self.name, success=True, output=output)

    async def _get_alerts(self, task: AgentTask) -> AgentResult:
        """Check current metrics against thresholds and return real alerts."""
        if not self.alert_thresholds:
            return AgentResult(
                task_id=task.task_id,
                agent_name=self.name,
                success=True,
                output={
                    "operation": "get_alerts",
                    "total_active": 0,
                    "alerts": [],
                    "note": "No alert thresholds configured. Use set_alert_threshold first.",
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )

        # Collect fresh metrics to check against
        await self._get_metrics(task)

        triggered = []
        for metric, config in self.alert_thresholds.items():
            history = self.metrics_history.get(metric, [])
            if not history:
                continue
            latest = history[-1]["value"]
            thresh = config["threshold"]
            op = config["operator"]

            fire = False
            if op == "greater_than" and latest > thresh:
                fire = True
            elif op == "less_than" and latest < thresh:
                fire = True
            elif op == "equals" and latest == thresh:
                fire = True

            if fire:
                triggered.append({
                    "metric": metric,
                    "severity": config["severity"],
                    "value": latest,
                    "threshold": thresh,
                    "operator": op,
                    "triggered_at": datetime.utcnow().isoformat(),
                })

        output = {
            "operation": "get_alerts",
            "total_active": len(triggered),
            "alerts": triggered,
            "thresholds_checked": len(self.alert_thresholds),
            "timestamp": datetime.utcnow().isoformat(),
        }

        return AgentResult(task_id=task.task_id, agent_name=self.name, success=True, output=output)

    async def _track_costs(self, task: AgentTask) -> AgentResult:
        """Track real LLM costs from the token usage log."""
        try:
            from app.services.llm_router import get_token_usage_stats
            stats = get_token_usage_stats()
            output = {
                "operation": "track_costs",
                **stats,
                "timestamp": datetime.utcnow().isoformat(),
            }
        except (ImportError, AttributeError):
            # Fallback: read from token log file if it exists
            token_log = self.data_dir / "token_usage.json"
            if token_log.exists():
                try:
                    data = json.loads(token_log.read_text())
                    output = {
                        "operation": "track_costs",
                        **data,
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                except Exception:
                    output = {
                        "operation": "track_costs",
                        "error": "Token usage tracking not available. No get_token_usage_stats() function and no token_usage.json log found.",
                        "status": "not_configured",
                        "timestamp": datetime.utcnow().isoformat(),
                    }
            else:
                output = {
                    "operation": "track_costs",
                    "error": "Cost tracking not configured. Token usage logs not found.",
                    "status": "not_configured",
                    "hint": "LLM router needs to log token usage to data/token_usage.json for cost tracking.",
                    "timestamp": datetime.utcnow().isoformat(),
                }

        return AgentResult(task_id=task.task_id, agent_name=self.name, success=True, output=output)

    async def _api_rate_limits(self, task: AgentTask) -> AgentResult:
        """Check real API rate limit status by making a lightweight request."""
        import httpx

        api_name = task.params.get("api_name", "anthropic")

        endpoints = {
            "anthropic": "https://api.anthropic.com/v1/messages",
            "openai": "https://api.openai.com/v1/models",
            "brave": "https://api.search.brave.com/res/v1/web/search",
        }

        url = endpoints.get(api_name, task.params.get("url", ""))
        if not url:
            return AgentResult(
                task_id=task.task_id, agent_name=self.name, success=False,
                error=f"Unknown API: {api_name}. Available: {', '.join(endpoints.keys())} or provide 'url' param",
            )

        try:
            from app.core.config import settings
            headers = {}
            if api_name == "anthropic":
                key = getattr(settings, "anthropic_api_key", "")
                if key:
                    headers = {"x-api-key": key, "anthropic-version": "2023-06-01"}
            elif api_name == "openai":
                key = getattr(settings, "openai_api_key", "")
                if key:
                    headers = {"Authorization": f"Bearer {key}"}
            elif api_name == "brave":
                key = getattr(settings, "brave_search_api_key", "")
                if key:
                    headers = {"X-Subscription-Token": key}

            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url, headers=headers)

            # Extract rate limit headers (most APIs use these)
            rate_limit = resp.headers.get("x-ratelimit-limit", resp.headers.get("ratelimit-limit"))
            remaining = resp.headers.get("x-ratelimit-remaining", resp.headers.get("ratelimit-remaining"))
            reset = resp.headers.get("x-ratelimit-reset", resp.headers.get("ratelimit-reset"))

            output = {
                "operation": "api_rate_limits",
                "api_name": api_name,
                "status_code": resp.status_code,
                "rate_limit": int(rate_limit) if rate_limit else "unknown",
                "remaining": int(remaining) if remaining else "unknown",
                "reset_at": reset or "unknown",
                "utilization_percent": round(
                    (1 - int(remaining) / int(rate_limit)) * 100, 1
                ) if rate_limit and remaining else "unknown",
                "timestamp": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            output = {
                "operation": "api_rate_limits",
                "api_name": api_name,
                "error": str(e),
                "status": "check_failed",
                "timestamp": datetime.utcnow().isoformat(),
            }

        return AgentResult(task_id=task.task_id, agent_name=self.name, success=True, output=output)

    async def _system_resources(self, task: AgentTask) -> AgentResult:
        """Get real system resource usage via psutil."""
        try:
            import psutil

            cpu = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage("/")

            output = {
                "operation": "system_resources",
                "cpu": {
                    "usage_percent": cpu,
                    "cores_total": cpu_count,
                    "load_avg": list(psutil.getloadavg()) if hasattr(psutil, "getloadavg") else [],
                },
                "memory": {
                    "used_gb": round(mem.used / (1024 ** 3), 2),
                    "total_gb": round(mem.total / (1024 ** 3), 2),
                    "available_gb": round(mem.available / (1024 ** 3), 2),
                    "usage_percent": mem.percent,
                },
                "disk": {
                    "used_gb": round(disk.used / (1024 ** 3), 2),
                    "total_gb": round(disk.total / (1024 ** 3), 2),
                    "free_gb": round(disk.free / (1024 ** 3), 2),
                    "usage_percent": disk.percent,
                },
                "timestamp": datetime.utcnow().isoformat(),
            }

            # Network I/O
            try:
                net = psutil.net_io_counters()
                output["network"] = {
                    "bytes_sent": net.bytes_sent,
                    "bytes_recv": net.bytes_recv,
                }
            except Exception:
                pass

        except ImportError:
            output = {
                "operation": "system_resources",
                "error": "psutil not installed. Install with: pip install psutil",
                "status": "not_available",
                "timestamp": datetime.utcnow().isoformat(),
            }

        return AgentResult(task_id=task.task_id, agent_name=self.name, success=True, output=output)

    async def verify(self, result: AgentResult) -> bool:
        """Verify monitoring result."""
        if not isinstance(result.output, dict):
            return False
        if "operation" not in result.output:
            return False
        return True
