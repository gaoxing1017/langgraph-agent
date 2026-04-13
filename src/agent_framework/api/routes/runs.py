from __future__ import annotations

import uuid
from typing import Any, AsyncIterator

import structlog
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage

from agent_framework.api.schemas.requests import RunRequest
from agent_framework.api.schemas.responses import MessageOutput, RunResponse, SubTaskOutput
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


def _extract_sub_tasks(result: dict[str, Any]) -> list[SubTaskOutput]:
    """从 logistics agent 结果中提取子任务列表。"""
    raw = result.get("sub_tasks", [])
    out = []
    for t in raw:
        data = t if isinstance(t, dict) else t.model_dump()
        out.append(SubTaskOutput(
            task_id=data.get("task_id", ""),
            agent_type=data.get("agent_type", ""),
            instruction=data.get("instruction", ""),
            status=data.get("status", ""),
            result=data.get("result"),
            error=data.get("error"),
        ))
    return out


# ── Logistics agent handler ────────────────────────────────────────────────────

async def _run_logistics(body: RunRequest, request: Request, run_id: str, thread_id: str):
    """同步执行 logistics orchestrator 并返回 RunResponse。"""
    agent = getattr(request.app.state, "logistics_agent", None)
    if agent is None:
        raise HTTPException(status_code=503, detail="Logistics agent 未初始化")

    user_message = next(
        (m.content for m in body.messages if m.role == "user"), ""
    )
    try:
        result = await agent.run(
            user_message=user_message,
            thread_id=thread_id,
            user_id=body.user_id,
            tenant_id=body.tenant_id,
            memory_enabled=body.memory_enabled,
        )
        return RunResponse(
            run_id=run_id,
            thread_id=thread_id,
            status="completed",
            final_answer=result.get("final_answer"),
            sub_tasks=_extract_sub_tasks(result),
            turn_count=result.get("turn_count", 0),
            intent=result.get("intent"),
            errors=result.get("errors", []),
        )
    except Exception as exc:
        logger.error("Logistics run 执行失败", run_id=run_id, error=str(exc))
        return RunResponse(run_id=run_id, thread_id=thread_id, status="error", errors=[str(exc)])


async def _stream_logistics(body: RunRequest, request: Request, thread_id: str) -> AsyncIterator[str]:
    """流式执行 logistics orchestrator，仅推送 LLM token。"""
    agent = getattr(request.app.state, "logistics_agent", None)
    if agent is None:
        yield "data: [ERROR] Logistics agent 未初始化\n\n"
        return

    user_message = next(
        (m.content for m in body.messages if m.role == "user"), ""
    )
    async for event in agent.stream(
        user_message=user_message,
        thread_id=thread_id,
        user_id=body.user_id,
        tenant_id=body.tenant_id,
    ):
        if event["event"] == "on_chat_model_stream":
            # 只推送 result_aggregator 节点的 token，过滤 analyze_and_plan 的 JSON 输出
            node = event.get("metadata", {}).get("langgraph_node", "")
            if node != "result_aggregator":
                continue
            chunk = event["data"].get("chunk", "")
            content = getattr(chunk, "content", "")
            if content:
                yield f"data: {content}\n\n"
    yield "data: [DONE]\n\n"


# ── ReAct (generic) handler ────────────────────────────────────────────────────

@router.post("", response_model=RunResponse)
async def create_run(body: RunRequest, request: Request):
    """执行智能体图，支持 react 与 logistics 两种 agent_type。

    响应模式：
    - 同步（stream=false）：返回完整 RunResponse JSON。
    - 流式（stream=true）：返回 text/event-stream 增量 token。
    """
    thread_id = body.thread_id or str(uuid.uuid4())
    run_id = str(uuid.uuid4())

    # ── logistics agent ──
    if body.agent_type == "logistics":
        if body.stream:
            return StreamingResponse(
                _stream_logistics(body, request, thread_id),
                media_type="text/event-stream",
            )
        return await _run_logistics(body, request, run_id, thread_id)

    # ── react / generic agent ──
    graph = getattr(request.app.state, "graph", None)
    if graph is None:
        raise HTTPException(status_code=503, detail="图未初始化")

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
