from __future__ import annotations

"""输入/输出守卫节点。

input_guard_node  — 在图处理之前运行；拦截符合违规策略模式的请求，
                    并短路图的后续执行。
output_guard_node — 在输出产生之后运行；占位符，用于 PII 检测、
                    毒性评分或长度校验。

重要提示：BLOCKED_PATTERNS 仅为演示用途的简单关键词列表。
在生产部署前请替换为专用的内容审核 API。
"""

from langchain_core.runnables import RunnableConfig

from typing import Any

import structlog
from langchain_core.messages import HumanMessage

from agent_framework.core.state import AgentState

logger = structlog.get_logger(__name__)

# 简单的基于关键词的守卫（生产环境中请替换为适当的策略模型）
BLOCKED_PATTERNS = [
    "ignore previous instructions",
    "jailbreak",
    "disregard your instructions",
]


async def input_guard_node(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    """在处理前根据策略规则验证用户输入。"""
    messages = state.get("messages", [])
    if not messages:
        return {}

    last_message = messages[-1]
    if not isinstance(last_message, HumanMessage):
        return {}

    content = last_message.content.lower() if isinstance(last_message.content, str) else ""

    for pattern in BLOCKED_PATTERNS:
        if pattern in content:
            logger.warning("输入被守卫拦截", pattern=pattern)
            return {
                "errors": [f"Input blocked by policy: contains disallowed pattern"],
                "final_answer": "I cannot process this request as it violates usage policies.",
            }

    return {}


async def output_guard_node(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    """在返回给调用方前验证最终输出。

    当前为透传占位符。生产实现应在此处
    添加 PII 检测、毒性评分和格式校验逻辑。
    """
    final_answer = state.get("final_answer", "")
    if not final_answer:
        return {}

    # 在此处添加输出验证逻辑（如 PII 检测、毒性检查）
    logger.debug("输出守卫通过")
    return {}
