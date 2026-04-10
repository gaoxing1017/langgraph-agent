from __future__ import annotations

"""LLM 节点：每个图中的主要推理步骤。

通过工厂函数获取 LLM，可选地绑定来自
config["configurable"]["tools"] 的工具，然后用当前消息历史调用 LLM。
只返回新的 AIMessage，由 add_messages reducer 追加。
"""

from langchain_core.runnables import RunnableConfig

from typing import Any

import structlog
from langchain_core.messages import AIMessage

from agent_framework.config.llm_config import get_llm
from agent_framework.config.settings import Settings, get_settings
from agent_framework.core.context import AgentContext
from agent_framework.core.state import AgentState

logger = structlog.get_logger(__name__)


async def llm_node(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    """使用当前消息调用 LLM 并返回新的 AI 消息。"""
    configurable = config.get("configurable", {})
    settings: Settings = configurable.get("settings") or get_settings()
    context: AgentContext = configurable.get("context", {})

    llm = get_llm(
        settings,
        provider=context.get("llm_provider"),
        model=context.get("model_name"),
        temperature=context.get("temperature"),
        max_tokens=context.get("max_tokens"),
    )

    # 若 configurable 中提供了工具则绑定工具
    tools = configurable.get("tools", [])
    if tools:
        llm = llm.bind_tools(tools)

    messages = state.get("messages", [])
    logger.debug("llm_node 被调用", message_count=len(messages))

    response: AIMessage = await llm.ainvoke(messages)
    return {"messages": [response]}
