from __future__ import annotations

"""任务预校验节点（人工补全缺失信息）。

在 analyze_and_plan 之后、第一次 dispatch 之前执行：
- 只校验没有前置任务依赖的任务（即排在最前面且字段无法由前面任务提供的任务）
- 若仍缺少必要信息，调用 interrupt() 暂停图并向用户提问
- 用户补充后，将补充内容追加到对应子任务的 instruction 尾部

有前置依赖的任务（如下单后审单）不在此处校验，
而是在 dispatch_node 执行前、注入前置上下文后再做校验（见 dispatch.py）。
"""

from typing import Any

import structlog
from langchain_core.runnables import RunnableConfig
from langgraph.types import interrupt

from agent_framework.agents.logistics.nodes.task_context import validate_task_fields
from agent_framework.agents.logistics.state import OrchestratorState, SubTask

logger = structlog.get_logger(__name__)

_AGENT_LABELS = {
    "place_order_agent":     "下单 Agent",
    "review_order_agent":    "审单 Agent",
    "exception_order_agent": "异常单处理 Agent",
    "skill_agent":           "Skill Agent",
}


def _format_question(gaps: list[dict]) -> str:
    lines = ["为了继续执行，需要您补充以下信息：\n"]
    for gap in gaps:
        lines.append(f"【{gap['agent_label']}】缺少：{' | '.join(gap['missing_fields'])}")
    lines.append("\n请直接输入补充信息（多项用逗号或换行分隔）：")
    return "\n".join(lines)


async def validate_tasks_node(
    state: OrchestratorState,
    config: RunnableConfig,  # noqa: ARG001 — kept for LangGraph node signature
) -> dict[str, Any]:
    """预校验当前轮次子任务，对无前置依赖且缺少必要信息的任务中断并询问用户。"""
    current_turn = state.get("turn_count", 1)
    tasks: list[SubTask] = [
        t for t in state.get("sub_tasks", []) if t.turn == current_turn
    ]

    # 将完整消息历史（含 AI 上一轮回复）拼成校验文本，
    # 支持"跟踪这个订单"等跨轮引用——历史消息中可能包含上轮生成的订单号等关键信息。
    # check_instruction=False 仍然排除当前轮 LLM 生成的 instruction，避免 AI 推断值误判为已提供。
    messages = state.get("messages", [])
    history_text: str = "\n".join(
        m.content for m in messages
        if hasattr(m, "content") and isinstance(m.content, str)
    )

    # 收集缺失字段（validate_task_fields 内部已处理前置任务依赖判断）
    gaps: list[dict] = []
    for task in tasks:
        missing = validate_task_fields(task, tasks, history_text, check_instruction=False)
        if missing:
            gaps.append({
                "task_id": task.task_id,
                "agent_type": task.agent_type.value,
                "agent_label": _AGENT_LABELS.get(task.agent_type.value, task.agent_type.value),
                "missing_fields": missing,
            })

    if not gaps:
        logger.debug("validate_tasks_ok", turn=current_turn, task_count=len(tasks))
        return {}

    logger.info(
        "validate_tasks_interrupt",
        turn=current_turn,
        gap_count=len(gaps),
        gaps=[f"{g['agent_type']}: {g['missing_fields']}" for g in gaps],
    )

    question = _format_question(gaps)
    supplement: str = interrupt({
        "type": "missing_info",
        "question": question,
        "gaps": gaps,
    })

    # 将补充信息追加到每个缺失任务的 instruction
    supplement_text = str(supplement or "").strip()
    updated: list[SubTask] = []
    for task in tasks:
        if any(g["task_id"] == task.task_id for g in gaps):
            new_instr = task.instruction.rstrip("。.") + f"\n【补充信息】{supplement_text}"
            updated.append(task.model_copy(update={"instruction": new_instr}))
        else:
            updated.append(task)

    logger.info("validate_tasks_resumed", turn=current_turn, supplement=supplement_text[:80])
    return {"sub_tasks": updated}
