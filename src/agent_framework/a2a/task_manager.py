"""内存中的 A2A 任务状态管理器。

跟踪委派给此智能体的任务生命周期：
    submitted → working → completed | failed | canceled

重要提示：这是适用于单实例部署的内存实现。
对于多实例生产部署，请替换为数据库支持的实现
（例如以 RunLog ORM 模型为后端）。
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog

from agent_framework.a2a.schemas import Artifact, Task, TaskState

logger = structlog.get_logger(__name__)


class TaskManager:
    """内存中的任务状态管理器。生产环境请替换为数据库支持的实现。"""

    def __init__(self) -> None:
        self._tasks: dict[str, Task] = {}

    def create_task(self, session_id: str = "", metadata: dict | None = None) -> Task:
        task = Task(
            task_id=str(uuid.uuid4()),
            session_id=session_id,
            state=TaskState.SUBMITTED,
            metadata=metadata or {},
        )
        self._tasks[task.task_id] = task
        logger.debug("任务已创建", task_id=task.task_id)
        return task

    def get_task(self, task_id: str) -> Task | None:
        return self._tasks.get(task_id)

    def update_state(self, task_id: str, state: TaskState) -> None:
        if task := self._tasks.get(task_id):
            task.state = state
            logger.debug("任务状态已更新", task_id=task_id, state=state)

    def add_artifact(self, task_id: str, artifact: Artifact) -> None:
        if task := self._tasks.get(task_id):
            task.artifacts.append(artifact)

    def cancel_task(self, task_id: str) -> bool:
        if task := self._tasks.get(task_id):
            if task.state in (TaskState.SUBMITTED, TaskState.WORKING):
                task.state = TaskState.CANCELED
                return True
        return False
