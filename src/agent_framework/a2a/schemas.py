from __future__ import annotations

from enum import Enum
from typing import Any, Literal
from pydantic import BaseModel, Field
import uuid


class TaskState(str, Enum):
    SUBMITTED = "submitted"
    WORKING = "working"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


class A2AMessage(BaseModel):
    role: Literal["user", "agent"]
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class Artifact(BaseModel):
    artifact_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: Literal["text", "file", "data"] = "text"
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class Task(BaseModel):
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = ""
    state: TaskState = TaskState.SUBMITTED
    messages: list[A2AMessage] = Field(default_factory=list)
    artifacts: list[Artifact] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentSkill(BaseModel):
    id: str
    name: str
    description: str
    input_modes: list[str] = ["text"]
    output_modes: list[str] = ["text"]


class AgentCard(BaseModel):
    name: str
    version: str
    description: str
    url: str
    skills: list[AgentSkill] = Field(default_factory=list)
    default_input_mode: str = "text"
    default_output_mode: str = "text"
