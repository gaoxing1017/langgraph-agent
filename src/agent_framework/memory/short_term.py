"""通过 LangGraph checkpointer 实现的短期（线程范围）记忆。

checkpointer 在每次节点执行后序列化完整的 AgentState。
当后续调用使用相同的 thread_id 时，LangGraph 会自动从最新的
checkpoint 中恢复状态——无需任何显式的会话管理，即可实现
无缝的对话连续性。

开发环境使用 get_memory_saver()，生产环境使用 AsyncPostgresSaver
（参见 persistence/checkpoint_factory.py）。
"""

from __future__ import annotations

from typing import Any

from langgraph.checkpoint.memory import MemorySaver


def get_memory_saver() -> MemorySaver:
    """返回用于开发/测试的内存 checkpointer。"""
    return MemorySaver()
