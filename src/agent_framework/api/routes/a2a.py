from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(tags=["a2a"])


@router.get("/.well-known/agent.json")
async def agent_card(request: Request) -> JSONResponse:
    """返回描述此智能体能力的 A2A AgentCard。"""
    from agent_framework.a2a.agent_card import build_agent_card
    settings = request.app.state.settings
    card = build_agent_card(settings)
    return JSONResponse(content=card)


@router.post("/a2a")
async def a2a_endpoint(body: dict, request: Request) -> JSONResponse:
    """A2A JSON-RPC 端点：处理 tasks/send、tasks/get、tasks/cancel。"""
    from agent_framework.a2a.server import handle_jsonrpc
    result = await handle_jsonrpc(body, request.app.state)
    return JSONResponse(content=result)
