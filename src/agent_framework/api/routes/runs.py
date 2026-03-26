from __future__ import annotations

import uuid
from typing import Any, AsyncIterator

import structlog
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage

from agent_framework.api.schemas.requests import RunRequest
from agent_framework.api.schemas.responses import MessageOutput, RunResponse
from agent_framework.core.context import AgentContext

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/runs", tags=["runs"])


def _build_context(body: RunRequest) -> AgentContext:
    """将 API 请求字段映射为图调用所需的 AgentContext。"""
    return AgentContext(
        user_id=body.user_id,
        tenant_id=body.tenant_id,
        llm_provider=body.llm_provider or "openai",
        tools_enabled=body.tools_enabled,
        memory_enabled=body.memory_enabled,
        streaming=body.stream,
        max_iterations=20,
    )


@router.post("", response_model=RunResponse)
async def create_run(body: RunRequest, request: Request):
    """为单轮对话执行智能体图。

    支持两种响应模式：
    - 同步模式（stream=false）：等待完整执行，返回 RunResponse JSON。
    - 流式模式（stream=true）：返回 text/event-stream 的增量 token。
    """
    graph = getattr(request.app.state, "graph", None)
    if graph is None:
        raise HTTPException(status_code=503, detail="图未初始化")

    thread_id = body.thread_id or str(uuid.uuid4())
    run_id = str(uuid.uuid4())
    context = _build_context(body)
    settings = request.app.state.settings

    messages = [HumanMessage(content=m.content) for m in body.messages if m.role == "user"]
    input_state = {"messages": messages, "thread_id": thread_id, "request_id": run_id}

    config = {
        "configurable": {
            "thread_id": thread_id,
            "settings": settings,
            "context": context,
        },
        "recursion_limit": 40,
    }

    if body.stream:
        async def event_stream() -> AsyncIterator[str]:
            async for event in graph.astream_events(input_state, config=config, version="v2"):
                if event["event"] == "on_chat_model_stream":
                    chunk = event["data"].get("chunk", "")
                    content = getattr(chunk, "content", "")
                    if content:
                        yield f"data: {content}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    try:
        result = await graph.ainvoke(input_state, config=config)
        out_messages = [
            MessageOutput(
                role=getattr(m, "type", type(m).__name__.lower().replace("message", "")),
                content=m.content,
            )
            for m in result.get("messages", [])
            if hasattr(m, "content")
        ]
        return RunResponse(
            run_id=run_id,
            thread_id=thread_id,
            status="completed",
            messages=out_messages,
            final_answer=result.get("final_answer"),
            errors=result.get("errors", []),
        )
    except Exception as exc:
        logger.error("Run 执行失败", run_id=run_id, error=str(exc))
        return RunResponse(run_id=run_id, thread_id=thread_id, status="error", errors=[str(exc)])
