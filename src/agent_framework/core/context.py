from __future__ import annotations

"""单次调用的运行时上下文（不持久化到 checkpoint）。

AgentContext 通过 RunnableConfig["configurable"]["context"] 传递，
持有可能因请求而异的配置（LLM 选择、工具白名单、用户身份）。
它有意不作为 AgentState 的一部分，从而避免膨胀 checkpoint 存储。
"""

from typing import Literal, TypedDict


class AgentContext(TypedDict, total=False):
    """单次调用的运行时配置 - 不持久化到 checkpoint。"""

    user_id: str
    tenant_id: str

    # LLM 选择
    llm_provider: Literal["openai", "anthropic", "deepseek", "zhipu", "siliconflow"]
    model_name: str
    temperature: float
    max_tokens: int

    # 工具访问控制
    tools_enabled: list[str]  # 白名单；为空表示启用所有工具

    # 功能开关
    memory_enabled: bool
    streaming: bool
    max_iterations: int

    # 可观测性
    trace_id: str
    session_id: str
