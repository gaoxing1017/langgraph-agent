from __future__ import annotations

"""规划节点：生成结构化执行计划。

使用 with_structured_output(Plan) 强制 LLM 返回类型化的步骤列表。
计划写入 state["plan"]，current_step 重置为 0。
系统提示无条件前置，以引导规划过程。
"""

from langchain_core.runnables import RunnableConfig

from typing import Any

import structlog
from langchain_core.messages import SystemMessage
from pydantic import BaseModel

from agent_framework.config.llm_config import get_llm
from agent_framework.config.settings import Settings
from agent_framework.core.context import AgentContext
from agent_framework.core.state import AgentState

logger = structlog.get_logger(__name__)

PLANNER_SYSTEM_PROMPT = """You are an expert planner. Given a user request, break it down into
a clear, ordered list of actionable steps. Each step should be concrete and executable.
Return ONLY the list of steps, nothing else."""


class Plan(BaseModel):
    steps: list[str]


async def planner_node(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    """从用户请求生成结构化执行计划。"""
    configurable = config.get("configurable", {})
    settings: Settings = configurable.get("settings")
    context: AgentContext = configurable.get("context", {})

    llm = get_llm(settings, provider=context.get("llm_provider"), model=context.get("model_name"))
    planner_llm = llm.with_structured_output(Plan)

    # 将规划指令前置于对话历史，确保无论之前的消息内容如何，
    # LLM 都能始终收到规划提示。
    messages = [SystemMessage(content=PLANNER_SYSTEM_PROMPT)] + list(state.get("messages", []))
    logger.debug("planner_node 被调用")

    plan: Plan = await planner_llm.ainvoke(messages)
    logger.info("计划已生成", step_count=len(plan.steps))

    return {"plan": plan.steps, "current_step": 0}
