from __future__ import annotations

"""路由节点：对用户意图进行分类并将路由键写入状态。

将决策写入 state["metadata"]["route"]，使条件边能够
路由到正确的专家子图，而无需在边函数中嵌入分类逻辑。
"""

from langchain_core.runnables import RunnableConfig

from typing import Any, Literal

import structlog
from langchain_core.messages import SystemMessage
from pydantic import BaseModel

from agent_framework.config.llm_config import get_llm
from agent_framework.config.settings import Settings
from agent_framework.core.context import AgentContext
from agent_framework.core.state import AgentState

logger = structlog.get_logger(__name__)

ROUTER_SYSTEM_PROMPT = """Classify the user's request into exactly one category:
- research: requires web search or information gathering
- code: requires writing or executing code
- analysis: requires data analysis or reasoning
- general: general question or conversation

Respond with only the category name."""


class RouteDecision(BaseModel):
    route: Literal["research", "code", "analysis", "general"]


async def router_node(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    """对用户意图进行分类并将路由决策存储到元数据中。"""
    configurable = config.get("configurable", {})
    settings: Settings = configurable.get("settings")
    context: AgentContext = configurable.get("context", {})

    llm = get_llm(settings, provider=context.get("llm_provider"))
    router_llm = llm.with_structured_output(RouteDecision)

    messages = [SystemMessage(content=ROUTER_SYSTEM_PROMPT)] + list(state.get("messages", []))
    decision: RouteDecision = await router_llm.ainvoke(messages)

    logger.info("路由决策", route=decision.route)
    metadata = dict(state.get("metadata", {}))
    metadata["route"] = decision.route
    return {"metadata": metadata}
