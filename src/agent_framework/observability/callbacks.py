"""节点级遥测的 LangChain 回调处理器。

AgentCallbackHandler 挂入 LangChain 的回调系统，用于：
  - 在每次 LLM 调用时递增 Prometheus token 计数器
  - 记录工具调用的成功/错误率
  - 为每次节点转换记录结构化事件

在 RunnableConfig["callbacks"] 中传入实例以激活：
    config = {"callbacks": [AgentCallbackHandler()], "configurable": {...}}
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import structlog
from langchain_core.callbacks import BaseCallbackHandler

from agent_framework.observability.metrics import (
    llm_requests_total,
    llm_tokens_total,
    tool_calls_total,
    tool_latency_seconds,
)

logger = structlog.get_logger(__name__)


class AgentCallbackHandler(BaseCallbackHandler):
    """节点级遥测的 LangChain 回调处理器。"""

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        """成功时记录 LLM token 使用量并递增请求计数器。"""
        usage = getattr(response, "llm_output", {}).get("token_usage", {})
        provider = kwargs.get("tags", ["unknown"])[0] if kwargs.get("tags") else "unknown"
        model = kwargs.get("invocation_params", {}).get("model_name", "unknown")

        if usage.get("prompt_tokens"):
            llm_tokens_total.labels(provider=provider, model=model, token_type="prompt").inc(
                usage["prompt_tokens"]
            )
        if usage.get("completion_tokens"):
            llm_tokens_total.labels(provider=provider, model=model, token_type="completion").inc(
                usage["completion_tokens"]
            )
        llm_requests_total.labels(provider=provider, model=model, status="success").inc()

    def on_llm_error(self, error: BaseException, **kwargs: Any) -> None:
        """递增错误计数器并记录 LLM 失败日志。"""
        provider = kwargs.get("tags", ["unknown"])[0] if kwargs.get("tags") else "unknown"
        model = kwargs.get("invocation_params", {}).get("model_name", "unknown")
        llm_requests_total.labels(provider=provider, model=model, status="error").inc()
        logger.error("LLM 错误", error=str(error))

    def on_tool_end(self, output: Any, **kwargs: Any) -> None:
        tool_name = kwargs.get("name", "unknown")
        tool_calls_total.labels(tool_name=tool_name, status="success").inc()

    def on_tool_error(self, error: BaseException, **kwargs: Any) -> None:
        tool_name = kwargs.get("name", "unknown")
        tool_calls_total.labels(tool_name=tool_name, status="error").inc()
        logger.error("工具错误", tool_name=tool_name, error=str(error))
