"""持久化层：checkpointer、长期存储和 ORM 模型。

工厂函数根据 Settings.CHECKPOINTER_TYPE 选择适当的后端：
  "memory"   → MemorySaver（开发环境，无外部依赖）
  "postgres" → AsyncPostgresSaver（生产环境，需要 langgraph-checkpoint-postgres）

AsyncPostgresStore 提供带有可选 pgvector 索引的长期记忆后端，
支持语义搜索。
"""

from agent_framework.persistence.checkpoint_factory import get_checkpointer
from agent_framework.persistence.postgres_store import get_postgres_store

__all__ = ["get_checkpointer", "get_postgres_store"]
