from __future__ import annotations

"""物流供应链协调器状态定义。

多轮对话关键设计：
  - SubTask.turn     : 标记所属轮次，dispatch/aggregator 按当前轮次过滤
  - TurnRecord       : 每轮结束后归档到 task_history，注入规划上下文
  - task_history     : last-write-wins reducer，turn_finalize 负责裁剪到最大长度
  - _merge_sub_tasks : 支持 __reset__ sentinel，turn_finalize 用于清理旧轮次任务
"""

import operator
from enum import Enum
from typing import Annotated, Any, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel

from agent_framework.core.state import AgentState


class LogisticsAgentType(str, Enum):
    PLACE_ORDER      = "place_order_agent"       # 下单 Agent
    REVIEW_ORDER     = "review_order_agent"      # 审单 Agent
    EXCEPTION_ORDER  = "exception_order_agent"   # 异常单处理 Agent
    ORDER_QUERY      = "order_query_agent"       # 订单信息查询 Agent
    CUSTOMER_QUERY   = "customer_query_agent"    # 客户信息查询 Agent
    PRODUCT_QUERY    = "product_query_agent"     # 商品信息查询 Agent
    SKILL            = "skill_agent"             # 通用 Skill 节点


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class SubTask(BaseModel):
    task_id: str
    turn: int = 0                    # 所属轮次，用于多轮隔离
    agent_type: LogisticsAgentType
    skill_name: str | None = None    # agent_type == SKILL 时指定具体 skill
    instruction: str
    status: TaskStatus = TaskStatus.PENDING
    result: str | None = None
    error: str | None = None
    retry_count: int = 0


class TurnRecord(BaseModel):
    """单轮对话的归档摘要，注入 analyze_and_plan 的规划上下文。"""
    turn: int
    intent: str
    agents_used: list[str]
    result_summary: str              # final_answer 前 300 字
    timestamp: int


# ── reducers ──────────────────────────────────────────────────────────────────

def _to_subtask(item: Any) -> SubTask:
    """兼容 Pydantic 对象与 checkpoint 反序列化的 dict。"""
    if isinstance(item, SubTask):
        return item
    return SubTask(**item)


def _to_turn_record(item: Any) -> TurnRecord:
    if isinstance(item, TurnRecord):
        return item
    return TurnRecord(**item)


def _merge_sub_tasks(existing: list, updates: list) -> list[SubTask]:
    """按 task_id 合并子任务。
    若 updates 首项为 {"__reset__": True}，则清空 existing 后仅保留后续条目。
    turn_finalize 用此机制归档旧轮次任务。
    """
    if updates and isinstance(updates[0], dict) and updates[0].get("__reset__"):
        tail = updates[1:]
        return [_to_subtask(t) for t in tail] if tail else []

    merged: dict[str, SubTask] = {_to_subtask(t).task_id: _to_subtask(t) for t in existing}
    for item in updates:
        st = _to_subtask(item)
        merged[st.task_id] = st
    return list(merged.values())


def _replace_task_history(existing: list, updates: list) -> list[TurnRecord]:
    """last-write-wins：turn_finalize 每轮覆盖整个列表（含裁剪）。"""
    return [_to_turn_record(t) for t in updates]


# ── state ─────────────────────────────────────────────────────────────────────

class OrchestratorState(AgentState):
    """物流协调器完整状态 — 持久化到 checkpoint。"""

    # 当前轮意图
    intent: str | None

    # 子任务列表：支持 reset sentinel 的 merge reducer
    sub_tasks: Annotated[list[SubTask], _merge_sub_tasks]

    # 业务上下文
    active_orders: list[str]
    active_shipments: list[str]
    business_context: dict[str, Any]

    # 记忆层
    short_term_summary: str | None
    user_preferences: dict[str, Any]

    # 多轮管理
    turn_count: int                                              # 当前轮次编号（1-based）
    task_history: Annotated[list[TurnRecord], _replace_task_history]  # 历史轮次摘要

    # 编排控制
    orchestrator_iteration: int
    escalation_reason: str | None


# ── output schema ──────────────────────────────────────────────────────────────

class LogisticsOutputState(TypedDict, total=False):
    """ainvoke / 前端可见的输出字段子集。"""
    messages: Annotated[list[AnyMessage], add_messages]
    final_answer: str | None
    errors: Annotated[list[str], operator.add]
    sub_tasks: Annotated[list[SubTask], _merge_sub_tasks]
    turn_count: int
    intent: str | None
    active_orders: list[str]
    active_shipments: list[str]
