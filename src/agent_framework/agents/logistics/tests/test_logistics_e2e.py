from __future__ import annotations

"""物流协调器端到端验证。

mock LLM（analyze_and_plan + result_aggregator + turn_finalize）+ mock Dify，
在不依赖任何外部服务的情况下跑通完整图流程，验证：

  1. 单 Agent 流程  — 意图→规划→dispatch→聚合
  2. 多 Agent 串行  — 两个子任务依次执行
  3. 任务失败与重试 — Dify 抛异常后正确标记 FAILED
  4. 会话连续性     — 同 thread_id 第二轮恢复 checkpoint
  5. 边界情况       — 空子任务 / 全量 agent 类型
  6. 多轮对话能力   — turn_count、task_history 累积、轮次隔离、消息裁剪

说明：
  graph.ainvoke() 只返回 OutputState（messages/final_answer/errors）。
  sub_tasks / intent / orchestrator_iteration 等内部字段须通过
  graph.aget_state(config).values 读取完整 checkpoint 状态。
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver

from agent_framework.agents.logistics.dify_registry import build_dify_registry
from agent_framework.agents.logistics.graph import LogisticsOrchestratorGraphBuilder
from agent_framework.agents.logistics.nodes.analyze_and_plan import SubTaskSpec, TaskPlan
from agent_framework.agents.logistics.state import (
    LogisticsAgentType,
    OrchestratorState,
    SubTask,
    TaskStatus,
)
from agent_framework.config.settings import Settings

# ── 共用 fixture & 工具 ───────────────────────────────────────────────────────

@pytest.fixture
def settings() -> Settings:
    return Settings(
        ENVIRONMENT="development",
        LLM_PROVIDER="openai",
        CHECKPOINTER_TYPE="memory",
        NACOS_ENABLED=False,
        LANGFUSE_ENABLED=False,
        DIFY_MOCK_MODE=True,
    )


@pytest.fixture
def graph(settings):
    """每个测试独立的 MemorySaver，互不干扰。"""
    checkpointer = MemorySaver()
    return LogisticsOrchestratorGraphBuilder().compile(checkpointer=checkpointer)


def _make_config(settings, thread_id: str) -> dict:
    return {
        "configurable": {
            "thread_id": thread_id,
            "settings": settings,
            "dify_registry": build_dify_registry(settings),
            "context": {"user_id": "tester", "tenant_id": "acme", "memory_enabled": False},
        }
    }


async def _get_full_state(graph, config: dict) -> dict:
    """从 checkpoint 读取完整的 OrchestratorState（含内部字段）。"""
    snapshot = await graph.aget_state(config)
    return snapshot.values


def _mock_planner(sub_task_specs: list[SubTaskSpec], intent: str = "测试意图",
                  referenced_orders: list[str] | None = None,
                  referenced_shipments: list[str] | None = None):
    """构造 analyze_and_plan_node 使用的 LLM mock。

    代码路径：llm.with_structured_output(TaskPlan).ainvoke(messages)
    必须用 MagicMock 承载 with_structured_output 返回值，
    再将 ainvoke 设为 AsyncMock，否则 await 得到 AsyncMock 而非 TaskPlan。
    """
    plan = TaskPlan(
        intent=intent,
        sub_tasks=sub_task_specs,
        referenced_orders=referenced_orders or [],
        referenced_shipments=referenced_shipments or [],
    )
    mock_chain = MagicMock()
    mock_chain.ainvoke = AsyncMock(return_value=plan)
    mock_llm = MagicMock()
    mock_llm.with_structured_output.return_value = mock_chain
    return mock_llm


def _mock_aggregator(answer: str = "操作完成。"):
    """构造 result_aggregator_node 使用的 LLM mock。"""
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content=answer))
    return mock_llm


def _mock_summarizer(summary: str = "会话摘要：操作已完成。"):
    """构造 turn_finalize._generate_summary 使用的 LLM mock。"""
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content=summary))
    return mock_llm


# ── Case 1: 单 Agent 完整流程 ─────────────────────────────────────────────────

class TestSingleAgentFlow:
    @pytest.mark.asyncio
    async def test_order_query_flow(self, graph, settings):
        """查询订单：order_agent 被调度，final_answer 有值，无 errors。"""
        cfg = _make_config(settings, "t1")
        planner = _mock_planner(
            [SubTaskSpec(agent_type=LogisticsAgentType.ORDER, instruction="查询订单 SO-001 状态")],
            intent="查询订单物流状态",
        )
        with (
            patch("agent_framework.agents.logistics.nodes.analyze_and_plan.get_llm", return_value=planner),
            patch("agent_framework.agents.logistics.nodes.result_aggregator.get_llm",
                  return_value=_mock_aggregator("订单 SO-001 已发货，预计明日送达。")),
            patch("agent_framework.agents.logistics.nodes.turn_finalize.get_llm",
                  return_value=_mock_summarizer()),
        ):
            result = await graph.ainvoke(
                {"messages": [HumanMessage(content="查一下订单 SO-001 的状态")], "thread_id": "t1"},
                config=cfg,
            )

        assert result["final_answer"] == "订单 SO-001 已发货，预计明日送达。"
        assert len(result["messages"]) >= 2
        assert result.get("errors", []) == []

    @pytest.mark.asyncio
    async def test_sub_task_marked_completed(self, graph, settings):
        """验证 sub_task 执行后状态被正确标记为 COMPLETED（从 checkpoint 读取）。"""
        cfg = _make_config(settings, "t2")
        planner = _mock_planner(
            [SubTaskSpec(agent_type=LogisticsAgentType.TRACKING, instruction="追踪运单 SF001")],
            intent="货物追踪",
        )
        with (
            patch("agent_framework.agents.logistics.nodes.analyze_and_plan.get_llm", return_value=planner),
            patch("agent_framework.agents.logistics.nodes.result_aggregator.get_llm",
                  return_value=_mock_aggregator("运单在途，预计明日到达。")),
            patch("agent_framework.agents.logistics.nodes.turn_finalize.get_llm",
                  return_value=_mock_summarizer()),
        ):
            await graph.ainvoke(
                {"messages": [HumanMessage(content="追踪运单 SF001")], "thread_id": "t2"},
                config=cfg,
            )

        state = await _get_full_state(graph, cfg)
        sub_tasks = state["sub_tasks"]
        assert len(sub_tasks) == 1
        assert sub_tasks[0].status == TaskStatus.COMPLETED
        assert sub_tasks[0].agent_type == LogisticsAgentType.TRACKING
        assert sub_tasks[0].result is not None
        assert "追踪" in sub_tasks[0].result


# ── Case 2: 多 Agent 串行流程 ─────────────────────────────────────────────────

class TestMultiAgentSerialFlow:
    @pytest.mark.asyncio
    async def test_two_agents_both_completed(self, graph, settings):
        """追踪 + 运输调度：两个子任务均 COMPLETED，dispatch 循环两次。"""
        cfg = _make_config(settings, "t3")
        planner = _mock_planner(
            [
                SubTaskSpec(agent_type=LogisticsAgentType.TRACKING, instruction="追踪运单当前位置"),
                SubTaskSpec(agent_type=LogisticsAgentType.TRANSPORT, instruction="重新调度更快承运商"),
            ],
            intent="追踪并重新调度延误运单",
        )
        with (
            patch("agent_framework.agents.logistics.nodes.analyze_and_plan.get_llm", return_value=planner),
            patch("agent_framework.agents.logistics.nodes.result_aggregator.get_llm",
                  return_value=_mock_aggregator("运单已重新调度，今日送达。")),
            patch("agent_framework.agents.logistics.nodes.turn_finalize.get_llm",
                  return_value=_mock_summarizer()),
        ):
            await graph.ainvoke(
                {"messages": [HumanMessage(content="运单延误了，帮我重新安排")], "thread_id": "t3"},
                config=cfg,
            )

        state = await _get_full_state(graph, cfg)
        sub_tasks = state["sub_tasks"]
        assert len(sub_tasks) == 2
        assert all(t.status == TaskStatus.COMPLETED for t in sub_tasks)
        agent_types = {t.agent_type for t in sub_tasks}
        assert LogisticsAgentType.TRACKING in agent_types
        assert LogisticsAgentType.TRANSPORT in agent_types

    @pytest.mark.asyncio
    async def test_iteration_counter_increments(self, graph, settings):
        """dispatch 循环 N 次后 orchestrator_iteration == N。"""
        cfg = _make_config(settings, "t4")
        planner = _mock_planner(
            [
                SubTaskSpec(agent_type=LogisticsAgentType.ORDER, instruction="查订单"),
                SubTaskSpec(agent_type=LogisticsAgentType.INVENTORY, instruction="查库存"),
                SubTaskSpec(agent_type=LogisticsAgentType.WAREHOUSE, instruction="查库位"),
            ],
            intent="查询订单、库存和库位",
        )
        with (
            patch("agent_framework.agents.logistics.nodes.analyze_and_plan.get_llm", return_value=planner),
            patch("agent_framework.agents.logistics.nodes.result_aggregator.get_llm",
                  return_value=_mock_aggregator("查询结果汇总完毕。")),
            patch("agent_framework.agents.logistics.nodes.turn_finalize.get_llm",
                  return_value=_mock_summarizer()),
        ):
            await graph.ainvoke(
                {"messages": [HumanMessage(content="帮我查一下订单、库存和库位")], "thread_id": "t4"},
                config=cfg,
            )

        state = await _get_full_state(graph, cfg)
        assert state["orchestrator_iteration"] == 3
        assert all(t.status == TaskStatus.COMPLETED for t in state["sub_tasks"])


# ── Case 3: 任务失败与重试 ────────────────────────────────────────────────────

class TestTaskFailureHandling:
    @pytest.mark.asyncio
    async def test_dify_exception_marks_task_failed(self, graph, settings):
        """Dify 抛异常 → 重试 1 次 → FAILED，图不崩溃，errors 有记录。"""
        registry = build_dify_registry(settings)
        registry[LogisticsAgentType.CUSTOMS].run = AsyncMock(
            side_effect=ConnectionError("Dify service unavailable")
        )
        cfg = {
            "configurable": {
                "thread_id": "t5",
                "settings": settings,
                "dify_registry": registry,
                "context": {"user_id": "tester", "tenant_id": "acme", "memory_enabled": False},
            }
        }
        planner = _mock_planner(
            [SubTaskSpec(agent_type=LogisticsAgentType.CUSTOMS, instruction="检查清关状态")],
            intent="清关状态查询",
        )
        with (
            patch("agent_framework.agents.logistics.nodes.analyze_and_plan.get_llm", return_value=planner),
            patch("agent_framework.agents.logistics.nodes.result_aggregator.get_llm",
                  return_value=_mock_aggregator("清关查询失败，请联系客服。")),
            patch("agent_framework.agents.logistics.nodes.turn_finalize.get_llm",
                  return_value=_mock_summarizer()),
        ):
            result = await graph.ainvoke(
                {"messages": [HumanMessage(content="帮我查清关状态")], "thread_id": "t5"},
                config=cfg,
            )

        # OutputState 可直接检查
        assert len(result.get("errors", [])) > 0
        assert result["final_answer"]

        # 完整状态通过 checkpoint 读取
        state = await _get_full_state(graph, cfg)
        failed = [t for t in state["sub_tasks"] if t.status == TaskStatus.FAILED]
        assert len(failed) == 1
        assert "Dify service unavailable" in failed[0].error

    @pytest.mark.asyncio
    async def test_retry_count_recorded(self, graph, settings):
        """失败任务在 _MAX_RETRY(1) 次重试后 retry_count == 2，状态 FAILED。"""
        registry = build_dify_registry(settings)
        registry[LogisticsAgentType.SUPPLIER].run = AsyncMock(
            side_effect=TimeoutError("timeout")
        )
        cfg = {
            "configurable": {
                "thread_id": "t6",
                "settings": settings,
                "dify_registry": registry,
                "context": {"user_id": "tester", "tenant_id": "acme", "memory_enabled": False},
            }
        }
        planner = _mock_planner(
            [SubTaskSpec(agent_type=LogisticsAgentType.SUPPLIER, instruction="查询供应商交货期")],
            intent="供应商查询",
        )
        with (
            patch("agent_framework.agents.logistics.nodes.analyze_and_plan.get_llm", return_value=planner),
            patch("agent_framework.agents.logistics.nodes.result_aggregator.get_llm",
                  return_value=_mock_aggregator("供应商查询失败。")),
            patch("agent_framework.agents.logistics.nodes.turn_finalize.get_llm",
                  return_value=_mock_summarizer()),
        ):
            await graph.ainvoke(
                {"messages": [HumanMessage(content="查供应商交货期")], "thread_id": "t6"},
                config=cfg,
            )

        state = await _get_full_state(graph, cfg)
        task = state["sub_tasks"][0]
        assert task.status == TaskStatus.FAILED
        assert task.retry_count == 2


# ── Case 4: 会话连续性（checkpoint 恢复）────────────────────────────────────

class TestSessionContinuity:
    @pytest.mark.asyncio
    async def test_second_turn_appends_messages(self, graph, settings):
        """同 thread_id 第二轮对话，messages 累积而不是覆盖。"""
        thread_id = "t7"
        cfg = _make_config(settings, thread_id)

        # 第一轮
        p1 = _mock_planner(
            [SubTaskSpec(agent_type=LogisticsAgentType.ORDER, instruction="查订单")],
            intent="订单查询",
        )
        with (
            patch("agent_framework.agents.logistics.nodes.analyze_and_plan.get_llm", return_value=p1),
            patch("agent_framework.agents.logistics.nodes.result_aggregator.get_llm",
                  return_value=_mock_aggregator("订单已发货。")),
            patch("agent_framework.agents.logistics.nodes.turn_finalize.get_llm",
                  return_value=_mock_summarizer("第1轮：查询了订单，已发货。")),
        ):
            r1 = await graph.ainvoke(
                {"messages": [HumanMessage(content="查订单状态")], "thread_id": thread_id},
                config=cfg,
            )

        # 第二轮（同 thread_id，从 checkpoint 恢复）
        p2 = _mock_planner(
            [SubTaskSpec(agent_type=LogisticsAgentType.INVENTORY, instruction="查库存")],
            intent="库存查询",
        )
        with (
            patch("agent_framework.agents.logistics.nodes.analyze_and_plan.get_llm", return_value=p2),
            patch("agent_framework.agents.logistics.nodes.result_aggregator.get_llm",
                  return_value=_mock_aggregator("库存充足。")),
            patch("agent_framework.agents.logistics.nodes.turn_finalize.get_llm",
                  return_value=_mock_summarizer("第2轮：查询了库存，充足。")),
        ):
            r2 = await graph.ainvoke(
                {"messages": [HumanMessage(content="再查一下库存")], "thread_id": thread_id},
                config=cfg,
            )

        # 第二轮消息数 > 第一轮（历史累积）
        assert len(r2["messages"]) > len(r1["messages"])
        assert r2["final_answer"] == "库存充足。"

        # 完整状态中 intent 更新为第二轮
        state = await _get_full_state(graph, cfg)
        assert state["intent"] == "库存查询"


# ── Case 5: 边界情况 ──────────────────────────────────────────────────────────

class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_empty_sub_tasks_no_crash(self, graph, settings):
        """LLM 规划返回空子任务列表，图正常结束并返回提示信息。"""
        cfg = _make_config(settings, "t8")
        planner = _mock_planner([], intent="无法识别意图")
        with (
            patch("agent_framework.agents.logistics.nodes.analyze_and_plan.get_llm", return_value=planner),
            patch("agent_framework.agents.logistics.nodes.result_aggregator.get_llm",
                  return_value=_mock_aggregator("抱歉，无法处理该请求。")),
            patch("agent_framework.agents.logistics.nodes.turn_finalize.get_llm",
                  return_value=_mock_summarizer()),
        ):
            result = await graph.ainvoke(
                {"messages": [HumanMessage(content="你好")], "thread_id": "t8"},
                config=cfg,
            )

        assert result["final_answer"] is not None
        assert result.get("errors", []) == []

    @pytest.mark.asyncio
    async def test_intent_propagated_to_state(self, graph, settings):
        """analyze_and_plan 输出的 intent 正确写入 checkpoint state。"""
        cfg = _make_config(settings, "t9")
        planner = _mock_planner(
            [SubTaskSpec(agent_type=LogisticsAgentType.ANALYTICS, instruction="生成本月KPI报告")],
            intent="生成供应链KPI分析报告",
        )
        with (
            patch("agent_framework.agents.logistics.nodes.analyze_and_plan.get_llm", return_value=planner),
            patch("agent_framework.agents.logistics.nodes.result_aggregator.get_llm",
                  return_value=_mock_aggregator("本月KPI已生成。")),
            patch("agent_framework.agents.logistics.nodes.turn_finalize.get_llm",
                  return_value=_mock_summarizer()),
        ):
            await graph.ainvoke(
                {"messages": [HumanMessage(content="出一份本月KPI报告")], "thread_id": "t9"},
                config=cfg,
            )

        state = await _get_full_state(graph, cfg)
        assert state["intent"] == "生成供应链KPI分析报告"

    @pytest.mark.asyncio
    async def test_all_eight_agent_types_dispatchable(self, graph, settings):
        """所有 8 种 agent 类型均可被调度，dispatch 循环 8 次全部 COMPLETED。"""
        cfg = _make_config(settings, "t10")
        all_specs = [
            SubTaskSpec(agent_type=t, instruction=f"测试 {t.value}")
            for t in LogisticsAgentType
        ]
        planner = _mock_planner(all_specs, intent="全量 agent 类型测试")
        with (
            patch("agent_framework.agents.logistics.nodes.analyze_and_plan.get_llm", return_value=planner),
            patch("agent_framework.agents.logistics.nodes.result_aggregator.get_llm",
                  return_value=_mock_aggregator("全部完成。")),
            patch("agent_framework.agents.logistics.nodes.turn_finalize.get_llm",
                  return_value=_mock_summarizer()),
        ):
            await graph.ainvoke(
                {"messages": [HumanMessage(content="测试所有 agent")], "thread_id": "t10"},
                config=cfg,
            )

        state = await _get_full_state(graph, cfg)
        assert len(state["sub_tasks"]) == 8
        assert all(t.status == TaskStatus.COMPLETED for t in state["sub_tasks"])
        assert state["orchestrator_iteration"] == 8


# ── Case 6: 多轮对话能力 ──────────────────────────────────────────────────────

class TestMultiTurnCapability:
    @pytest.mark.asyncio
    async def test_turn_count_increments(self, graph, settings):
        """每轮调用后 turn_count 递增。"""
        thread_id = "mt1"
        cfg = _make_config(settings, thread_id)

        for i in range(1, 4):
            p = _mock_planner(
                [SubTaskSpec(agent_type=LogisticsAgentType.ORDER, instruction=f"第{i}轮查询")],
                intent=f"第{i}轮意图",
            )
            with (
                patch("agent_framework.agents.logistics.nodes.analyze_and_plan.get_llm", return_value=p),
                patch("agent_framework.agents.logistics.nodes.result_aggregator.get_llm",
                      return_value=_mock_aggregator(f"第{i}轮完成。")),
                patch("agent_framework.agents.logistics.nodes.turn_finalize.get_llm",
                      return_value=_mock_summarizer(f"第{i}轮摘要")),
            ):
                await graph.ainvoke(
                    {"messages": [HumanMessage(content=f"第{i}轮请求")], "thread_id": thread_id},
                    config=cfg,
                )

        state = await _get_full_state(graph, cfg)
        assert state["turn_count"] == 3

    @pytest.mark.asyncio
    async def test_task_history_accumulates(self, graph, settings):
        """每轮结束后 task_history 累积 TurnRecord。"""
        thread_id = "mt2"
        cfg = _make_config(settings, thread_id)

        intents = ["查询订单", "查询库存", "分析KPI"]
        agent_types = [LogisticsAgentType.ORDER, LogisticsAgentType.INVENTORY, LogisticsAgentType.ANALYTICS]

        for intent, agent_type in zip(intents, agent_types):
            p = _mock_planner(
                [SubTaskSpec(agent_type=agent_type, instruction=f"执行：{intent}")],
                intent=intent,
            )
            with (
                patch("agent_framework.agents.logistics.nodes.analyze_and_plan.get_llm", return_value=p),
                patch("agent_framework.agents.logistics.nodes.result_aggregator.get_llm",
                      return_value=_mock_aggregator(f"{intent}完成。")),
                patch("agent_framework.agents.logistics.nodes.turn_finalize.get_llm",
                      return_value=_mock_summarizer(f"{intent}摘要")),
            ):
                await graph.ainvoke(
                    {"messages": [HumanMessage(content=intent)], "thread_id": thread_id},
                    config=cfg,
                )

        state = await _get_full_state(graph, cfg)
        history = state["task_history"]
        assert len(history) == 3
        assert [r.turn for r in history] == [1, 2, 3]
        assert [r.intent for r in history] == intents

    @pytest.mark.asyncio
    async def test_turn_isolation_previous_tasks_not_reprocessed(self, graph, settings):
        """上一轮的 COMPLETED 任务在新一轮不被重复执行。"""
        thread_id = "mt3"
        cfg = _make_config(settings, thread_id)

        # 第一轮：order_agent
        p1 = _mock_planner(
            [SubTaskSpec(agent_type=LogisticsAgentType.ORDER, instruction="查订单")],
            intent="订单查询",
        )
        with (
            patch("agent_framework.agents.logistics.nodes.analyze_and_plan.get_llm", return_value=p1),
            patch("agent_framework.agents.logistics.nodes.result_aggregator.get_llm",
                  return_value=_mock_aggregator("订单已发货。")),
            patch("agent_framework.agents.logistics.nodes.turn_finalize.get_llm",
                  return_value=_mock_summarizer()),
        ):
            await graph.ainvoke(
                {"messages": [HumanMessage(content="查订单")], "thread_id": thread_id},
                config=cfg,
            )

        # 第二轮：tracking_agent（应只有 1 个任务）
        p2 = _mock_planner(
            [SubTaskSpec(agent_type=LogisticsAgentType.TRACKING, instruction="追踪运单")],
            intent="货物追踪",
        )
        with (
            patch("agent_framework.agents.logistics.nodes.analyze_and_plan.get_llm", return_value=p2),
            patch("agent_framework.agents.logistics.nodes.result_aggregator.get_llm",
                  return_value=_mock_aggregator("运单在途。")),
            patch("agent_framework.agents.logistics.nodes.turn_finalize.get_llm",
                  return_value=_mock_summarizer()),
        ):
            await graph.ainvoke(
                {"messages": [HumanMessage(content="追踪运单")], "thread_id": thread_id},
                config=cfg,
            )

        state = await _get_full_state(graph, cfg)
        # turn_finalize 清理后，sub_tasks 只保留最新轮次
        sub_tasks = state["sub_tasks"]
        assert all(t.turn == 2 for t in sub_tasks), "旧轮次任务应已被清理"
        assert len(sub_tasks) == 1
        assert sub_tasks[0].agent_type == LogisticsAgentType.TRACKING

    @pytest.mark.asyncio
    async def test_short_term_summary_written(self, graph, settings):
        """turn_finalize 生成的摘要写入 short_term_summary。"""
        thread_id = "mt4"
        cfg = _make_config(settings, thread_id)
        expected_summary = "已完成订单查询，订单处于发货状态。"

        p = _mock_planner(
            [SubTaskSpec(agent_type=LogisticsAgentType.ORDER, instruction="查订单")],
            intent="订单查询",
        )
        with (
            patch("agent_framework.agents.logistics.nodes.analyze_and_plan.get_llm", return_value=p),
            patch("agent_framework.agents.logistics.nodes.result_aggregator.get_llm",
                  return_value=_mock_aggregator("订单已发货。")),
            patch("agent_framework.agents.logistics.nodes.turn_finalize.get_llm",
                  return_value=_mock_summarizer(expected_summary)),
        ):
            await graph.ainvoke(
                {"messages": [HumanMessage(content="查订单")], "thread_id": thread_id},
                config=cfg,
            )

        state = await _get_full_state(graph, cfg)
        assert state.get("short_term_summary") == expected_summary

    @pytest.mark.asyncio
    async def test_message_trimming_on_overflow(self, graph, settings):
        """消息超过 KEEP_LAST_MESSAGES 时，旧消息被裁剪。"""
        # 使用较小的 keep 值便于测试
        trim_settings = Settings(
            ENVIRONMENT="development",
            LLM_PROVIDER="openai",
            CHECKPOINTER_TYPE="memory",
            NACOS_ENABLED=False,
            LANGFUSE_ENABLED=False,
            DIFY_MOCK_MODE=True,
            ORCHESTRATOR_KEEP_LAST_MESSAGES=4,  # 每轮产生 ~2 条消息，4轮后触发裁剪
        )
        checkpointer = MemorySaver()
        trim_graph = LogisticsOrchestratorGraphBuilder().compile(checkpointer=checkpointer)

        thread_id = "mt5"
        cfg = {
            "configurable": {
                "thread_id": thread_id,
                "settings": trim_settings,
                "dify_registry": build_dify_registry(trim_settings),
                "context": {"user_id": "tester", "tenant_id": "acme", "memory_enabled": False},
            }
        }

        # 连续 5 轮，每轮累积 2 条消息，超过 keep=4
        for i in range(1, 6):
            p = _mock_planner(
                [SubTaskSpec(agent_type=LogisticsAgentType.ORDER, instruction=f"第{i}轮")],
                intent=f"第{i}轮意图",
            )
            with (
                patch("agent_framework.agents.logistics.nodes.analyze_and_plan.get_llm", return_value=p),
                patch("agent_framework.agents.logistics.nodes.result_aggregator.get_llm",
                      return_value=_mock_aggregator(f"第{i}轮完成。")),
                patch("agent_framework.agents.logistics.nodes.turn_finalize.get_llm",
                      return_value=_mock_summarizer(f"摘要{i}")),
            ):
                await trim_graph.ainvoke(
                    {"messages": [HumanMessage(content=f"第{i}轮请求")], "thread_id": thread_id},
                    config=cfg,
                )

        state = await _get_full_state(trim_graph, cfg)
        # 消息数不超过 keep 限制
        assert len(state["messages"]) <= trim_settings.ORCHESTRATOR_KEEP_LAST_MESSAGES
