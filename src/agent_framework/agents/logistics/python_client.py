from __future__ import annotations

"""Python 函数子 Agent 客户端。

将任意 Python 异步（或同步）函数包装为 SubAgentClient，
适用于：
  - 直接调用企业内部 Python SDK
  - 单元测试中注入自定义 mock 实现
  - 快速原型：将业务逻辑写成普通函数即可接入编排器

用法示例：
    async def my_order_handler(instruction: str, user: str) -> str:
        # 调用内部 OMS SDK
        order_id = oms.create_order(parse_instruction(instruction))
        return f"订单已创建：{order_id}"

    registry[LogisticsAgentType.PLACE_ORDER] = PythonSubAgent(my_order_handler)
"""

import asyncio
from collections.abc import Awaitable, Callable

import structlog

from agent_framework.agents.logistics.base_client import SubAgentClient

logger = structlog.get_logger(__name__)

# 支持同步或异步函数类型
_HandlerType = Callable[[str, str], str | Awaitable[str]]


class PythonSubAgent(SubAgentClient):
    """将 Python 函数包装为子 Agent 客户端。

    Args:
        handler:  签名为 (instruction: str, user: str) -> str 的函数（同步或 async）
        name:     Agent 名称，用于日志（默认取函数名）
    """

    def __init__(self, handler: _HandlerType, name: str = "") -> None:
        self._handler = handler
        self._name = name or getattr(handler, "__name__", "python_sub_agent")

    async def run(self, instruction: str, user: str = "orchestrator") -> str:
        logger.info("python_sub_agent_call", name=self._name, instruction=instruction[:80])
        try:
            result = self._handler(instruction, user)
            if asyncio.iscoroutine(result):
                result = await result
            logger.info("python_sub_agent_done", name=self._name)
            return str(result)
        except Exception as exc:
            logger.error("python_sub_agent_failed", name=self._name, error=str(exc))
            raise
