from __future__ import annotations

import structlog

from agent_framework.a2a.schemas import Task, TaskState

logger = structlog.get_logger(__name__)


class A2AClient:
    """向远程 A2A 兼容智能体发送任务的客户端。"""

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")

    async def send_task(self, message: str, session_id: str = "") -> Task:
        """向远程智能体发送任务并等待完成。"""
        import httpx
        payload = {
            "jsonrpc": "2.0",
            "method": "tasks/send",
            "params": {
                "message": {"role": "user", "content": message},
                "sessionId": session_id,
            },
            "id": 1,
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(f"{self._base_url}/a2a", json=payload)
            response.raise_for_status()
            data = response.json()
            result = data.get("result", {})
            task = Task.model_validate(result)
            logger.info("A2A 任务已发送", task_id=task.task_id, url=self._base_url)
            return task

    async def get_task(self, task_id: str) -> Task:
        import httpx
        payload = {
            "jsonrpc": "2.0",
            "method": "tasks/get",
            "params": {"taskId": task_id},
            "id": 1,
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(f"{self._base_url}/a2a", json=payload)
            response.raise_for_status()
            data = response.json()
            return Task.model_validate(data.get("result", {}))
