from __future__ import annotations

"""子 Agent 注册表。

将 LogisticsAgentType 映射为对应的 SubAgentClient 实例。
支持混合注册多种客户端类型：DifyClient / HttpSubAgent / PythonSubAgent / LLMSubAgent。

典型用法：
    # 全部使用 Dify（默认）
    registry = build_dify_registry(settings)

    # 混合注册：部分使用自定义 HTTP，部分使用 Python 函数
    registry = build_agent_registry(settings, overrides={
        LogisticsAgentType.ORDER_QUERY: HttpSubAgent(url="http://oms.internal/query"),
        LogisticsAgentType.PRODUCT_QUERY: PythonSubAgent(my_product_handler),
    })

在 FastAPI lifespan 中调用一次，结果存入 app.state.logistics_agent._dify_registry。
"""

from agent_framework.agents.logistics.base_client import SubAgentClient
from agent_framework.agents.logistics.dify_client import DifyClient
from agent_framework.agents.logistics.state import LogisticsAgentType
from agent_framework.config.settings import Settings

# 类型别名：注册表 = agent 类型 → 任意 SubAgentClient 实现
AgentRegistry = dict[LogisticsAgentType, SubAgentClient]


def build_dify_registry(settings: Settings) -> AgentRegistry:
    """用 DifyClient 填充 Dify 托管的 agent 类型。

    注意：以下 agent 已迁移为内置 Skill，不再注册到此处：
      - order_query_agent   → skill: query_order_status
      - product_query_agent → skill: query_product_info
      - customer_query_agent → skill: query_customer_info
    如需恢复 Dify 版本，可通过 build_agent_registry 的 overrides 覆盖。
    """
    mock = settings.DIFY_MOCK_MODE

    def _client(url: str, key_secret, agent_type: LogisticsAgentType) -> DifyClient:
        api_key = (
            key_secret.get_secret_value()
            if hasattr(key_secret, "get_secret_value")
            else str(key_secret)
        )
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
    }


def build_agent_registry(
    settings: Settings,
    overrides: AgentRegistry | None = None,
) -> AgentRegistry:
    """构建支持混合客户端的注册表。

    以 build_dify_registry 的结果为基础，用 overrides 中指定的客户端覆盖对应 agent 类型。

    Args:
        settings:  应用配置
        overrides: 需要替换的 {agent_type: client} 映射。
                   值可以是 DifyClient / HttpSubAgent / PythonSubAgent / LLMSubAgent
                   或任何实现了 SubAgentClient 接口的自定义类。

    Returns:
        完整的 AgentRegistry（所有 6 种 agent 类型均已注册）

    Example::

        from agent_framework.agents.logistics.http_client import HttpSubAgent
        from agent_framework.agents.logistics.llm_client import LLMSubAgent

        registry = build_agent_registry(settings, overrides={
            # 订单查询改用内部 OMS HTTP 接口
            LogisticsAgentType.ORDER_QUERY: HttpSubAgent(
                url="http://oms.internal/api/order/query",
                api_key="secret",
                result_path="data.summary",
            ),
            # 商品查询改用 LLM 直接回答（无需外部服务）
            LogisticsAgentType.PRODUCT_QUERY: LLMSubAgent(
                system_prompt="你是商品信息专家，根据 SKU 编码给出详细的商品信息。",
                settings=settings,
            ),
        })
    """
    registry = build_dify_registry(settings)
    if overrides:
        registry.update(overrides)
    return registry
