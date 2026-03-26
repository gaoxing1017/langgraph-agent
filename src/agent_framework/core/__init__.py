"""智能体框架的核心领域类型。

从此处导入 AgentState、InputState、OutputState、AgentContext 以及错误层次结构，
而不是从各自的独立模块导入。
"""

from agent_framework.core.channels import AppendList, add_messages
from agent_framework.core.context import AgentContext
from agent_framework.core.errors import (
    A2AError,
    AgentError,
    AgentFrameworkError,
    ConfigurationError,
    GraphError,
    NacosError,
    ToolError,
)
from agent_framework.core.state import AgentState, InputState, OutputState

__all__ = [
    "AgentState",
    "InputState",
    "OutputState",
    "AgentContext",
    "AgentFrameworkError",
    "AgentError",
    "ToolError",
    "GraphError",
    "ConfigurationError",
    "A2AError",
    "NacosError",
    "AppendList",
    "add_messages",
]
