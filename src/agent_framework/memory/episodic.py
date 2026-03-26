"""情节记忆：压缩的对话摘要。

在长对话结束时，summarize_and_store_episode() 将最近 N 条消息
压缩为一段短文并持久化到 (user_id, "episodes") 命名空间下。
后续会话通过语义搜索检索这些情节，以恢复相关上下文。
"""

from __future__ import annotations

from typing import Any

import structlog
from langchain_core.messages import AnyMessage

logger = structlog.get_logger(__name__)

# 触发情节摘要所需的最少消息数
_MIN_MESSAGES_FOR_EPISODE = 4
# 输入摘要提示的最近消息数量窗口
_SUMMARISATION_WINDOW = 20


async def summarize_and_store_episode(
    messages: list[AnyMessage],
    store: Any,
    user_id: str,
    session_id: str,
    llm: Any,
) -> None:
    """对对话进行摘要并将其作为情节存储到长期记忆中。"""
    if len(messages) < _MIN_MESSAGES_FOR_EPISODE:
        return

    conversation_text = "\n".join(
        f"{type(m).__name__}: {m.content}" for m in messages[-_SUMMARISATION_WINDOW:]
    )
    prompt = f"Summarize the key points of this conversation:\n\n{conversation_text}"

    try:
        from langchain_core.messages import HumanMessage
        summary_msg = await llm.ainvoke([HumanMessage(content=prompt)])
        summary = summary_msg.content

        await store.aput(
            namespace=(user_id, "episodes"),
            key=session_id,
            value={
                "summary": summary,
                "session_id": session_id,
                "message_count": len(messages),
            },
        )
        logger.info("情节已存储", user_id=user_id, session_id=session_id)
    except Exception as exc:
        logger.error("情节摘要失败", error=str(exc))
