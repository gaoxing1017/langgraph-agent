from __future__ import annotations

import operator
from typing import Annotated

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from agent_framework.core.state import AgentState, InputState, OutputState


def test_agent_state_messages_reducer():
    """add_messages reducer should deduplicate by message ID."""
    from langgraph.graph.message import add_messages

    msgs1 = [HumanMessage(content="Hello", id="msg-1")]
    msgs2 = [AIMessage(content="Hi there!", id="msg-2")]

    result = add_messages(msgs1, msgs2)
    assert len(result) == 2
    assert result[0].content == "Hello"
    assert result[1].content == "Hi there!"


def test_agent_state_errors_reducer():
    """operator.add reducer should append errors."""
    errors1 = ["error1"]
    errors2 = ["error2", "error3"]
    combined = operator.add(errors1, errors2)
    assert combined == ["error1", "error2", "error3"]


def test_input_state_is_subset():
    """InputState should only contain user-facing fields."""
    input_state = InputState(
        messages=[HumanMessage(content="test")],
        thread_id="thread-1",
    )
    assert "thread_id" in input_state
    assert "plan" not in input_state


def test_output_state_excludes_internals():
    """OutputState should not expose internal scratchpad fields."""
    output = OutputState(
        messages=[AIMessage(content="result")],
        final_answer="4",
    )
    assert "plan" not in output
    assert "current_step" not in output
