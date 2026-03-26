"""节点函数库。

此包中的每个函数均遵循 LangGraph 节点契约：

    async def node_fn(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
        # ... 仅修改自己负责的键，返回部分状态字典
        return {"messages": [...]}

节点对于工具失败绝不能抛出异常——而应返回带有 status="error" 的 ToolMessage，
以便 LLM 能够观察到错误并进行重试。
"""

from agent_framework.nodes.executor_node import executor_node
from agent_framework.nodes.guard_node import input_guard_node, output_guard_node
from agent_framework.nodes.human_node import human_node
from agent_framework.nodes.llm_node import llm_node
from agent_framework.nodes.memory_node import memory_read_node, memory_write_node
from agent_framework.nodes.planner_node import planner_node
from agent_framework.nodes.router_node import router_node
from agent_framework.nodes.tool_node import build_tool_node

__all__ = [
    "llm_node",
    "build_tool_node",
    "planner_node",
    "executor_node",
    "router_node",
    "memory_read_node",
    "memory_write_node",
    "human_node",
    "input_guard_node",
    "output_guard_node",
]
