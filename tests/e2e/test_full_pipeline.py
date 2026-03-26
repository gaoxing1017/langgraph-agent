from __future__ import annotations

import pytest

# E2E tests require a running Postgres and real API keys.
# Run with: uv run pytest tests/e2e/ -v --e2e
# These are skipped by default in CI.

pytestmark = pytest.mark.skip(reason="E2E tests require external services")


@pytest.mark.asyncio
async def test_full_conversation_with_memory():
    """Full pipeline: message → graph → checkpoint → resume."""
    pass


@pytest.mark.asyncio
async def test_a2a_task_delegation():
    """Full A2A flow: send task → execute → return artifact."""
    pass
