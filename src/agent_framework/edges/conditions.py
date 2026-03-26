from __future__ import annotations

"""条件边所使用的纯谓词函数。

每个函数接收 AgentState 并返回 bool。函数不包含任何副作用，
便于隔离进行单元测试。routers.py 中的路由函数
组合这些谓词以返回路由决策。
"""

from agent_framework.core.state import AgentState

# LLM 与工具之间的最大往返次数，超出后图强制终止。
# 每次"迭代"至少产生一条 HumanMessage 和一条 AIMessage，
# 因此消息列表守卫使用 MAX_ITERATIONS * 2。
MAX_ITERATIONS = 20


def has_tool_calls(state: AgentState) -> bool:
    """若最后一条消息包含待执行的工具调用则返回 True。"""
    messages = state.get("messages", [])
    if not messages:
        return False
    last = messages[-1]
    return bool(getattr(last, "tool_calls", None))


def has_errors(state: AgentState) -> bool:
    """若任意节点向 state["errors"] 写入了错误则返回 True。"""
    return bool(state.get("errors"))


def plan_has_more_steps(state: AgentState) -> bool:
    """若 current_step 尚未到达计划末尾则返回 True。"""
    plan = state.get("plan", [])
    current_step = state.get("current_step", 0)
    return current_step < len(plan)


def is_over_iteration_limit(state: AgentState) -> bool:
    """当消息数量超过 MAX_ITERATIONS * 2 时返回 True。

    乘以 2 是因为每次往返都会追加一条 HumanMessage
    （工具结果/步骤提示）和一条 AIMessage（LLM 响应）。
    """
    messages = state.get("messages", [])
    return len(messages) > MAX_ITERATIONS * 2


def needs_human_approval(state: AgentState) -> bool:
    """当图需要人工审批下一步操作时返回 True。"""
    metadata = state.get("metadata", {})
    return bool(metadata.get("requires_human_approval", False))


def route_by_metadata(state: AgentState) -> str:
    """返回存储在 state["metadata"]["route"] 中的路由键（默认值为 'general'）。"""
    metadata = state.get("metadata", {})
    return metadata.get("route", "general")
