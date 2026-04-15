from __future__ import annotations

"""子任务分发节点 + 路由函数。

每次循环处理当前轮次第一个 PENDING 任务，流程如下：
  1. inject_predecessor_context() — 注入本轮已完成任务的关键实体到 instruction 前缀
  2. validate_task_fields()       — 校验注入后是否还有缺失字段
  3. 若缺失 → interrupt() 等待用户补充，resume 后继续
  4. 若完整 → 调用 SubAgentClient.run()，结果写回 sub_tasks

多轮增强：所有过滤均按 current_turn，确保历史轮次任务不影响当前轮次。
"""

from typing import Any

import structlog
from langchain_core.runnables import RunnableConfig
from langgraph.types import interrupt

from agent_framework.agents.logistics.base_client import SubAgentClient
from agent_framework.agents.logistics.dify_registry import build_dify_registry
from agent_framework.agents.logistics.nodes.task_context import (
    inject_predecessor_context,
    validate_task_fields,
)
from agent_framework.agents.logistics.skill_client import SkillClient
from agent_framework.agents.logistics.skill_registry import SkillRegistry
from agent_framework.agents.logistics.state import LogisticsAgentType, OrchestratorState, SubTask, TaskStatus
from agent_framework.config.settings import Settings, get_settings
from agent_framework.core.context import AgentContext

logger = structlog.get_logger(__name__)

_MAX_RETRY = 1

_AGENT_LABELS = {
    "place_order_agent":     "下单 Agent",
    "review_order_agent":    "审单 Agent",
    "exception_order_agent": "异常单处理 Agent",
    "skill_agent":           "Skill Agent",
}


async def dispatch_node(
    state: OrchestratorState,
    config: RunnableConfig,
) -> dict[str, Any]:
    """注入前置上下文 → 校验 → 执行当前轮次第一个 PENDING 任务。"""
    configurable  = config.get("configurable", {})
    settings: Settings = configurable.get("settings") or get_settings()
    context: AgentContext = configurable.get("context", {})
    dify_registry: dict = configurable.get("dify_registry") or build_dify_registry(settings)
    skill_registry: SkillRegistry | None = configurable.get("skill_registry")

    current_turn = state.get("turn_count", 0)
    iteration    = state.get("orchestrator_iteration", 0) + 1
    all_tasks    = state.get("sub_tasks", [])

    pending = [t for t in all_tasks if t.status == TaskStatus.PENDING and t.turn == current_turn]
    if not pending:
        return {"orchestrator_iteration": iteration}

    task: SubTask = pending[0]

    # ── 1. 注入前置任务上下文 ─────────────────────────────────────────────────
    enriched_task = inject_predecessor_context(task, all_tasks, current_turn)
    if enriched_task.instruction != task.instruction:
        logger.info(
            "dispatch_context_injected",
            task_id=task.task_id,
            agent_type=task.agent_type.value,
        )

    # ── 2. 执行前字段校验（注入后仍缺则中断）────────────────────────────────
    messages = state.get("messages", [])
    # 完整历史文本：历史 AI 回复中可能包含订单号等跨轮信息
    history_text: str = "\n".join(
        m.content for m in messages
        if hasattr(m, "content") and isinstance(m.content, str)
    )
    missing = validate_task_fields(enriched_task, all_tasks, history_text)

    if missing:
        agent_label = _AGENT_LABELS.get(task.agent_type.value, task.agent_type.value)
        gap = {
            "task_id": task.task_id,
            "agent_type": task.agent_type.value,
            "agent_label": agent_label,
            "missing_fields": missing,
        }
        question = (
            f"执行【{agent_label}】时仍缺少以下信息：{' | '.join(missing)}\n"
            "请补充后继续："
        )
        logger.info("dispatch_interrupt_missing", task_id=task.task_id, missing=missing)

        supplement: str = interrupt({
            "type": "missing_info",
            "question": question,
            "gaps": [gap],
        })
        supplement_text = str(supplement or "").strip()
        enriched_task = enriched_task.model_copy(
            update={"instruction": enriched_task.instruction.rstrip("。.") + f"\n【补充信息】{supplement_text}"}
        )

    # ── 3. 调用子 Agent ───────────────────────────────────────────────────────
    client: SubAgentClient | None = dify_registry.get(task.agent_type)

    if client is None and task.agent_type == LogisticsAgentType.SKILL and skill_registry and task.skill_name:
        client = SkillClient(skill_registry, task.skill_name)

    if client is None:
        failed = task.model_copy(update={
            "status": TaskStatus.FAILED,
            "error": f"未找到 agent 类型 {task.agent_type} 的客户端，请在注册表中配置",
        })
        logger.warning("dispatch_no_client", agent_type=task.agent_type, task_id=task.task_id)
        return {"sub_tasks": [failed], "orchestrator_iteration": iteration}

    user_id = context.get("user_id", "orchestrator")
    logger.info(
        "dispatch_task_start",
        task_id=task.task_id,
        agent_type=task.agent_type.value,
        turn=current_turn,
        iteration=iteration,
    )

    try:
        result = await client.run(instruction=enriched_task.instruction, user=user_id)
        completed = task.model_copy(update={"status": TaskStatus.COMPLETED, "result": result})
        logger.info("dispatch_task_done", task_id=task.task_id, agent_type=task.agent_type.value)
        return {"sub_tasks": [completed], "orchestrator_iteration": iteration}

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


def dispatch_router(state: OrchestratorState) -> str:
    """决定下一步：继续分发当前轮次的任务 or 汇总结果。"""
    current_turn = state.get("turn_count", 0)
    iteration    = state.get("orchestrator_iteration", 0)

    if iteration >= 10:
        logger.warning("dispatch_max_iterations_reached", iteration=iteration, turn=current_turn)
        return "result_aggregator"

    pending = [
        t for t in state.get("sub_tasks", [])
        if t.status == TaskStatus.PENDING and t.turn == current_turn
    ]
    return "dispatch" if pending else "result_aggregator"
