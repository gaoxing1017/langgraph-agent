from __future__ import annotations

from fastapi import APIRouter, Request

from agent_framework.api.schemas.responses import GraphInfoResponse

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.get("/graph", response_model=GraphInfoResponse)
async def graph_info(request: Request) -> GraphInfoResponse:
    graph = getattr(request.app.state, "graph", None)
    if graph is None:
        return GraphInfoResponse(nodes=[], edges=[])
    # 从已编译图中提取节点和边信息
    nodes = list(graph.nodes.keys()) if hasattr(graph, "nodes") else []
    return GraphInfoResponse(nodes=nodes, edges=[])
