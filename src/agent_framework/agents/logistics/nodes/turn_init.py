from __future__ import annotations

"""轮次初始化节点。

每次用户发起新消息时最先执行：
  1. turn_count +1（1-based，首轮为 1）
  2. 重置 orchestrator_iteration = 0（每轮 dispatch 循环独立计数）
  3. 清空 intent（上一轮意图不应干扰本轮规划）

注意：sub_tasks 在本节点不清空，保留历史任务用于轮次过滤；
      旧任务的清理由 turn_finalize 在轮末执行。
"""

from typing import Any

import structlog
from langchain_core.runnables import RunnableConfig

from agent_framework.agents.logistics.state import OrchestratorState

logger = structlog.get_logger(__name__)


async def turn_init_node(
    state: OrchestratorState,
    config: RunnableConfig,
) -> dict[str, Any]:
    """初始化新轮次状态。"""
    new_turn = state.get("turn_count", 0) + 1
    logger.info("turn_init", turn=new_turn, prev_intent=state.get("intent"))
    return {
        "turn_count": new_turn,
        "orchestrator_iteration": 0,
        "intent": None,
    }
