from __future__ import annotations

"""子任务分发节点 + 路由函数。

多轮增强：
  dispatch_node 和 dispatch_router 均按 current_turn 过滤 sub_tasks，
  确保上一轮已完成的任务不被重复处理。
"""

from typing import Any

import structlog
from langchain_core.runnables import RunnableConfig

from agent_framework.config.settings import Settings, get_settings
from agent_framework.core.context import AgentContext
from agent_framework.agents.logistics.dify_client import DifyClient
from agent_framework.agents.logistics.dify_registry import build_dify_registry
from agent_framework.agents.logistics.state import OrchestratorState, SubTask, TaskStatus

logger = structlog.get_logger(__name__)

_MAX_RETRY = 1  # 单任务最大重试次数


async def dispatch_node(
    state: OrchestratorState,
    config: RunnableConfig,
) -> dict[str, Any]:
    """取当前轮次第一个 PENDING 任务，调用对应 Dify Agent，更新任务状态。"""
    configurable = config.get("configurable", {})
    settings: Settings = configurable.get("settings") or get_settings()
    context: AgentContext = configurable.get("context", {})

    dify_registry: dict = configurable.get("dify_registry") or build_dify_registry(settings)

    current_turn = state.get("turn_count", 0)
    iteration = state.get("orchestrator_iteration", 0) + 1

    # 仅处理当前轮次的 PENDING 任务
    pending = [
        t for t in state.get("sub_tasks", [])
        if t.status == TaskStatus.PENDING and t.turn == current_turn
    ]
    if not pending:
        return {"orchestrator_iteration": iteration}

    task: SubTask = pending[0]
    client: DifyClient | None = dify_registry.get(task.agent_type)

    if client is None:
        updated = task.model_copy(
            update={
                "status": TaskStatus.FAILED,
                "error": f"未找到 agent 类型 {task.agent_type} 的 Dify 客户端",
            }
        )
        logger.warning("dispatch_no_client", agent_type=task.agent_type, task_id=task.task_id)
        return {"sub_tasks": [updated], "orchestrator_iteration": iteration}

    user_id = context.get("user_id", "orchestrator")
    logger.info(
        "dispatch_task_start",
        task_id=task.task_id,
        agent_type=task.agent_type.value,
        turn=current_turn,
        iteration=iteration,
    )

    try:
        result = await client.run(instruction=task.instruction, user=user_id)
        updated = task.model_copy(update={"status": TaskStatus.COMPLETED, "result": result})
        logger.info("dispatch_task_done", task_id=task.task_id, agent_type=task.agent_type.value)
    except Exception as exc:
        retry = task.retry_count + 1
        if retry <= _MAX_RETRY:
            updated = task.model_copy(
                update={"status": TaskStatus.PENDING, "retry_count": retry, "error": str(exc)}
            )
            logger.warning("dispatch_task_retry", task_id=task.task_id, retry=retry, error=str(exc))
        else:
            updated = task.model_copy(
                update={"status": TaskStatus.FAILED, "retry_count": retry, "error": str(exc)}
            )
            logger.error(
                "dispatch_task_failed",
                task_id=task.task_id,
                agent_type=task.agent_type.value,
                error=str(exc),
            )
        return {
            "sub_tasks": [updated],
            "orchestrator_iteration": iteration,
            "errors": [f"[{task.agent_type.value}] {exc}"],
        }

    return {"sub_tasks": [updated], "orchestrator_iteration": iteration}


def dispatch_router(state: OrchestratorState) -> str:
    """决定下一步：继续分发当前轮次的任务 or 汇总结果。"""
    current_turn = state.get("turn_count", 0)
    iteration = state.get("orchestrator_iteration", 0)

    if iteration >= 10:
        logger.warning("dispatch_max_iterations_reached", iteration=iteration, turn=current_turn)
        return "result_aggregator"

    pending = [
        t for t in state.get("sub_tasks", [])
        if t.status == TaskStatus.PENDING and t.turn == current_turn
    ]
    return "dispatch" if pending else "result_aggregator"
