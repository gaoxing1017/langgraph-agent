from __future__ import annotations

"""物流协调器集成测试。

使用 MemorySaver checkpointer + DIFY_MOCK_MODE=True，
无需真实 LLM 或 Dify 服务即可验证图拓扑和节点串联。
"""

import pytest
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver

from agent_framework.config.settings import Settings
from agent_framework.agents.logistics.dify_client import DifyClient
from agent_framework.agents.logistics.dify_registry import build_dify_registry
from agent_framework.agents.logistics.graph import LogisticsOrchestratorGraphBuilder
from agent_framework.agents.logistics.nodes.dispatch import dispatch_router
from agent_framework.agents.logistics.state import (
    LogisticsAgentType,
    OrchestratorState,
    SubTask,
    TaskStatus,
    _merge_sub_tasks,
)


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_settings() -> Settings:
    return Settings(
        ENVIRONMENT="development",
        LLM_PROVIDER="openai",
        CHECKPOINTER_TYPE="memory",
        NACOS_ENABLED=False,
        LANGFUSE_ENABLED=False,
        DIFY_MOCK_MODE=True,
    )


@pytest.fixture
def dify_registry(mock_settings):
    return build_dify_registry(mock_settings)


@pytest.fixture
def compiled_graph(mock_settings):
    checkpointer = MemorySaver()
    return LogisticsOrchestratorGraphBuilder().compile(checkpointer=checkpointer)


# ── SubTask reducer ───────────────────────────────────────────────────────────

class TestMergeSubTasks:
    def test_appends_new_tasks(self):
        t1 = SubTask(task_id="a", agent_type=LogisticsAgentType.ORDER, instruction="查订单")
        t2 = SubTask(task_id="b", agent_type=LogisticsAgentType.TRACKING, instruction="查追踪")
        result = _merge_sub_tasks([], [t1, t2])
        assert len(result) == 2

    def test_updates_existing_by_id(self):
        t1 = SubTask(task_id="a", agent_type=LogisticsAgentType.ORDER, instruction="查订单")
        t1_done = t1.model_copy(update={"status": TaskStatus.COMPLETED, "result": "ok"})
        result = _merge_sub_tasks([t1], [t1_done])
        assert len(result) == 1
        assert result[0].status == TaskStatus.COMPLETED

    def test_handles_dict_input(self):
        """checkpoint 反序列化后 sub_tasks 为 dict 列表，reducer 需兼容。"""
        raw = {"task_id": "x", "agent_type": "order_agent", "instruction": "test"}
        result = _merge_sub_tasks([], [raw])
        assert result[0].task_id == "x"
        assert isinstance(result[0], SubTask)


# ── DifyClient mock mode ──────────────────────────────────────────────────────

class TestDifyClientMock:
    @pytest.mark.asyncio
    async def test_order_agent_mock(self):
        client = DifyClient(
            base_url="http://mock",
            api_key="key",
            agent_type=LogisticsAgentType.ORDER,
            mock_mode=True,
        )
        result = await client.run("查询订单 SO-001")
        assert "订单" in result

    @pytest.mark.asyncio
    async def test_tracking_agent_mock(self):
        client = DifyClient(
            base_url="http://mock",
            api_key="key",
            agent_type=LogisticsAgentType.TRACKING,
            mock_mode=True,
        )
        result = await client.run("追踪运单 SF1234567890")
        assert "追踪" in result or "运单" in result


# ── dispatch_router ───────────────────────────────────────────────────────────

class TestDispatchRouter:
    def _state(self, sub_tasks, iteration=0) -> OrchestratorState:
        return OrchestratorState(
            messages=[],
            sub_tasks=sub_tasks,
            orchestrator_iteration=iteration,
        )

    def test_routes_to_dispatch_when_pending(self):
        task = SubTask(task_id="1", agent_type=LogisticsAgentType.ORDER, instruction="test")
        state = self._state([task])
        assert dispatch_router(state) == "dispatch"

    def test_routes_to_aggregator_when_all_done(self):
        task = SubTask(
            task_id="1",
            agent_type=LogisticsAgentType.ORDER,
            instruction="test",
            status=TaskStatus.COMPLETED,
        )
        state = self._state([task])
        assert dispatch_router(state) == "result_aggregator"

    def test_routes_to_aggregator_on_max_iterations(self):
        task = SubTask(task_id="1", agent_type=LogisticsAgentType.ORDER, instruction="test")
        state = self._state([task], iteration=10)
        assert dispatch_router(state) == "result_aggregator"


# ── dify_registry ─────────────────────────────────────────────────────────────

class TestDifyRegistry:
    def test_all_agent_types_registered(self, dify_registry):
        for agent_type in LogisticsAgentType:
            assert agent_type in dify_registry, f"Missing: {agent_type}"

    def test_all_in_mock_mode(self, dify_registry):
        for client in dify_registry.values():
            assert client.mock_mode is True


# ── graph structure ───────────────────────────────────────────────────────────

class TestOrchestratorGraphStructure:
    def test_graph_compiles(self, compiled_graph):
        assert compiled_graph is not None

    def test_graph_has_expected_nodes(self):
        graph = LogisticsOrchestratorGraphBuilder().build()
        compiled = graph.compile()
        node_names = set(compiled.get_graph().nodes.keys())
        expected = {"turn_init", "memory_load", "analyze_and_plan", "dispatch", "result_aggregator", "turn_finalize"}
        assert expected.issubset(node_names), f"Missing nodes: {expected - node_names}"
