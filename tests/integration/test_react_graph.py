from __future__ import annotations

import pytest
from langchain_core.messages import HumanMessage
from unittest.mock import AsyncMock, MagicMock, patch

from agent_framework.graphs.react_graph import build_react_graph
from agent_framework.config.settings import Settings


@pytest.mark.asyncio
async def test_react_graph_structure():
    """Verify the ReAct graph compiles and has expected nodes."""
    graph = build_react_graph()
    compiled = graph.compile()
    assert compiled is not None
    # Graph should have llm and tools nodes
    nodes = list(compiled.nodes.keys())
    assert "llm" in nodes
    assert "tools" in nodes


@pytest.mark.asyncio
async def test_react_graph_with_no_tool_calls():
    """Graph should end after a single LLM call when no tool calls are made."""
    settings = Settings(ENVIRONMENT="development", CHECKPOINTER_TYPE="memory")

    with patch("agent_framework.nodes.llm_node.get_llm") as mock_get_llm:
        from langchain_core.messages import AIMessage
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="The answer is 4."))
        mock_get_llm.return_value = mock_llm

        graph = build_react_graph()
        compiled = graph.compile()

        config = {
            "configurable": {
                "thread_id": "test-thread",
                "settings": settings,
                "context": {},
            }
        }
        result = await compiled.ainvoke(
            {"messages": [HumanMessage(content="What is 2+2?")]},
            config=config,
        )
        assert result is not None
        assert "messages" in result
