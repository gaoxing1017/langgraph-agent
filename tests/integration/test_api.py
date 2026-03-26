from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock

from agent_framework.api.app import create_app
from agent_framework.config.settings import Settings


@pytest.fixture
def test_app():
    settings = Settings(ENVIRONMENT="development", CHECKPOINTER_TYPE="memory", NACOS_ENABLED=False)
    app = create_app(settings=settings)
    return app


@pytest.fixture
def client(test_app):
    with TestClient(test_app) as c:
        yield c


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_readiness_endpoint(client):
    response = client.get("/readiness")
    assert response.status_code == 200


def test_agent_card_endpoint(client):
    response = client.get("/.well-known/agent.json")
    assert response.status_code == 200
    data = response.json()
    assert "name" in data
    assert "skills" in data


def test_create_thread(client):
    response = client.post("/api/v1/threads", json={"user_id": "test-user"})
    assert response.status_code == 201
    data = response.json()
    assert "thread_id" in data
