from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage

from agent_framework.core.state import AgentState
from agent_framework.edges.conditions import (
    has_errors,
    has_tool_calls,
    is_over_iteration_limit,
    plan_has_more_steps,
)


def test_has_tool_calls_true():
    msg = AIMessage(content="", tool_calls=[{"name": "search", "args": {}, "id": "tc-1"}])
    state = AgentState(messages=[msg])
    assert has_tool_calls(state) is True


def test_has_tool_calls_false():
    msg = AIMessage(content="No tools needed")
    state = AgentState(messages=[msg])
    assert has_tool_calls(state) is False


def test_has_errors():
    state = AgentState(errors=["something went wrong"])
    assert has_errors(state) is True


def test_no_errors():
    state = AgentState(errors=[])
    assert has_errors(state) is False


def test_plan_has_more_steps():
    state = AgentState(plan=["step1", "step2"], current_step=1)
    assert plan_has_more_steps(state) is True


def test_plan_exhausted():
    state = AgentState(plan=["step1", "step2"], current_step=2)
    assert plan_has_more_steps(state) is False


def test_over_iteration_limit():
    msgs = [HumanMessage(content=f"msg {i}") for i in range(50)]
    state = AgentState(messages=msgs)
    assert is_over_iteration_limit(state) is True
