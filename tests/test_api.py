"""
Tests for Orchid API endpoints.
Run: pytest tests/ -v
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.database import Base, engine


@pytest.fixture(autouse=True)
def setup_db():
    """Create fresh database for each test."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app)


class TestRootEndpoints:
    def test_root(self, client):
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Orchid"
        assert "version" in data

    def test_ping(self, client):
        response = client.get("/ping")
        assert response.status_code == 200
        assert response.json() == {"pong": True}


class TestSystemEndpoints:
    def test_health(self, client):
        response = client.get("/api/v1/system/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert "uptime_seconds" in data

    def test_prompts_empty(self, client):
        response = client.get("/api/v1/system/prompts")
        assert response.status_code == 200
        assert response.json()["prompts"] == []

    def test_create_and_list_prompt(self, client):
        # Create
        response = client.post(
            "/api/v1/system/prompts",
            params={"name": "test_prompt", "content": "You are a test assistant.", "is_default": True},
        )
        assert response.status_code == 200

        # List
        response = client.get("/api/v1/system/prompts")
        prompts = response.json()["prompts"]
        assert len(prompts) == 1
        assert prompts[0]["name"] == "test_prompt"
        assert prompts[0]["is_default"] is True


class TestModelEndpoints:
    def test_list_models(self, client):
        response = client.get("/api/v1/models/")
        assert response.status_code == 200
        data = response.json()
        assert "models" in data
        assert len(data["models"]) > 0

    def test_usage_empty(self, client):
        response = client.get("/api/v1/models/usage")
        assert response.status_code == 200
        data = response.json()
        assert data["period_days"] == 30
        assert data["models"] == []


class TestMemoryEndpoints:
    def test_store_and_recall(self, client):
        # Store
        response = client.post(
            "/api/v1/memory/store",
            json={"content": "Mark is building Orchid, a sovereign AI daemon.", "metadata": {"source": "test"}},
        )
        assert response.status_code == 200
        assert "memory_id" in response.json()

        # Recall
        response = client.post(
            "/api/v1/memory/recall",
            json={"query": "What is Orchid?", "n_results": 3},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["count"] > 0
        assert "sovereign" in data["memories"][0]["content"].lower()

    def test_stats(self, client):
        response = client.get("/api/v1/memory/stats")
        assert response.status_code == 200
        assert "total_memories" in response.json()


class TestChatEndpoints:
    def test_conversations_empty(self, client):
        response = client.get("/api/v1/chat/conversations")
        assert response.status_code == 200
        assert response.json() == []

    def test_conversation_not_found(self, client):
        response = client.get("/api/v1/chat/conversations/nonexistent")
        assert response.status_code == 404
