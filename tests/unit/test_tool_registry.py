from __future__ import annotations

import pytest
from langchain_core.tools import tool

from agent_framework.tools.registry import ToolRegistry


@tool
def dummy_search(query: str) -> str:
    """A dummy search tool."""
    return f"Results for: {query}"


@tool
def dummy_code(code: str) -> str:
    """A dummy code tool."""
    return f"Executed: {code}"


def test_register_and_get():
    registry = ToolRegistry()
    registry.register(dummy_search, category="search")
    assert registry.get("dummy_search") is dummy_search


def test_get_by_category():
    registry = ToolRegistry()
    registry.register(dummy_search, category="search")
    registry.register(dummy_code, category="code")
    search_tools = registry.get_by_category("search")
    assert len(search_tools) == 1
    assert search_tools[0].name == "dummy_search"


def test_get_enabled_empty_returns_all():
    registry = ToolRegistry()
    registry.register(dummy_search, category="search")
    registry.register(dummy_code, category="code")
    all_tools = registry.get_enabled([])
    assert len(all_tools) == 2


def test_get_enabled_with_whitelist():
    registry = ToolRegistry()
    registry.register(dummy_search, category="search")
    registry.register(dummy_code, category="code")
    enabled = registry.get_enabled(["dummy_search"])
    assert len(enabled) == 1
    assert enabled[0].name == "dummy_search"


def test_get_unknown_raises():
    registry = ToolRegistry()
    with pytest.raises(KeyError):
        registry.get("nonexistent_tool")
