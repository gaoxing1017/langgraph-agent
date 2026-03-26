from __future__ import annotations

from fastapi import APIRouter, Request

from agent_framework.api.schemas.responses import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    settings = request.app.state.settings
    return HealthResponse(
        status="ok",
        version="1.0.0",
        environment=settings.ENVIRONMENT,
    )


@router.get("/readiness", response_model=HealthResponse)
async def readiness(request: Request) -> HealthResponse:
    """检查数据库连通性和图的可用性。"""
    try:
        graph = getattr(request.app.state, "graph", None)
        if graph is None:
            return HealthResponse(status="degraded")
        return HealthResponse(status="ok", environment=request.app.state.settings.ENVIRONMENT)
    except Exception:
        return HealthResponse(status="error")
