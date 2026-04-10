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
        LogisticsAgentType.ORDER: _client(
            settings.DIFY_ORDER_AGENT_URL, settings.DIFY_ORDER_AGENT_KEY, LogisticsAgentType.ORDER
        ),
        LogisticsAgentType.TRACKING: _client(
            settings.DIFY_TRACKING_AGENT_URL, settings.DIFY_TRACKING_AGENT_KEY, LogisticsAgentType.TRACKING
        ),
        LogisticsAgentType.INVENTORY: _client(
            settings.DIFY_INVENTORY_AGENT_URL, settings.DIFY_INVENTORY_AGENT_KEY, LogisticsAgentType.INVENTORY
        ),
        LogisticsAgentType.TRANSPORT: _client(
            settings.DIFY_TRANSPORT_AGENT_URL, settings.DIFY_TRANSPORT_AGENT_KEY, LogisticsAgentType.TRANSPORT
        ),
        LogisticsAgentType.WAREHOUSE: _client(
            settings.DIFY_WAREHOUSE_AGENT_URL, settings.DIFY_WAREHOUSE_AGENT_KEY, LogisticsAgentType.WAREHOUSE
        ),
        LogisticsAgentType.SUPPLIER: _client(
            settings.DIFY_SUPPLIER_AGENT_URL, settings.DIFY_SUPPLIER_AGENT_KEY, LogisticsAgentType.SUPPLIER
        ),
        LogisticsAgentType.CUSTOMS: _client(
            settings.DIFY_CUSTOMS_AGENT_URL, settings.DIFY_CUSTOMS_AGENT_KEY, LogisticsAgentType.CUSTOMS
        ),
        LogisticsAgentType.ANALYTICS: _client(
            settings.DIFY_ANALYTICS_AGENT_URL, settings.DIFY_ANALYTICS_AGENT_KEY, LogisticsAgentType.ANALYTICS
        ),
    }
