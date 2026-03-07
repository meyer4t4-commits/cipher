"""
Pytest configuration and shared fixtures for Cipher tests.
"""

import os
import sys
import pytest

# Ensure the project root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set minimal env vars so config doesn't crash
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("APP_ENV", "testing")
os.environ.setdefault("APP_DEBUG", "false")
os.environ.setdefault("SCANNER_ENABLED", "false")


@pytest.fixture
def sample_task():
    """Create a sample agent task for testing."""
    from app.agents.models import AgentTask
    return AgentTask(
        agent_name="test_agent",
        instruction="Test instruction",
        params={"key": "value"},
        timeout_seconds=10,
    )


@pytest.fixture
def sample_result():
    """Create a sample agent result for testing."""
    from app.agents.models import AgentResult
    return AgentResult(
        task_id="test-123",
        agent_name="test_agent",
        success=True,
        output="Test output",
        execution_time_ms=42.0,
        verified=True,
    )


@pytest.fixture
def clean_registry():
    """Provide a fresh registry for each test."""
    from app.agents.registry import AgentRegistry
    return AgentRegistry()
