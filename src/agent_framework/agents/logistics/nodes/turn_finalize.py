from __future__ import annotations

"""轮次收尾节点（替换原 memory_save_node）。

每轮执行完毕后负责：
  1. 归档本轮到 task_history（TurnRecord）
  2. 清理 sub_tasks —— 仅保留本轮任务（reset sentinel + 本轮条目）
  3. 消息裁剪 —— 超出 KEEP_LAST_MESSAGES 时用 RemoveMessage 删除旧消息
  4. 每轮必生成摘要 —— 基于 task_history 而非原始 messages，省 token 且稳定
  5. 提取业务实体 —— 更新 active_orders / active_shipments
  6. 持久化到 Store（memory_enabled=True 且 store 可用时）
"""

import re
import time
from typing import Any

import structlog
from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from agent_framework.config.llm_config import get_llm
from agent_framework.config.settings import Settings, get_settings
from agent_framework.core.context import AgentContext
from agent_framework.agents.logistics.state import (
    OrchestratorState,
    TaskStatus,
    TurnRecord,
    _to_turn_record,
)

logger = structlog.get_logger(__name__)

# 订单 / 运单号提取正则
_ORDER_PATTERN = re.compile(r"\b(?:SO|PO|ORD|订单)[- _]?[A-Z0-9\-]{3,20}\b", re.IGNORECASE)
_SHIPMENT_PATTERN = re.compile(r"\b(?:SF|YT|JD|运单|WH|TMS)[A-Z0-9\-]{5,20}\b", re.IGNORECASE)

_SUMMARIZE_SYSTEM_PROMPT = (
    "你是物流供应链助手。请根据近几轮操作记录，用2-3句中文总结当前会话的状态，"
    "包含最新完成的操作、关键数据和未完成事项（如有）。语气简洁专业。"
)


async def turn_finalize_node(
    state: OrchestratorState,
    config: RunnableConfig,
) -> dict[str, Any]:
    """轮次收尾：归档 → 清理 → 裁剪 → 摘要 → 持久化。"""
    configurable = config.get("configurable", {})
    settings: Settings = configurable.get("settings") or get_settings()
    context: AgentContext = configurable.get("context", {})

    current_turn = state.get("turn_count", 1)
    sub_tasks = state.get("sub_tasks", [])
    current_tasks = [t for t in sub_tasks if t.turn == current_turn]
    completed = [t for t in current_tasks if t.status == TaskStatus.COMPLETED]

    result: dict[str, Any] = {}

    # ── 1. 归档本轮 ─────────────────────────────────────────────────────────
    new_record = TurnRecord(
        turn=current_turn,
        intent=state.get("intent") or "",
        agents_used=[t.agent_type.value for t in completed],
        result_summary=(state.get("final_answer") or "")[:300],
        timestamp=int(time.time()),
    )
    existing_history = [_to_turn_record(t) for t in state.get("task_history", [])]
    new_history = (existing_history + [new_record])[-settings.ORCHESTRATOR_TASK_HISTORY_SIZE:]
    result["task_history"] = new_history

    # ── 2. 清理 sub_tasks：保留本轮，丢弃旧轮 ──────────────────────────────
    # __reset__ sentinel 触发 _merge_sub_tasks 清空后重建
    result["sub_tasks"] = [{"__reset__": True}] + [
        t.model_dump() for t in current_tasks
    ]

    # ── 3. 消息裁剪 ──────────────────────────────────────────────────────────
    messages = state.get("messages", [])
    keep = settings.ORCHESTRATOR_KEEP_LAST_MESSAGES
    if len(messages) > keep:
        to_remove = messages[:-keep]
        result["messages"] = [RemoveMessage(id=m.id) for m in to_remove]
        logger.info(
            "messages_trimmed",
            removed=len(to_remove),
            kept=keep,
            turn=current_turn,
        )

    # ── 4. 每轮生成摘要（基于 task_history，省 token）────────────────────────
    summary = await _generate_summary(new_history, current_turn, config)
    if summary:
        result["short_term_summary"] = summary

    # ── 5. 提取业务实体（订单 / 运单）────────────────────────────────────────
    all_instructions = " ".join(t.instruction for t in current_tasks)
    new_orders = _ORDER_PATTERN.findall(all_instructions)
    new_shipments = _SHIPMENT_PATTERN.findall(all_instructions)

    if new_orders:
        existing = state.get("active_orders", [])
        result["active_orders"] = list(dict.fromkeys(existing + new_orders))[:20]

    if new_shipments:
        existing = state.get("active_shipments", [])
        result["active_shipments"] = list(dict.fromkeys(existing + new_shipments))[:20]

    # ── 6. 持久化到 Store ────────────────────────────────────────────────────
    store = configurable.get("store")
    if context.get("memory_enabled", True) and store:
        await _persist_to_store(state, config, new_record, summary)

    logger.info(
        "turn_finalize_done",
        turn=current_turn,
        completed=len(completed),
        history_size=len(new_history),
        messages_kept=min(len(messages), keep),
    )
    return result


async def _generate_summary(
    task_history: list[TurnRecord],
    current_turn: int,
    config: RunnableConfig,
) -> str:
    """基于结构化 task_history 生成会话摘要，避免传入原始 messages。"""
    configurable = config.get("configurable", {})
    settings: Settings = configurable.get("settings") or get_settings()
    context: AgentContext = configurable.get("context", {})

    llm = get_llm(settings, provider=context.get("llm_provider"), temperature=0.0)

    recent = task_history[-3:]
    if not recent:
        return ""

    history_text = "\n".join(
        f"第{r.turn}轮 [{r.intent}] → {', '.join(r.agents_used) or '无'} → {r.result_summary[:120]}"
        for r in recent
    )

    try:
        resp = await llm.ainvoke([
            SystemMessage(content=_SUMMARIZE_SYSTEM_PROMPT),
            HumanMessage(content=f"近期操作记录（共{current_turn}轮）：\n{history_text}"),
        ])
        return resp.content
    except Exception as exc:
        logger.warning("summary_generation_failed", error=str(exc))
        return ""


async def _persist_to_store(
    state: OrchestratorState,
    config: RunnableConfig,
    record: TurnRecord,
    summary: str,
) -> None:
    """将情景记忆和摘要写入 PostgreSQL Store。"""
    configurable = config.get("configurable", {})
    context: AgentContext = configurable.get("context", {})
    store = configurable.get("store")

    user_id = context.get("user_id", "anonymous")
    tenant_id = context.get("tenant_id", "default")
    thread_id = state.get("thread_id", "")

    try:
        # 情景记忆
        await store.aput(
            namespace=("logistics", "episodes", tenant_id, user_id),
            key=f"{thread_id}_{record.turn}_{record.timestamp}",
            value=record.model_dump(),
        )
        # 摘要
        if summary:
            await store.aput(
                namespace=("logistics", "summaries"),
                key=f"summary/{thread_id}",
                value={"summary": summary, "turn": record.turn},
            )
        logger.debug("store_persisted", turn=record.turn, thread_id=thread_id)
    except Exception as exc:
        logger.warning("store_persist_error", error=str(exc))
