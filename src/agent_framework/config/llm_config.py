from __future__ import annotations

"""LLM 提供商工厂。

根据当前激活的 provider 配置返回已配置好的 BaseChatModel。
所有提供商均通过统一接口暴露，图节点无需知道底层使用的具体模型。
"""

from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from agent_framework.config.settings import Settings


def get_llm(
    settings: Settings,
    provider: str | None = None,
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> BaseChatModel:
    """LLM 工厂函数：根据 provider 配置返回对应的 ChatModel。"""
    _provider = provider or settings.LLM_PROVIDER
    _model = model or settings.DEFAULT_MODEL
    _temperature = temperature if temperature is not None else settings.DEFAULT_TEMPERATURE
    _max_tokens = max_tokens or settings.DEFAULT_MAX_TOKENS

    if _provider == "openai":
        return ChatOpenAI(
            model=_model,
            temperature=_temperature,
            max_tokens=_max_tokens,
            api_key=settings.OPENAI_API_KEY.get_secret_value() if settings.OPENAI_API_KEY else None,
        )
    elif _provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=_model or "claude-3-5-sonnet-20241022",
            temperature=_temperature,
            max_tokens=_max_tokens,
            api_key=settings.ANTHROPIC_API_KEY.get_secret_value() if settings.ANTHROPIC_API_KEY else None,
        )
    elif _provider in ("deepseek", "zhipu"):
        base_urls = {
            "deepseek": "https://api.deepseek.com/v1",
            "zhipu": "https://open.bigmodel.cn/api/paas/v4",
        }
        api_keys = {
            "deepseek": settings.DEEPSEEK_API_KEY.get_secret_value() if settings.DEEPSEEK_API_KEY else None,
            "zhipu": None,  # 智谱使用自有鉴权，通过环境变量 ZHIPU_AI_API_KEY 传入
        }
        return ChatOpenAI(
            model=_model,
            temperature=_temperature,
            max_tokens=_max_tokens,
            base_url=base_urls[_provider],
            api_key=api_keys[_provider],
        )
    elif _provider == "siliconflow":
        return ChatOpenAI(
            model=_model,
            temperature=_temperature,
            max_tokens=_max_tokens,
            base_url=settings.SILICONFLOW_BASE_URL,
            api_key=settings.SILICONFLOW_API_KEY.get_secret_value() if settings.SILICONFLOW_API_KEY else None,
        )
    else:
        raise ValueError(f"不支持的 LLM provider: {_provider}")
