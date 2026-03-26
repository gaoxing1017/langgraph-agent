from __future__ import annotations

"""智能体状态定义。

AgentState 是流经 LangGraph 图的所有数据的唯一来源。
每个持有列表的字段都必须通过 Annotated 声明显式的 reducer，
以保证节点在并行分支上运行时的正确行为。

InputState / OutputState 是在图边界暴露的 TypedDict 子类：
  - InputState  → API 调用方允许提供的字段
  - OutputState → 返回给 API 调用方的字段（内部字段已剥离）
"""

import operator
from typing import Annotated, Any, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):
    """核心智能体状态 - 持久化到 checkpoint 中。"""

    # 消息通道：add_messages reducer 按消息 ID 进行去重处理
    messages: Annotated[list[AnyMessage], add_messages]

    # 会话标识符
    thread_id: str
    request_id: str

    # Plan-Execute 模式字段
    plan: list[str]
    current_step: int

    # 记忆上下文
    memory_context: str

    # 最终输出
    final_answer: str | None

    # operator.add reducer：每个节点追加自身的错误，不会覆盖已有内容
    errors: Annotated[list[str], operator.add]

    # 透传元数据
    metadata: dict[str, Any]


class InputState(TypedDict, total=False):
    """暴露给 API 调用方的输入字段子集。"""
    messages: Annotated[list[AnyMessage], add_messages]
    thread_id: str
    request_id: str
    metadata: dict[str, Any]


class OutputState(TypedDict, total=False):
    """返回给 API 调用方的输出字段子集。"""
    messages: Annotated[list[AnyMessage], add_messages]
    final_answer: str | None
    errors: Annotated[list[str], operator.add]
