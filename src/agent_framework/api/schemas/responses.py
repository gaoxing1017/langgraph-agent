from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel


class MessageOutput(BaseModel):
    role: str
    content: str


class SubTaskOutput(BaseModel):
    task_id: str
    agent_type: str
    instruction: str
    status: str
    result: str | None = None
    error: str | None = None


class RunResponse(BaseModel):
    run_id: str
    thread_id: str
    status: Literal["completed", "interrupted", "error"]
    messages: list[MessageOutput] = []
    final_answer: str | None = None
    errors: list[str] = []
    sub_tasks: list[SubTaskOutput] = []
    turn_count: int = 0
    intent: str | None = None
    metadata: dict[str, Any] = {}


class ThreadResponse(BaseModel):
    thread_id: str
    user_id: str
    created_at: datetime
    message_count: int = 0


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded", "error"] = "ok"
    version: str = "1.0.0"
    environment: str = "development"


class GraphInfoResponse(BaseModel):
    nodes: list[str]
    edges: list[dict[str, str]]
