from __future__ import annotations

"""结果聚合节点。

多轮增强：仅聚合当前轮次（turn == turn_count）的子任务结果，
避免历史轮次的已完成任务干扰本轮回复生成。
"""

from typing import Any

import structlog
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from agent_framework.config.llm_config import get_llm
from agent_framework.config.settings import Settings, get_settings
from agent_framework.core.context import AgentContext
from agent_framework.agents.logistics.state import OrchestratorState, TaskStatus

logger = structlog.get_logger(__name__)

_AGGREGATOR_SYSTEM_PROMPT = """你是企业级物流供应链协调器，负责将多个子 Agent 的执行结果整合为清晰的最终回复。

要求：
- 用中文回复
- 直接给出结论和关键数据，不要重复用户的问题
- 如果有需要用户确认的事项，明确列出
- 如果某个子任务失败，告知用户并说明影响
- 语气专业、简洁
"""


async def result_aggregator_node(
    state: OrchestratorState,
    config: RunnableConfig,
) -> dict[str, Any]:
    """聚合当前轮次子任务结果，调用 LLM 生成最终回复。"""
    configurable = config.get("configurable", {})
    settings: Settings = configurable.get("settings") or get_settings()
    context: AgentContext = configurable.get("context", {})

    current_turn = state.get("turn_count", 0)

    # 只聚合当前轮次的任务
    sub_tasks = state.get("sub_tasks", [])
    completed = [t for t in sub_tasks if t.status == TaskStatus.COMPLETED and t.turn == current_turn]
    failed = [t for t in sub_tasks if t.status == TaskStatus.FAILED and t.turn == current_turn]

    logger.info(
        "result_aggregator",
        turn=current_turn,
        completed=len(completed),
        failed=len(failed),
        intent=state.get("intent"),
    )

    if not completed and not failed:
        msg = "未执行任何子任务，无法生成回复。"
        return {"messages": [AIMessage(content=msg)], "final_answer": msg}

    context_parts = [f"用户意图：{state.get('intent', '未知')}"]
    for task in completed:
        context_parts.append(f"\n[{task.agent_type.value}] 执行成功：\n{task.result}")
    for task in failed:
        context_parts.append(f"\n[{task.agent_type.value}] 执行失败：{task.error}")

    llm = get_llm(
        settings,
        provider=context.get("llm_provider"),
        model=context.get("model_name"),
        temperature=0.0,
    )
    response: AIMessage = await llm.ainvoke([
        SystemMessage(content=_AGGREGATOR_SYSTEM_PROMPT),
        HumanMessage(content=f"请根据以下子任务执行结果，生成最终回复：\n\n{''.join(context_parts)}"),
    ])
    final_answer = response.content

    return {"messages": [AIMessage(content=final_answer)], "final_answer": final_answer}
