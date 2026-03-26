"""图构建器库。

每个构建器继承 BaseGraphBuilder 并实现 build() 方法来组装节点和边。
在应用启动时通过 compile(checkpointer=, store=) 编译一次，
并将结果存储在 FastAPI app.state 中——绝不在请求处理器内编译。

可用图：
  build_react_graph()        — ReAct 工具调用循环
  build_plan_execute_graph() — 先生成结构化计划再逐步执行
  build_supervisor_graph()   — 多智能体 supervisor/specialist 协调
"""

from agent_framework.graphs.plan_execute_graph import build_plan_execute_graph
from agent_framework.graphs.react_graph import build_react_graph
from agent_framework.graphs.supervisor_graph import build_supervisor_graph

__all__ = ["build_react_graph", "build_plan_execute_graph", "build_supervisor_graph"]
