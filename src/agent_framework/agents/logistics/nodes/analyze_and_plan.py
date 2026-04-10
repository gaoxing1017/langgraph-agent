from __future__ import annotations

"""意图识别 + 任务规划节点（合并为一次 LLM 调用）。

多轮增强：
  - SubTask 打上当前 turn_count 标记，供 dispatch/aggregator 过滤
  - 系统提示注入：task_history（历史轮次）/ active_orders / active_shipments / short_term_summary
  - TaskPlan 新增 referenced_orders / referenced_shipments，turn_finalize 据此更新业务上下文
"""

import uuid
from typing import Any

import structlog
from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from agent_framework.config.llm_config import get_llm
from agent_framework.config.settings import Settings, get_settings
from agent_framework.core.context import AgentContext
from agent_framework.agents.logistics.state import (
    LogisticsAgentType,
    OrchestratorState,
    SubTask,
    TaskStatus,
    TurnRecord,
    _to_turn_record,
)

logger = structlog.get_logger(__name__)

ANALYZE_AND_PLAN_SYSTEM_PROMPT = """你是一个企业级物流供应链智能协调器。

你的任务：
1. 结合历史操作记录理解用户的当前请求（用户可能引用了上一轮的结果）
2. 将请求拆解为需要调用的子任务序列

可用的子 Agent 类型及职责：
- order_agent      : 订单查询、创建、修改、取消、状态变更
- inventory_agent  : 库存查询、预留、调拨、盘点
- transport_agent  : 承运商选择、路线规划、运单预订、运力调度
- warehouse_agent  : 入库、出库、拣货、上架、库位管理
- supplier_agent   : 供应商查询、询价、采购单、绩效查看
- customs_agent    : 报关单生成、HS 编码查询、合规检查、清关状态
- tracking_agent   : 货物实时追踪、异常预警、ETA 查询
- analytics_agent  : 供应链 KPI 分析、预测、优化建议

规则：
- 按实际需要选择最少的 agent 类型
- 每个子任务的 instruction 用中文写清楚具体操作和关键参数
- 子任务顺序代表执行优先级（串行执行）
- 如果一个请求只需要一个 agent，sub_tasks 列表只写一项
- referenced_orders / referenced_shipments 填写本轮涉及的单号（没有则为空列表）
"""


def _format_task_history(history: list[TurnRecord]) -> str:
    if not history:
        return "（首轮对话，无历史记录）"
    lines = []
    for r in history[-5:]:
        agents = "、".join(r.agents_used) if r.agents_used else "无子任务"
        summary = r.result_summary[:80] + "…" if len(r.result_summary) > 80 else r.result_summary
        lines.append(f"  第{r.turn}轮 | {r.intent} → [{agents}] → {summary}")
    return "\n".join(lines)


class SubTaskSpec(BaseModel):
    agent_type: LogisticsAgentType
    instruction: str


class TaskPlan(BaseModel):
    intent: str
    sub_tasks: list[SubTaskSpec]
    referenced_orders: list[str] = Field(default_factory=list)
    referenced_shipments: list[str] = Field(default_factory=list)


async def analyze_and_plan_node(
    state: OrchestratorState,
    config: RunnableConfig,
) -> dict[str, Any]:
    """识别用户意图，生成打上轮次标记的子任务列表。"""
    configurable = config.get("configurable", {})
    settings: Settings = configurable.get("settings") or get_settings()
    context: AgentContext = configurable.get("context", {})

    current_turn = state.get("turn_count", 1)
    task_history = [_to_turn_record(t) for t in state.get("task_history", [])]

    # ── 构建多轮感知的系统提示 ─────────────────────────────────────────────
    system_content = ANALYZE_AND_PLAN_SYSTEM_PROMPT
    system_content += f"\n\n【当前第 {current_turn} 轮对话】"

    if task_history:
        system_content += f"\n\n【历史操作记录（近5轮）】\n{_format_task_history(task_history)}"

    if active_orders := state.get("active_orders", []):
        system_content += f"\n\n【本会话关联订单】{', '.join(active_orders)}"

    if active_shipments := state.get("active_shipments", []):
        system_content += f"\n\n【本会话关联运单】{', '.join(active_shipments)}"

    if summary := state.get("short_term_summary"):
        system_content += f"\n\n【会话摘要】\n{summary}"

    if prefs := state.get("user_preferences"):
        system_content += f"\n\n【用户偏好】{prefs}"

    llm = get_llm(
        settings,
        provider=context.get("llm_provider"),
        model=context.get("model_name"),
        temperature=0.0,
    )
    planner_llm = llm.with_structured_output(TaskPlan)

    messages = [SystemMessage(content=system_content)] + list(state.get("messages", []))

    logger.debug("analyze_and_plan_node 开始", turn=current_turn, message_count=len(state.get("messages", [])))
    plan: TaskPlan = await planner_llm.ainvoke(messages)

    # 每个 SubTask 打上当前轮次标记
    sub_tasks = [
        SubTask(
            task_id=str(uuid.uuid4())[:8],
            turn=current_turn,
            agent_type=spec.agent_type,
            instruction=spec.instruction,
            status=TaskStatus.PENDING,
        )
        for spec in plan.sub_tasks
    ]

    logger.info(
        "任务规划完成",
        turn=current_turn,
        intent=plan.intent,
        task_count=len(sub_tasks),
        agent_types=[t.agent_type.value for t in sub_tasks],
    )

    # 合并本轮提取的业务实体
    updates: dict[str, Any] = {
        "intent": plan.intent,
        "sub_tasks": sub_tasks,
        "orchestrator_iteration": 0,
    }
    if plan.referenced_orders:
        existing = state.get("active_orders", [])
        updates["active_orders"] = list(dict.fromkeys(existing + plan.referenced_orders))[:20]
    if plan.referenced_shipments:
        existing = state.get("active_shipments", [])
        updates["active_shipments"] = list(dict.fromkeys(existing + plan.referenced_shipments))[:20]

    return updates
