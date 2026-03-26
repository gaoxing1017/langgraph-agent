from __future__ import annotations

import pytest

from agent_framework.core.errors import (
    AgentError,
    AgentFrameworkError,
    GraphError,
    ToolError,
)


def test_tool_error_attributes():
    err = ToolError("tool failed", tool_name="search", tool_call_id="tc-1")
    assert err.tool_name == "search"
    assert err.tool_call_id == "tc-1"
    assert str(err) == "tool failed"


def test_error_hierarchy():
    assert issubclass(AgentError, AgentFrameworkError)
    assert issubclass(ToolError, AgentFrameworkError)
    assert issubclass(GraphError, AgentFrameworkError)


def test_tool_error_is_catchable_as_base():
    with pytest.raises(AgentFrameworkError):
        raise ToolError("test error")
