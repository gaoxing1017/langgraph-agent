from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import HumanMessage

from agent_framework.config.settings import Settings
from agent_framework.core.state import AgentState, InputState


@pytest.fixture(scope="session")
def settings() -> Settings:
    return Settings(
        ENVIRONMENT="development",
        LLM_PROVIDER="openai",
        CHECKPOINTER_TYPE="memory",
        NACOS_ENABLED=False,
        LANGFUSE_ENABLED=False,
    )


@pytest.fixture
def sample_input_state() -> InputState:
    return InputState(
        messages=[HumanMessage(content="Hello, what is 2+2?")],
        thread_id="test-thread-001",
        request_id="test-run-001",
    )


@pytest.fixture
def sample_agent_state() -> AgentState:
    return AgentState(
        messages=[HumanMessage(content="Hello, what is 2+2?")],
        thread_id="test-thread-001",
        request_id="test-run-001",
        plan=[],
        current_step=0,
        memory_context="",
        final_answer=None,
        errors=[],
        metadata={},
    )
