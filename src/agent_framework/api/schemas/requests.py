from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field


class MessageInput(BaseModel):
    role: Literal["user", "assistant", "system"] = "user"
    content: str


class RunRequest(BaseModel):
    thread_id: str = Field(default="", description="Conversation thread ID. Auto-generated if empty.")
    messages: list[MessageInput]
    stream: bool = False
    agent_type: Literal["react", "plan_execute", "supervisor"] = "react"
    user_id: str = "anonymous"
    tenant_id: str = "default"
    llm_provider: str | None = None
    model_name: str | None = None
    tools_enabled: list[str] = Field(default_factory=list)
    memory_enabled: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class CreateThreadRequest(BaseModel):
    user_id: str = "anonymous"
    metadata: dict[str, Any] = Field(default_factory=dict)
