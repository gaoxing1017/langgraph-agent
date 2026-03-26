from __future__ import annotations

"""条件边路由函数。

每个路由函数组合 conditions.py 中的谓词并返回一个字面字符串，
LangGraph 用它来选择下一个节点。字符串必须与
传递给 add_conditional_edges() 的键匹配。
"""

from typing import Literal

from agent_framework.core.state import AgentState
from agent_framework.edges.conditions import (
    has_errors,
    has_tool_calls,
    is_over_iteration_limit,
    needs_human_approval,
    plan_has_more_steps,
)


def react_router(state: AgentState) -> Literal["tools", "end"]:
    """LLM 节点执行后的路由逻辑。

    - "tools"  → 最后一条消息包含 tool_calls，执行工具
    - "end"    → 无工具调用，或达到错误/迭代上限，终止
    """
    if is_over_iteration_limit(state) or has_errors(state):
        return "end"
    if has_tool_calls(state):
        return "tools"
    return "end"


def plan_execute_router(state: AgentState) -> Literal["execute", "end"]:
    """执行节点完成后的路由逻辑。

    - "execute" → 计划中仍有剩余步骤
    - "end"     → 所有步骤已完成，或达到错误/迭代上限
    """
    if has_errors(state) or is_over_iteration_limit(state):
        return "end"
    if plan_has_more_steps(state):
        return "execute"
    return "end"


def supervisor_router(state: AgentState) -> str:
    """将 supervisor 的输出路由到专家节点或 END。

    从最后一条消息的第一个 tool_call 名称中读取目标节点。
    该名称必须与已注册的专家节点键匹配；否则回退到 "end"。
    """
    if is_over_iteration_limit(state) or has_errors(state):
        return "end"
    messages = state.get("messages", [])
    if not messages:
        return "end"
    last = messages[-1]
    tool_calls = getattr(last, "tool_calls", [])
    if tool_calls:
        return tool_calls[0].get("name", "end")
    return "end"


def human_in_loop_router(state: AgentState) -> Literal["human", "llm", "end"]:
    """根据状态标志路由到人工审批、LLM 重试或结束。"""
    if needs_human_approval(state):
        return "human"
    if has_tool_calls(state):
        return "llm"
    return "end"
