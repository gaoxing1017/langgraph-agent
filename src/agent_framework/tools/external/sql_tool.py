from __future__ import annotations

from typing import Any

import structlog
from langchain_core.tools import tool

logger = structlog.get_logger(__name__)


def build_sql_tool(engine: Any) -> Any:
    """构建以 SQLAlchemy 异步引擎为后端的只读 SQL 查询工具。"""

    @tool
    async def sql_query(query: str) -> str:
        """执行只读 SQL SELECT 查询并返回结果。

        Args:
            query: 要执行的 SQL SELECT 语句。
        """
        if not query.strip().upper().startswith("SELECT"):
            return "Error: Only SELECT queries are allowed."
        try:
            from sqlalchemy import text
            async with engine.connect() as conn:
                result = await conn.execute(text(query))
                rows = result.fetchall()
                if not rows:
                    return "Query returned no results."
                cols = list(result.keys())
                lines = [" | ".join(cols)]
                lines += [" | ".join(str(v) for v in row) for row in rows[:50]]
                return "\n".join(lines)
        except Exception as exc:
            logger.error("SQL 查询失败", error=str(exc))
            return f"SQL error: {exc}"

    return sql_query
