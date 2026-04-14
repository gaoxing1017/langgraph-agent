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
from agent_framework.agents.logistics.skill_registry import SkillRegistry
from agent_framework.agents.logistics.state import (
    LogisticsAgentType,
    OrchestratorState,
    SubTask,
    TaskStatus,
    TurnRecord,
    _to_turn_record,
)

logger = structlog.get_logger(__name__)

ANALYZE_AND_PLAN_SYSTEM_PROMPT = """你是一个企业级供应链智能协调器。

你的任务：
1. 结合历史操作记录理解用户的当前请求（用户可能引用了上一轮的结果）
2. 将请求拆解为需要调用的子任务序列

可用的子 Agent 类型及职责：
- place_order_agent      : 创建新订单，包含商品明细、数量、收货信息、支付方式、交货日期等
- review_order_agent     : 审核订单，校验客户信用、库存可用性、价格合规、地址白名单等
- exception_order_agent  : 处理异常订单，包括货损索赔、补发、异常标记解除、责任认定等
- skill_agent            : 执行已注册的自定义 Skill（skill_name 字段指定具体 Skill 名称，见下方【已注册 Skill】）

路由规则：
- 用户明确要"下单"、"创建订单"、"新建订单" → place_order_agent
- 用户要"审核"、"审批"、"核单" → review_order_agent
- 用户提到"异常"、"破损"、"丢件"、"延误"、"投诉"、"补发" → exception_order_agent
- 用户要查订单"状态"、"进度"、"物流"、"追踪" → skill_agent（skill_name="query_order_status"）
- 用户要查"客户"、"买家"、"信用"、"授信"、"联系方式" → skill_agent（skill_name="query_customer_info"）
- 用户要查"商品"、"SKU"、"产品"、"规格"、"价格" → skill_agent（skill_name="query_product_info"）
- 下单前如需确认商品价格可先用 skill_agent（query_product_info），再调用 place_order_agent，请根据业务逻辑判断是否需要多步骤任务

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
    skill_name: str | None = None   # agent_type == "skill_agent" 时必填


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
    skill_registry: SkillRegistry | None = configurable.get("skill_registry")

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

    if skill_registry and not skill_registry.is_empty():
        system_content += f"\n\n【已注册 Skill】\n{skill_registry.prompt_description()}"
        system_content += "\n\n使用 skill_agent 时，必须在 skill_name 字段填写具体的 Skill 名称（如 calc_shipping_cost）。"

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
            skill_name=spec.skill_name,
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
