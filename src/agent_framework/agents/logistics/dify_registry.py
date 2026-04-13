from __future__ import annotations

"""Dify 客户端注册表。

根据 Settings 为每种 LogisticsAgentType 构建对应的 DifyClient 实例。
在 FastAPI lifespan 中调用 build_dify_registry() 一次，结果存入 app.state。
"""

from agent_framework.config.settings import Settings
from agent_framework.agents.logistics.dify_client import DifyClient
from agent_framework.agents.logistics.state import LogisticsAgentType


def build_dify_registry(settings: Settings) -> dict[LogisticsAgentType, DifyClient]:
    """根据 Settings 构建 {agent_type: DifyClient} 映射表。"""
    mock = settings.DIFY_MOCK_MODE

    def _client(url: str, key_secret, agent_type: LogisticsAgentType) -> DifyClient:
        api_key = key_secret.get_secret_value() if hasattr(key_secret, "get_secret_value") else str(key_secret)
        return DifyClient(
            base_url=url,
            api_key=api_key,
            agent_type=agent_type,
            mock_mode=mock,
            timeout=settings.ORCHESTRATOR_TASK_TIMEOUT,
        )

    return {
        LogisticsAgentType.PLACE_ORDER: _client(
            settings.DIFY_PLACE_ORDER_AGENT_URL,
            settings.DIFY_PLACE_ORDER_AGENT_KEY,
            LogisticsAgentType.PLACE_ORDER,
        ),
        LogisticsAgentType.REVIEW_ORDER: _client(
            settings.DIFY_REVIEW_ORDER_AGENT_URL,
            settings.DIFY_REVIEW_ORDER_AGENT_KEY,
            LogisticsAgentType.REVIEW_ORDER,
        ),
        LogisticsAgentType.EXCEPTION_ORDER: _client(
            settings.DIFY_EXCEPTION_ORDER_AGENT_URL,
            settings.DIFY_EXCEPTION_ORDER_AGENT_KEY,
            LogisticsAgentType.EXCEPTION_ORDER,
        ),
        LogisticsAgentType.ORDER_QUERY: _client(
            settings.DIFY_ORDER_QUERY_AGENT_URL,
            settings.DIFY_ORDER_QUERY_AGENT_KEY,
            LogisticsAgentType.ORDER_QUERY,
        ),
        LogisticsAgentType.CUSTOMER_QUERY: _client(
            settings.DIFY_CUSTOMER_QUERY_AGENT_URL,
            settings.DIFY_CUSTOMER_QUERY_AGENT_KEY,
            LogisticsAgentType.CUSTOMER_QUERY,
        ),
        LogisticsAgentType.PRODUCT_QUERY: _client(
            settings.DIFY_PRODUCT_QUERY_AGENT_URL,
            settings.DIFY_PRODUCT_QUERY_AGENT_KEY,
            LogisticsAgentType.PRODUCT_QUERY,
        ),
    }
