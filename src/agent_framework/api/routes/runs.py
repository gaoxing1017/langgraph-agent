from __future__ import annotations

import json
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


def _enum_val(v: Any) -> str:
    """提取枚举的 .value，避免 Python 3.11+ str(Enum) 返回 'ClassName.MEMBER'。"""
    return v.value if hasattr(v, "value") else str(v)


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
            agent_type=_enum_val(data.get("agent_type", "")),
            instruction=data.get("instruction", ""),
            status=_enum_val(data.get("status", "")),
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
            resume=body.resume,
        )

        # 图被 interrupt() 挂起（HITL validate_tasks）
        if "__interrupt__" in result:
            iv = result["__interrupt__"]
            return RunResponse(
                run_id=run_id,
                thread_id=thread_id,
                status="interrupted",
                final_answer=iv.get("question", "需要补充信息"),
                errors=[],
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


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _task_dict(t: Any) -> dict:
    d = t if isinstance(t, dict) else t.model_dump()
    return {
        "task_id":     str(d.get("task_id", "")),
        "agent_type":  _enum_val(d.get("agent_type", "")),
        "instruction": d.get("instruction", ""),
        "status":      _enum_val(d.get("status", "")),
        "result":      d.get("result"),
        "error":       d.get("error"),
    }


async def _stream_logistics(body: RunRequest, request: Request, thread_id: str) -> AsyncIterator[str]:
    """流式执行 logistics orchestrator，推送结构化过程事件 + 最终 token。

    SSE 事件类型：
      {"type":"plan",        "intent":"...", "tasks":[...]}   ← 规划完成
      {"type":"task_update", "tasks":[...]}                   ← 单个任务状态变更
      {"type":"token",       "content":"..."}                 ← 最终回答 token
      {"type":"done"}                                         ← 流结束
      {"type":"interrupt",   "question":"...", "gaps":[...]}  ← HITL 缺少信息
      {"type":"error",       "message":"..."}                 ← 错误
    """
    agent = getattr(request.app.state, "logistics_agent", None)
    if agent is None:
        yield _sse({"type": "error", "message": "Logistics agent 未初始化"})
        return

    user_message = next((m.content for m in body.messages if m.role == "user"), "")

    try:
        async for event in agent.stream(
            user_message=user_message,
            thread_id=thread_id,
            user_id=body.user_id,
            tenant_id=body.tenant_id,
            resume=body.resume,
        ):
            etype = event["event"]

            # ── 人工补全中断事件（validate_tasks interrupt）────────────────
            if etype == "__interrupt__":
                iv = event["data"]["value"]
                yield _sse({
                    "type": "interrupt",
                    "question": iv.get("question", ""),
                    "gaps": iv.get("gaps", []),
                })
                return  # 不发送 done，等待用户 resume

            node  = event.get("metadata", {}).get("langgraph_node", "")
            event_name = event.get("name", "")
            logger.debug("stream_event", etype=etype, node=node, name=event_name)

            # ── 规划完成：推送意图 + 全部子任务（pending 状态）──────────────
            # 只处理节点本身的 on_chain_end（name == 注册名），忽略内部子链事件
            if etype == "on_chain_end" and node == "analyze_and_plan" and event_name == "analyze_and_plan":
                out = event["data"].get("output", {})
                if isinstance(out, dict):
                    tasks = [_task_dict(t) for t in out.get("sub_tasks", [])]
                    if tasks:
                        yield _sse({"type": "plan", "intent": out.get("intent", ""), "tasks": tasks})

            # ── 单次 dispatch 完成：推送该任务最新状态 ─────────────────────
            elif etype == "on_chain_end" and node == "dispatch" and event_name == "dispatch":
                out = event["data"].get("output", {})
                if isinstance(out, dict):
                    tasks = [_task_dict(t) for t in out.get("sub_tasks", [])]
                    if tasks:
                        yield _sse({"type": "task_update", "tasks": tasks})

            # ── result_aggregator LLM token ────────────────────────────────
            elif etype == "on_chat_model_stream" and node == "result_aggregator":
                chunk   = event["data"].get("chunk", "")
                content = getattr(chunk, "content", "")
                if content:
                    yield _sse({"type": "token", "content": content})

        yield _sse({"type": "done"})

    except Exception as exc:
        logger.error("stream_logistics_error", error=str(exc), exc_info=True)
        yield _sse({"type": "error", "message": f"执行失败: {exc}"})


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
