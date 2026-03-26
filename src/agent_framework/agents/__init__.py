"""智能体类——对已编译 LangGraph 图的高层封装。

使用模式：
    agent = ReActAgent(settings, tool_registry=registry)
    agent.build_graph(checkpointer=checkpointer, store=store)  # 启动时调用一次
    result = await agent.ainvoke(input_state, context, thread_id="abc")

所有智能体均继承 BaseAgent，BaseAgent 持有已编译图并提供
ainvoke() / astream() 执行方法。
"""

from agent_framework.agents.base_agent import BaseAgent
from agent_framework.agents.coordinator_agent import CoordinatorAgent
from agent_framework.agents.plan_execute_agent import PlanExecuteAgent
from agent_framework.agents.react_agent import ReActAgent

__all__ = ["BaseAgent", "ReActAgent", "PlanExecuteAgent", "CoordinatorAgent"]
