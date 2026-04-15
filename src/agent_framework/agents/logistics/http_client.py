from __future__ import annotations

"""通用 HTTP POST 子 Agent 客户端。

适用于任何通过 HTTP POST 接口暴露的 Agent 服务，例如：
  - 自定义 FastAPI 服务
  - Coze / 百炼 / 其他 LLM 平台
  - 企业内部 RPC 服务（包装为 HTTP）

请求格式（默认）：
    POST <url>
    Authorization: Bearer <api_key>
    Content-Type: application/json
    {"instruction": "...", "user": "..."}

响应格式（可通过 result_path 配置）：
    {"result": "..."}          ← 默认
    {"data": {"text": "..."}}  ← result_path="data.text"
"""

import structlog

from agent_framework.agents.logistics.base_client import SubAgentClient

logger = structlog.get_logger(__name__)


class HttpSubAgent(SubAgentClient):
    """通用 HTTP POST 子 Agent。

    Args:
        url:         目标接口完整 URL
        api_key:     Bearer Token（可为空）
        input_field: 请求 body 中传入指令的字段名，默认 "instruction"
        result_path: 从响应 JSON 中提取结果的点分路径，默认 "result"
        timeout:     请求超时秒数
        extra_body:  附加到每次请求 body 的固定字段
    """

    def __init__(
        self,
        url: str,
        api_key: str = "",
        input_field: str = "instruction",
        result_path: str = "result",
        timeout: int = 60,
        extra_body: dict | None = None,
    ) -> None:
        self.url = url
        self.api_key = api_key
        self.input_field = input_field
        self.result_path = result_path
        self.timeout = timeout
        self.extra_body = extra_body or {}

    async def run(self, instruction: str, user: str = "orchestrator") -> str:
        import httpx

        body = {self.input_field: instruction, "user": user, **self.extra_body}
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        logger.info("http_sub_agent_call", url=self.url, instruction=instruction[:80])
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(self.url, headers=headers, json=body)
                resp.raise_for_status()
                data = resp.json()

            # 按点分路径提取结果
            result: object = data
            for key in self.result_path.split("."):
                if isinstance(result, dict):
                    result = result.get(key, "")
                else:
                    result = ""
                    break

            logger.info("http_sub_agent_done", url=self.url)
            return str(result)

        except Exception as exc:
            logger.error("http_sub_agent_failed", url=self.url, error=str(exc))
            raise
