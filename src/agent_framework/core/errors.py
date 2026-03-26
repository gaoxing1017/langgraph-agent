from __future__ import annotations

"""智能体框架的领域错误层次结构。

所有异常均继承自 AgentFrameworkError，
在需要时调用方可以用单个 except 子句捕获整个异常族。
"""


class AgentFrameworkError(Exception):
    """智能体框架的基础异常。"""


class AgentError(AgentFrameworkError):
    """智能体在图执行过程中抛出的异常。"""


class ToolError(AgentFrameworkError):
    """工具执行过程中抛出的异常。"""

    def __init__(self, message: str, tool_name: str = "", tool_call_id: str = "") -> None:
        super().__init__(message)
        self.tool_name = tool_name
        self.tool_call_id = tool_call_id


class GraphError(AgentFrameworkError):
    """图编译或执行过程中的异常。"""


class MemoryError(AgentFrameworkError):  # noqa: A001
    """记忆读写操作的异常。命名为此是为了避免遮蔽内置的 MemoryError。"""


class ConfigurationError(AgentFrameworkError):
    """配置无效或缺失时的异常。"""


class A2AError(AgentFrameworkError):
    """A2A 协议通信过程中的异常。"""


class NacosError(AgentFrameworkError):
    """Nacos 操作过程中的异常。"""
