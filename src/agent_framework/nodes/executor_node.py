from __future__ import annotations

"""执行节点：逐步驱动计划执行。

从状态中读取 current_step，将该步骤注入为 HumanMessage，
以便下游 LLM 节点对其采取行动，然后递增计数器。
plan_execute_router 边决定是否循环回去执行下一步，
或在计划耗尽时终止。
"""

from langchain_core.runnables import RunnableConfig

from typing import Any

import structlog
from langchain_core.messages import HumanMessage

from agent_framework.core.state import AgentState

logger = structlog.get_logger(__name__)


async def executor_node(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    """通过将当前计划步骤注入为消息来执行该步骤。"""
    plan = state.get("plan", [])
    current_step = state.get("current_step", 0)

    if current_step >= len(plan):
        return {}

    step = plan[current_step]
    logger.info("执行计划步骤", step=current_step, content=step)

    step_message = HumanMessage(content=f"Step {current_step + 1}: {step}")
    return {
        "messages": [step_message],
        "current_step": current_step + 1,
    }
