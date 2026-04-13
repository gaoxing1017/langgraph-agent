from __future__ import annotations

"""物流供应链协调器图（多轮对话版）。

拓扑：
    START
      ↓
    turn_init            ← 轮次 +1，重置 iteration，清空 intent
      ↓
    memory_load          ← 加载用户偏好与历史摘要（Store 可用时）
      ↓
    analyze_and_plan     ← 注入 task_history 的多轮感知规划
      ↓
    dispatch ←──────┐   ← 按 current_turn 过滤，调用 Dify 子 Agent
      ↓             │
    dispatch_router ─┘   ← PENDING 任务存在则循环，否则汇总
      ↓
    result_aggregator    ← 只聚合当前轮次结果
      ↓
    turn_finalize        ← 归档 / 清理 sub_tasks / 裁剪消息 / 每轮生成摘要
      ↓
    END
"""

from langgraph.graph import END, START, StateGraph

from agent_framework.core.state import InputState
from agent_framework.graphs.base_graph import BaseGraphBuilder
from agent_framework.agents.logistics.nodes.analyze_and_plan import analyze_and_plan_node
from agent_framework.agents.logistics.nodes.dispatch import dispatch_node, dispatch_router
from agent_framework.agents.logistics.nodes.memory import memory_load_node
from agent_framework.agents.logistics.nodes.result_aggregator import result_aggregator_node
from agent_framework.agents.logistics.nodes.turn_finalize import turn_finalize_node
from agent_framework.agents.logistics.nodes.turn_init import turn_init_node
from agent_framework.agents.logistics.state import LogisticsOutputState, OrchestratorState


class LogisticsOrchestratorGraphBuilder(BaseGraphBuilder):
    def build(self) -> StateGraph:
        graph = StateGraph(OrchestratorState, input_schema=InputState, output_schema=LogisticsOutputState)

        graph.add_node("turn_init", turn_init_node)
        graph.add_node("memory_load", memory_load_node)
        graph.add_node("analyze_and_plan", analyze_and_plan_node)
        graph.add_node("dispatch", dispatch_node)
        graph.add_node("result_aggregator", result_aggregator_node)
        graph.add_node("turn_finalize", turn_finalize_node)

        graph.add_edge(START, "turn_init")
        graph.add_edge("turn_init", "memory_load")
        graph.add_edge("memory_load", "analyze_and_plan")
        graph.add_edge("analyze_and_plan", "dispatch")

        graph.add_conditional_edges(
            "dispatch",
            dispatch_router,
            {"dispatch": "dispatch", "result_aggregator": "result_aggregator"},
        )

        graph.add_edge("result_aggregator", "turn_finalize")
        graph.add_edge("turn_finalize", END)

        return graph


def build_logistics_orchestrator_graph() -> StateGraph:
    """LangGraph Studio / langgraph dev 无参数工厂函数。"""
    return LogisticsOrchestratorGraphBuilder().build()
