"""A2A JSON-RPC 服务端处理器。

通过 POST /a2a 接收入站任务委派，并根据 JSON-RPC 方法名
路由到相应的处理函数。

支持的方法：
  tasks/send   — 创建新任务并同步调用图
  tasks/get    — 轮询已有任务的当前状态
  tasks/cancel — 取消待处理或进行中的任务

注意：_task_manager 当前为模块级单例。
对于多实例生产部署，请改为通过 FastAPI app.state 注入。
"""

from __future__ import annotations

from typing import Any

import structlog
from langchain_core.messages import HumanMessage

from agent_framework.a2a.schemas import Artifact, TaskState
from agent_framework.a2a.task_manager import TaskManager

logger = structlog.get_logger(__name__)

_task_manager = TaskManager()


async def handle_jsonrpc(body: dict[str, Any], app_state: Any) -> dict[str, Any]:
    """将 A2A JSON-RPC 方法调用路由到相应的处理函数。"""
    method = body.get("method", "")
    params = body.get("params", {})
    rpc_id = body.get("id", 1)

    try:
        if method == "tasks/send":
            result = await _handle_tasks_send(params, app_state)
        elif method == "tasks/get":
            result = await _handle_tasks_get(params)
        elif method == "tasks/cancel":
            result = await _handle_tasks_cancel(params)
        else:
            return _error_response(rpc_id, -32601, f"方法未找到：{method}")
        return {"jsonrpc": "2.0", "result": result, "id": rpc_id}
    except Exception as exc:
        logger.error("A2A 处理器错误", method=method, error=str(exc))
        return _error_response(rpc_id, -32603, str(exc))


async def _handle_tasks_send(params: dict, app_state: Any) -> dict:
    message_data = params.get("message", {})
    session_id = params.get("sessionId", "")
    content = message_data.get("content", "")

    task = _task_manager.create_task(session_id=session_id)
    _task_manager.update_state(task.task_id, TaskState.WORKING)

    try:
        graph = getattr(app_state, "graph", None)
        settings = getattr(app_state, "settings", None)
        if graph and settings:
            config = {"configurable": {"thread_id": task.task_id, "settings": settings, "context": {}}}
            result = await graph.ainvoke({"messages": [HumanMessage(content=content)]}, config=config)
            answer = result.get("final_answer") or ""
            if not answer and result.get("messages"):
                answer = result["messages"][-1].content
            _task_manager.add_artifact(task.task_id, Artifact(content=answer))
        _task_manager.update_state(task.task_id, TaskState.COMPLETED)
    except Exception as exc:
        _task_manager.update_state(task.task_id, TaskState.FAILED)
        task.metadata["error"] = str(exc)

    updated = _task_manager.get_task(task.task_id)
    return updated.model_dump() if updated else {}


async def _handle_tasks_get(params: dict) -> dict:
    task_id = params.get("taskId", "")
    task = _task_manager.get_task(task_id)
    if not task:
        raise ValueError(f"任务未找到：{task_id}")
    return task.model_dump()


async def _handle_tasks_cancel(params: dict) -> dict:
    task_id = params.get("taskId", "")
    canceled = _task_manager.cancel_task(task_id)
    return {"taskId": task_id, "canceled": canceled}


def _error_response(rpc_id: int, code: int, message: str) -> dict:
    """构建 JSON-RPC 2.0 错误响应信封。"""
    return {"jsonrpc": "2.0", "error": {"code": code, "message": message}, "id": rpc_id}
