"""所有图构建器的抽象基类。

build/compile 分离允许测试使用不带 checkpointer（或使用 MemorySaver）
的 build()，而生产代码调用 compile(checkpointer=PostgresSaver)。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from langgraph.graph import StateGraph

from agent_framework.core.state import AgentState, InputState, OutputState


class BaseGraphBuilder(ABC):
    """所有图构建器的抽象基类。"""

    @abstractmethod
    def build(self) -> StateGraph:
        """构建并返回未编译的 StateGraph。

        在此处添加节点和边。不要在 build() 内调用 .compile()；
        编译被推迟，以便调用方能注入不同的 checkpointer
        （测试使用 MemorySaver，生产使用 AsyncPostgresSaver）。
        """
        ...

    def compile(self, **kwargs: Any):
        """一步完成图的构建与编译。

        Args:
            **kwargs: 转发给 StateGraph.compile() 的参数——通常为
                      checkpointer= 和/或 store=。
        Returns:
            可用于 ainvoke() / astream_events() 的已编译图。
        """
        return self.build().compile(**kwargs)
