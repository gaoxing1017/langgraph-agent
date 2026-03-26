from __future__ import annotations

"""人机协同（HITL）节点。

调用 interrupt() 挂起图并将控制权归还给 API 调用方。
LangGraph 在此时对完整状态进行 checkpoint。当调用方发送以下请求时恢复执行：

    await graph.ainvoke(Command(resume=<bool>), config=config)

False → 操作被拒绝；注入错误消息和拒绝回复。
True  → 节点返回空字典，图正常继续执行。
"""

from langchain_core.runnables import RunnableConfig

from typing import Any

from langgraph.types import interrupt

from agent_framework.core.state import AgentState


async def human_node(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    """暂停图执行并请求人工审批。

    图在此处挂起并将中断载荷返回给调用方。
    通过调用 graph.ainvoke(Command(resume=True/False), config=...) 恢复执行。
    """
    metadata = state.get("metadata", {})
    pending_action = metadata.get("pending_action", "Action requires approval")

    # interrupt() 内部抛出 NodeInterrupt；LangGraph 捕获它，
    # 对当前状态进行 checkpoint，并将载荷暴露给 API 调用方。
    approved: bool = interrupt(
        {
            "message": "Human approval required",
            "pending_action": pending_action,
            "thread_id": state.get("thread_id"),
        }
    )

    if not approved:
        return {
            "errors": ["Action rejected by human reviewer"],
            "final_answer": "Action was not approved by the reviewer.",
        }

    return {}
