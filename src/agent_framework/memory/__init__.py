"""智能体对话的四层记忆系统。

  short_term  — 线程范围的 checkpoint（MemorySaver / AsyncPostgresSaver）
  long_term   — 跨会话用户事实，存储于 AsyncPostgresStore
  episodic    — 历史对话的压缩摘要
  semantic    — 对存储的事实/片段进行向量相似度搜索

manager.py 中的 MemoryManager 门面协调所有层。
使用 memory_read_node / memory_write_node（nodes/memory_node.py）
将记忆功能接入 LangGraph 图。
"""

from agent_framework.memory.manager import MemoryManager

__all__ = ["MemoryManager"]
