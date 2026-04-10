# 物流供应链协调器（Logistics Orchestrator）

## 目录结构

所有物流相关代码集中在独立目录，与框架其他模块解耦：

```
src/agent_framework/logistics/
├── __init__.py              # 公共导出：Agent、GraphBuilder、State 类型
├── agent.py                 # LogisticsOrchestratorAgent — 对外入口
├── graph.py                 # 图拓扑定义 + LogisticsOrchestratorGraphBuilder
├── state.py                 # OrchestratorState、SubTask、LogisticsAgentType
├── dify_client.py           # Dify Workflow API 异步客户端（含 mock 模式）
├── dify_registry.py         # 从 Settings 构建 {AgentType → DifyClient} 映射
└── nodes/
    ├── analyze_and_plan.py  # 意图识别 + 任务规划节点
    ├── dispatch.py          # 子任务分发节点 + dispatch_router 路由函数
    ├── result_aggregator.py # 结果聚合节点
    └── memory.py            # 记忆加载 / 保存节点
```

## 图拓扑

```
START → memory_load → analyze_and_plan → dispatch ←──┐
                                              │        │ (PENDING 任务存在)
                                         dispatch_router
                                              │ (全部完成)
                                              ↓
                                      result_aggregator → memory_save → END
```

## 核心组件

### OrchestratorState（`state.py`）

继承 `AgentState`，扩展字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `intent` | `str \| None` | LLM 识别出的用户意图 |
| `sub_tasks` | `Annotated[list[SubTask], _merge_sub_tasks]` | 子任务列表，按 task_id 去重合并 |
| `short_term_summary` | `str \| None` | 历史会话摘要（防 token 溢出） |
| `user_preferences` | `dict` | 用户偏好（从 Store 加载） |
| `orchestrator_iteration` | `int` | 分发循环计数（上限 10，防死循环） |

### 子任务生命周期

```
PENDING → RUNNING → COMPLETED
                 ↘ FAILED（重试 1 次后）
```

### Dify 集成

每个 `LogisticsAgentType` 对应一个 Dify Workflow App：

| Agent 类型 | 职责 | 环境变量 |
|-----------|------|---------|
| `order_agent` | 订单 CRUD、状态变更 | `DIFY_ORDER_AGENT_URL/KEY` |
| `tracking_agent` | 货物追踪、ETA | `DIFY_TRACKING_AGENT_URL/KEY` |
| `inventory_agent` | 库存查询、预留 | `DIFY_INVENTORY_AGENT_URL/KEY` |
| `transport_agent` | 承运商调度、路线 | `DIFY_TRANSPORT_AGENT_URL/KEY` |
| `warehouse_agent` | 入出库、库位 | `DIFY_WAREHOUSE_AGENT_URL/KEY` |
| `supplier_agent` | 供应商、采购 | `DIFY_SUPPLIER_AGENT_URL/KEY` |
| `customs_agent` | 清关、报关 | `DIFY_CUSTOMS_AGENT_URL/KEY` |
| `analytics_agent` | KPI、预测 | `DIFY_ANALYTICS_AGENT_URL/KEY` |

**Mock 模式**（默认开启）：设置 `DIFY_MOCK_MODE=false` 并填写 URL/KEY 即可切换到真实 Dify 服务。

### 三层记忆

| 层级 | 存储 | 内容 |
|------|------|------|
| 工作记忆 | Checkpoint（PostgreSQL） | 当前会话 messages + sub_tasks 状态 |
| 情景记忆 | PostgreSQL Store | 历史操作摘要，namespace=`logistics/episodes/{tenant}/{user}` |
| 语义记忆 | 会话摘要 | 超过 `MEMORY_SUMMARIZE_THRESHOLD` 条消息时 LLM 压缩写入 Store |

## 使用方式

```python
from agent_framework.logistics import LogisticsOrchestratorAgent
from agent_framework.config.settings import get_settings

settings = get_settings()
agent = LogisticsOrchestratorAgent(settings)
agent.build_graph(checkpointer=checkpointer, store=store)

# 同步调用
result = await agent.run(
    user_message="查一下订单 SO-001 的物流状态",
    thread_id="thread-123",
    user_id="user-456",
)
print(result["final_answer"])

# 流式调用（SSE）
async for event in agent.stream("帮我重新调度延误的运单", thread_id="thread-123"):
    ...
```

## 配置项（`.env`）

```env
# Mock 模式（开发/测试，默认 true）
DIFY_MOCK_MODE=true

# 切换到真实 Dify 时按需填写
DIFY_ORDER_AGENT_URL=https://dify.example.com/v1
DIFY_ORDER_AGENT_KEY=app-xxxx
DIFY_TRACKING_AGENT_URL=https://dify.example.com/v1
DIFY_TRACKING_AGENT_KEY=app-yyyy

# 协调器控制
ORCHESTRATOR_MAX_ITERATIONS=10
ORCHESTRATOR_TASK_TIMEOUT=60
```
