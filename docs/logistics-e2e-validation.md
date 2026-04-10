# 物流协调器端到端验证报告

## 验证范围

`tests/integration/test_logistics_e2e.py` — 10 个测试用例，覆盖完整图执行流程。

## 技术说明

### mock 策略

| 组件 | mock 方式 | 原因 |
|------|----------|------|
| `analyze_and_plan` LLM | `patch get_llm`，`with_structured_output` 返回 `MagicMock`，`ainvoke` 设为 `AsyncMock(return_value=TaskPlan(...))` | 需要返回真实 Pydantic 对象，否则 intent 字段变成 AsyncMock 导致 msgpack 序列化失败 |
| `result_aggregator` LLM | `patch get_llm`，`ainvoke` 设为 `AsyncMock(return_value=AIMessage(...))` | 返回真实 AIMessage 确保 final_answer 可序列化 |
| Dify 子 Agent | `DIFY_MOCK_MODE=True`（内置 mock 响应库） | 无需外部服务 |

### 内部状态读取

`graph.ainvoke()` 只返回 `OutputState`（messages/final_answer/errors）。
`sub_tasks`、`intent`、`orchestrator_iteration` 等内部字段须通过 checkpoint 读取：

```python
snapshot = await graph.aget_state(config)
state = snapshot.values  # 完整 OrchestratorState
```

## 测试结果

| # | 测试名称 | 验证内容 | 结果 |
|---|---------|---------|------|
| 1 | `test_order_query_flow` | final_answer 有值，无 errors | PASS |
| 2 | `test_sub_task_marked_completed` | sub_task 状态 COMPLETED，result 含追踪关键词 | PASS |
| 3 | `test_two_agents_both_completed` | 两个 sub_task 均 COMPLETED | PASS |
| 4 | `test_iteration_counter_increments` | 3 个任务后 orchestrator_iteration == 3 | PASS |
| 5 | `test_dify_exception_marks_task_failed` | Dify 异常 → FAILED，errors 有记录，图不崩溃 | PASS |
| 6 | `test_retry_count_recorded` | 重试 1 次后 retry_count == 2，状态 FAILED | PASS |
| 7 | `test_second_turn_appends_messages` | 第二轮消息累积，intent 更新为新轮意图 | PASS |
| 8 | `test_empty_sub_tasks_no_crash` | 空子任务规划不崩溃，返回兜底回复 | PASS |
| 9 | `test_intent_propagated_to_state` | intent 字段正确写入 checkpoint | PASS |
| 10 | `test_all_eight_agent_types_dispatchable` | 8 种 agent 类型全部 COMPLETED，iteration == 8 | PASS |

**10 / 10 PASSED**

## 发现并修复的问题

1. **AsyncMock 序列化错误**：`with_structured_output` 的返回值被设为 `AsyncMock`，导致 `await chain.ainvoke()` 返回的是 `AsyncMock` 对象而非 `TaskPlan`，进而写入 checkpoint 时 msgpack 序列化失败。
   - 修复：用 `MagicMock` 承载链对象，仅将 `ainvoke` 设为 `AsyncMock(return_value=plan)`。

2. **OutputState 字段裁剪**：`output_schema=OutputState` 裁掉了内部字段，测试直接从 `ainvoke` 返回值读取 `sub_tasks` 会得到空 `[]`。
   - 修复：通过 `graph.aget_state(config).values` 读取完整 checkpoint 状态。
