from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from agent_framework.api.schemas.requests import CreateThreadRequest
from agent_framework.api.schemas.responses import ThreadResponse

router = APIRouter(prefix="/api/v1/threads", tags=["threads"])


@router.post("", response_model=ThreadResponse, status_code=201)
async def create_thread(body: CreateThreadRequest, request: Request) -> ThreadResponse:
    thread_id = str(uuid.uuid4())
    return ThreadResponse(
        thread_id=thread_id,
        user_id=body.user_id,
        created_at=datetime.utcnow(),
    )


@router.get("/{thread_id}", response_model=ThreadResponse)
async def get_thread(thread_id: str, request: Request) -> ThreadResponse:
    checkpointer = getattr(request.app.state, "checkpointer", None)
    if checkpointer is None:
        raise HTTPException(status_code=503, detail="Checkpointer 不可用")
    return ThreadResponse(
        thread_id=thread_id,
        user_id="unknown",
        created_at=datetime.utcnow(),
    )


@router.delete("/{thread_id}", status_code=204)
async def delete_thread(thread_id: str, request: Request) -> None:
    # checkpoint 的删除取决于 checkpointer 的具体实现
    pass
