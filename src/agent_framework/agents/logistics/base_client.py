from __future__ import annotations

"""子 Agent 客户端抽象基类。

所有能被 dispatch_node 调用的 Agent 客户端必须实现此接口：
    async def run(instruction: str, user: str) -> str

内置实现：
  - DifyClient      : 调用 Dify Workflow API
  - HttpSubAgent    : 调用任意 HTTP POST 接口
  - PythonSubAgent  : 直接调用 Python 异步函数
  - LLMSubAgent     : 使用 LLM 直接处理（无需外部服务）
"""

from abc import ABC, abstractmethod


class SubAgentClient(ABC):
    """子 Agent 客户端统一接口。"""

    @abstractmethod
    async def run(self, instruction: str, user: str = "orchestrator") -> str:
        """执行子 Agent 并返回文本结果。

        Args:
            instruction: 自然语言指令（由 analyze_and_plan 生成）
            user:        调用方用户标识（用于审计）

        Returns:
            子 Agent 的文本输出结果
        """
