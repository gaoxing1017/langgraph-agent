"""工具库。

所有工具均遵循 LangChain @tool 模式，并注册在 ToolRegistry 实例中。
registry 支持每次调用的工具白名单，
使不同租户或用户能拥有不同的工具访问权限。

快速注册示例：
    from agent_framework.tools.registry import ToolRegistry
    from agent_framework.tools.search.tavily_search import tavily_search

    registry = ToolRegistry()
    registry.register(tavily_search, category="search")
"""

from agent_framework.tools.registry import ToolRegistry

__all__ = ["ToolRegistry"]
