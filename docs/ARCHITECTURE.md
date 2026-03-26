# LangGraph 项目基础框架设计

> 生产级 AI Agent 应用框架 — 基座组件清单 & 技术选型

---

## 一、整体目录结构

```
langgraph/
├── src/
│   └── agent_framework/              # 主 Python 包（src layout）
│       ├── config/                   # 配置层
│       │   ├── settings.py           # Pydantic-Settings BaseSettings
│       │   ├── llm_config.py         # LLM 提供商工厂 + 选型
│       │   ├── nacos_config.py       # Nacos 动态配置客户端（覆盖 Settings 热更新）
│       │   └── logging_config.py     # structlog / loguru 初始化
│       │
│       ├── core/                     # 核心层：Graph Engine 基础
│       │   ├── state.py              # AgentState TypedDict + reducers
│       │   ├── context.py            # Runtime Context（不持久化）
│       │   ├── channels.py           # 自定义 channel reducers
│       │   └── errors.py             # AgentError / ToolError / GraphError
│       │
│       ├── graphs/                   # 图定义层
│       │   ├── base_graph.py         # 抽象工厂：build_graph() 模式
│       │   ├── react_graph.py        # ReAct 单 Agent 图
│       │   ├── plan_execute_graph.py # Plan-and-Execute 图
│       │   ├── supervisor_graph.py   # 多 Agent Supervisor 图
│       │   └── subgraphs/            # 专家子图（specialist 封装）
│       │       ├── research_subgraph.py
│       │       └── execution_subgraph.py
│       │
│       ├── nodes/                    # 节点层（8 个核心节点）
│       │   ├── llm_node.py           # LLM 调用节点，支持流式
│       │   ├── tool_node.py          # ToolNode 封装（并行工具执行）
│       │   ├── planner_node.py       # 结构化输出生成计划
│       │   ├── executor_node.py      # 执行单步计划
│       │   ├── router_node.py        # 意图分类 / 路由
│       │   ├── memory_node.py        # 读写长期记忆，注入 memory_context
│       │   ├── human_node.py         # interrupt() 暂停，人工审批
│       │   └── guard_node.py         # 输入/输出护栏检查
│       │
│       ├── edges/                    # 边层：条件路由
│       │   ├── routers.py            # 条件边路由函数
│       │   └── conditions.py         # 可复用断言谓词
│       │
│       ├── agents/                   # Agent 层
│       │   ├── base_agent.py         # 抽象 BaseAgent（ABC）
│       │   ├── react_agent.py        # ReAct Agent
│       │   ├── plan_execute_agent.py # Plan-Execute Agent
│       │   ├── coordinator_agent.py  # 多 Agent 协调器
│       │   └── specialist/
│       │       ├── researcher.py     # 网络研究专家
│       │       ├── coder.py          # 代码生成专家
│       │       └── analyst.py        # 数据分析专家
│       │
│       ├── tools/                    # 工具层
│       │   ├── registry.py           # ToolRegistry：动态加载/发现
│       │   ├── base_tool.py          # BaseTool（retry + 可观测钩子）
│       │   ├── search/
│       │   │   ├── tavily_search.py  # Tavily 网络搜索
│       │   │   └── wikipedia.py      # Wikipedia 查询
│       │   ├── code/
│       │   │   └── python_repl.py    # 沙箱 Python REPL
│       │   ├── rag/
│       │   │   ├── retriever.py      # 向量检索工具
│       │   │   └── indexer.py        # 文档摄取/嵌入工具
│       │   └── external/
│       │       ├── http_client.py    # 通用 HTTP API 调用
│       │       └── sql_tool.py       # 只读 SQL 查询
│       │
│       ├── memory/                   # 记忆层（4 层）
│       │   ├── short_term.py         # 线程级对话缓冲（MemorySaver）
│       │   ├── long_term.py          # 跨线程 BaseStore（Postgres）
│       │   ├── episodic.py           # 情节记忆：摘要 + 检索
│       │   ├── semantic.py           # 语义记忆：向量搜索
│       │   └── manager.py            # MemoryManager：统一门面
│       │
│       ├── persistence/              # 持久层
│       │   ├── checkpoint_factory.py # 工厂：MemorySaver or PostgresSaver
│       │   ├── postgres_store.py     # AsyncPostgresStore（长期存储）
│       │   ├── models.py             # SQLAlchemy ORM 模型
│       │   └── migrations/           # Alembic 迁移
│       │       ├── env.py
│       │       └── versions/
│       │           └── 0001_initial_schema.py
│       │
│       ├── api/                      # API 层
│       │   ├── app.py                # FastAPI 应用工厂
│       │   ├── dependencies.py       # DI：get_checkpointer, get_graph
│       │   ├── middleware.py         # CORS, 认证, request_id
│       │   ├── routes/
│       │   │   ├── health.py         # GET /health, /readiness
│       │   │   ├── threads.py        # 会话线程 CRUD
│       │   │   ├── runs.py           # POST /runs（同步/流式）
│       │   │   ├── a2a.py            # GET /.well-known/agent.json, POST /a2a
│       │   │   └── admin.py          # 图内省, checkpoint 管理
│       │   └── schemas/
│       │       ├── requests.py       # Pydantic 请求模型
│       │       └── responses.py      # Pydantic 响应模型
│       │
│       ├── a2a/                      # A2A 协同层（Google A2A Protocol）
│       │   ├── agent_card.py         # AgentCard：声明 Agent 能力 / skill 描述
│       │   ├── server.py             # A2A Server：暴露 /a2a 端点，处理跨 Agent 任务委托
│       │   ├── client.py             # A2A Client：向远端 Agent 发起任务委托
│       │   ├── task_manager.py       # TaskManager：管理跨 Agent 任务状态（SUBMITTED/WORKING/DONE）
│       │   └── schemas.py            # A2A 标准 Pydantic 模型（Task, Artifact, Message）
│       │
│       └── observability/            # 可观测层
│           ├── langfuse_tracer.py    # Langfuse tracer + CallbackHandler
│           ├── metrics.py            # Prometheus 指标定义
│           ├── logging.py            # structlog 结构化日志配置
│           └── callbacks.py          # LangChain callbacks（节点级遥测）
│
├── tests/
│   ├── conftest.py                   # 共享 fixtures
│   ├── unit/                         # 快速单元测试（无 I/O）
│   ├── integration/                  # 图端到端测试
│   └── e2e/                          # 全栈测试（含 Postgres）
│
├── scripts/
│   ├── bootstrap.sh                  # uv sync + alembic upgrade head
│   ├── seed_db.py                    # 开发数据库初始化
│   └── generate_openapi.py           # 导出 OpenAPI spec
│
├── docs/
│   ├── architecture.md               # 系统图 + 设计决策
│   ├── state_schema.md               # State 字段参考
│   ├── adding_tools.md               # 新增工具开发指南
│   └── deployment.md                 # Docker、环境变量、扩展说明
│
├── docker/
│   ├── Dockerfile                    # 多阶段生产镜像
│   ├── Dockerfile.dev                # 开发镜像（热重载）
│   └── docker-compose.yml            # Postgres 16 + app 一键启动
│
├── .env.example                      # 所有环境变量说明
├── .gitignore
├── .python-version                   # Python 3.12
├── langgraph.json                    # LangGraph Server 入口清单
├── pyproject.toml                    # uv 管理，含 optional deps
├── alembic.ini
├── Makefile                          # dev, test, lint, docker 快捷命令
└── CLAUDE.md                         # AI 助手上下文文件
```

---

## 二、基座组件清单

### 2.1 Graph Engine 组件

#### AgentState（`core/state.py`）

主状态 TypedDict，**所有 list 字段必须声明 Reducer**（防止并行分支写冲突）：

```python
class AgentState(TypedDict):
    # 消息通道：add_messages reducer 自动处理去重
    messages: Annotated[list[AnyMessage], add_messages]
    # 会话标识
    thread_id: str
    request_id: str
    # Plan-Execute 专用
    plan: list[str]
    current_step: int
    # 工具调用
    tool_calls: list[ToolCall]
    tool_results: list[ToolMessage]
    # 记忆
    memory_context: str
    # 输出
    final_answer: str | None
    # 错误追加（operator.add reducer）
    errors: Annotated[list[str], operator.add]
    # 透传元数据
    metadata: dict[str, Any]
```

**InputState / OutputState 分离**：定义为 `AgentState` 的子集，防止内部 scratchpad 字段泄漏给 API 调用方。

#### AgentContext（`core/context.py`）

运行时配置，**不持久化**（通过 `context_schema` 注入，不存入 checkpoint）：

```python
class AgentContext(TypedDict):
    user_id: str
    tenant_id: str
    llm_provider: Literal["openai", "anthropic", "deepseek"]
    model_name: str
    temperature: float
    max_tokens: int
    tools_enabled: list[str]   # 动态工具白名单
    memory_enabled: bool
    streaming: bool
    max_iterations: int
```

#### 节点函数签名

```python
async def node_fn(
    state: AgentState,
    runtime: Runtime[AgentContext]
) -> dict:
    # 只返回修改的 state 字段
    ...
```

### 2.2 三种 Agent 类型

| Agent | 图结构 | 适用场景 |
|-------|--------|---------|
| **ReAct** | `START → llm → [tool_node ↔ llm] → END` | 通用问答、工具调用 |
| **Plan-Execute** | `START → planner → execute_step → [continue\|replan\|END]` | 复杂多步骤任务 |
| **Supervisor** | `START → supervisor → [researcher\|coder\|analyst\|END]` | 多 Agent 协作编排 |

### 2.3 节点清单（8 个）

| 节点 | 文件 | 职责 |
|------|------|------|
| `llm_node` | `nodes/llm_node.py` | LLM 调用，支持 astream_events 流式 |
| `tool_node` | `nodes/tool_node.py` | 基于 prebuilt ToolNode，asyncio.gather 并行执行 |
| `planner_node` | `nodes/planner_node.py` | `with_structured_output(Plan)` 生成类型化计划 |
| `executor_node` | `nodes/executor_node.py` | 执行单步计划，推进 `current_step` |
| `router_node` | `nodes/router_node.py` | 意图分类，选择下游路径 |
| `memory_node` | `nodes/memory_node.py` | `store.search()` 向量检索，注入 `memory_context` |
| `human_node` | `nodes/human_node.py` | `interrupt("approve: {action}")` 暂停图执行 |
| `guard_node` | `nodes/guard_node.py` | 输入/输出护栏，策略规则验证 |

### 2.4 记忆系统（4 层）

| 类型 | 实现方案 | 作用域 | 存储位置 |
|------|---------|--------|---------|
| **短期记忆** | `MemorySaver`（开发）/ `AsyncPostgresSaver`（生产） | 线程级，对话连续性 | Postgres `checkpoints` 表 |
| **长期记忆** | `AsyncPostgresStore`，namespace: `(user_id, "facts")` | 用户级，跨会话事实 | Postgres `store` 表 |
| **情节记忆** | 对话摘要 Pipeline → Store | 历史会话压缩检索 | namespace: `(user_id, "episodes")` |
| **语义记忆** | `AsyncPostgresStore` + `IndexConfig`（pgvector） | 相似度向量检索 | pgvector 索引 |

### 2.5 工具清单（7 个）

| 类别 | 工具类 | 外部依赖 |
|------|--------|---------|
| 搜索 | `TavilySearchTool` | `tavily-python` |
| 搜索 | `WikipediaTool` | `langchain-community` |
| 代码 | `PythonREPLTool` | `langchain-experimental` |
| RAG | `VectorRetrieverTool` | `langchain-core` + `AsyncPostgresStore` |
| RAG | `DocumentIndexerTool` | `langchain-text-splitters` |
| 外部 | `HTTPClientTool` | `httpx` |
| 外部 | `SQLQueryTool`（只读） | `sqlalchemy` |

**ToolRegistry**：支持按 `AgentContext.tools_enabled` 动态筛选，实现多租户工具隔离，无需为不同用户维护多个图实例。

### 2.6 API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/health` | 存活探针 |
| `GET` | `/readiness` | 就绪探针（DB + 图检查） |
| `POST` | `/api/v1/threads` | 创建会话线程 |
| `GET` | `/api/v1/threads/{thread_id}` | 获取线程状态/历史 |
| `DELETE` | `/api/v1/threads/{thread_id}` | 删除线程 + checkpoints |
| `POST` | `/api/v1/runs` | 执行图（同步 or 流式 SSE） |
| `GET` | `/api/v1/runs/{run_id}` | 获取运行结果 |
| `GET` | `/api/v1/admin/graph` | 图结构内省 |
| `GET` | `/.well-known/agent.json` | A2A AgentCard（能力声明） |
| `POST` | `/a2a` | A2A JSON-RPC 入口（tasks/send 等） |

流式响应：`POST /api/v1/runs` + `{"stream": true}` → `text/event-stream`，基于 `graph.astream_events(input, config, version="v2")`。

### 2.7 可观测性组件

| 组件 | 技术 | 关键指标/字段 |
|------|------|-------------|
| 追踪 | **Langfuse**（`LangfuseCallbackHandler`） | Trace / Span / Generation 三级结构；token cost、延迟、评分；支持自托管 |
| 指标 | Prometheus（`/metrics`） | `agent_invocations_total`, `agent_latency_seconds`, `tool_calls_total{tool_name,status}`, `llm_tokens_total{provider,model,type}` |
| 日志 | structlog（JSON） | 每条日志绑定 `thread_id`, `run_id`, `node_name`, `user_id` |
| 回调 | `AgentCallbackHandler` | `on_llm_end` 记录 token，`on_tool_end` 记录延迟，`langfuse_handler` 注入 `config["callbacks"]` |

**Langfuse 接入方式：**

```python
from langfuse.callback import CallbackHandler

langfuse_handler = CallbackHandler(
    public_key=settings.LANGFUSE_PUBLIC_KEY,
    secret_key=settings.LANGFUSE_SECRET_KEY.get_secret_value(),
    host=settings.LANGFUSE_HOST,          # 支持私有化部署
    session_id=state["thread_id"],
    user_id=context["user_id"],
    trace_name="agent-run",
)

# 注入图调用
await graph.ainvoke(input, config={"callbacks": [langfuse_handler]})
```

Langfuse 支持 **自托管**（docker-compose 一键部署），无需依赖外部 SaaS，适合私有化场景。

### 2.8 A2A 协同组件

基于 [Google A2A Protocol](https://google.github.io/A2A/)，实现跨 Agent / 跨服务的标准化任务委托。

**核心概念：**

| 概念 | 说明 |
|------|------|
| **AgentCard** | JSON 描述文件，声明 Agent 的 skill、输入输出格式、端点地址，托管于 `GET /.well-known/agent.json` |
| **Task** | 跨 Agent 工作单元，状态机：`submitted → working → [completed\|failed\|canceled]` |
| **Artifact** | 任务输出产物（文本、文件、结构化数据） |
| **A2A Server** | 接收来自其他 Agent 的任务委托，映射到内部 LangGraph 图执行 |
| **A2A Client** | 向注册在 Nacos 的远端 Agent 发起任务，支持同步 / SSE 流式 / 轮询三种模式 |

**文件职责：**

| 文件 | 职责 |
|------|------|
| `a2a/agent_card.py` | 构建并暴露 AgentCard JSON，描述本 Agent 的能力清单 |
| `a2a/server.py` | FastAPI router，处理 `POST /a2a`（JSON-RPC），将 Task 分发给对应图 |
| `a2a/client.py` | 基于 `httpx.AsyncClient`，向远端 Agent 发起 `tasks/send` / `tasks/sendSubscribe` |
| `a2a/task_manager.py` | 维护 Task 状态，支持 `tasks/get` / `tasks/cancel` |
| `a2a/schemas.py` | A2A 标准 Pydantic 模型：`Task`, `TaskState`, `Artifact`, `Message`, `AgentCard` |

**A2A 端点：**

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/.well-known/agent.json` | 返回 AgentCard（能力声明） |
| `POST` | `/a2a` | JSON-RPC 入口：`tasks/send`, `tasks/get`, `tasks/cancel` |
| `POST` | `/a2a/subscribe` | SSE 流式任务（`tasks/sendSubscribe`） |

**Nacos 服务注册与 A2A 发现：**

```
本 Agent 启动
  → 注册到 Nacos（serviceName=agent-framework, metadata={a2a_url, skills}）
  → A2A Client 查询 Nacos 发现目标 Agent 地址
  → 直接 HTTP 调用远端 /a2a 端点，无需硬编码 URL
```

### 2.9 Nacos 配置与服务发现

**双重职责：**

| 功能 | 说明 |
|------|------|
| **动态配置** | 运行时热更新 LLM 参数、限流阈值、Feature Flag，无需重启 |
| **服务注册/发现** | Agent 实例注册，A2A Client 通过服务名发现远端 Agent 地址 |

**`config/nacos_config.py` 职责：**

```python
class NacosConfigManager:
    """启动时拉取 Nacos 配置，覆盖 Settings；同时订阅变更回调实现热更新"""

    async def start(self) -> None:
        # 1. 拉取初始配置（dataId=agent-framework, group=DEFAULT_GROUP）
        # 2. 注册监听器：配置变更时回调 _on_config_change()
        # 3. 注册服务实例（ip/port/metadata）

    async def _on_config_change(self, config: str) -> None:
        # 热更新：解析新配置，刷新 app.state.settings
        ...

    async def get_service_url(self, service_name: str) -> str:
        # 服务发现：查询健康实例，返回 http://ip:port
        ...
```

**Nacos 配置命名空间规划：**

| Namespace | DataId | Group | 内容 |
|-----------|--------|-------|------|
| `dev` | `agent-framework.yaml` | `DEFAULT_GROUP` | 开发环境配置 |
| `prod` | `agent-framework.yaml` | `DEFAULT_GROUP` | 生产环境配置 |
| `shared` | `llm-config.yaml` | `AI_GROUP` | LLM 参数（跨服务共享） |

**FastAPI Lifespan 集成：**

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    nacos = NacosConfigManager(settings)
    await nacos.start()           # 拉取配置 + 注册服务 + 订阅变更
    app.state.nacos = nacos

    checkpointer = await get_checkpointer()
    app.state.graph = build_react_graph().compile(checkpointer=checkpointer)

    yield

    await nacos.deregister()      # 优雅下线（从 Nacos 注销）
    await checkpointer.aclose()
```

---

## 三、技术选型

| 维度 | 选型 | 版本 | 选型理由 |
|------|------|------|---------|
| **核心框架** | LangGraph + LangChain | 1.0.x + 1.2.x | Pregel 执行模型保障幂等性；prebuilt ToolNode / create_react_agent 成熟稳定 |
| **LLM 主力** | OpenAI GPT-4o | — | 并行工具调用最可靠，结构化输出支持最完善 |
| **LLM 备选** | Anthropic Claude | — | 200k 长上下文，适合 planner 节点 |
| **LLM 成本优化** | DeepSeek / Zhipu | — | 统一 `ChatOpenAI(base_url=...)` 适配，无需额外 SDK |
| **向量存储** | PostgreSQL + pgvector | 16 | 与 checkpoint 同库，运维零额外成本；百万级向量够用 |
| **向量存储（扩展）** | Qdrant | — | 千万级向量 ANN 场景，仅改 `tools/rag/retriever.py` |
| **Checkpoint / Store** | `AsyncPostgresSaver` + `AsyncPostgresStore` | — | 统一 Postgres，`ShallowPostgresSaver` 可降低历史存储开销 |
| **ORM** | SQLAlchemy 2.x async + asyncpg | 2.x | 异步优先，FastAPI 友好 |
| **数据库迁移** | Alembic | 1.x | 与 SQLAlchemy 无缝集成 |
| **API 框架** | FastAPI | 0.128 | 原生 async，`StreamingResponse` SSE，Pydantic v2 自动 schema |
| **可观测—追踪** | **Langfuse** | 3.x | 支持自托管（隐私友好）；Trace/Span/Generation 三级结构；原生 LangChain callback 集成；内置评分和数据集管理 |
| **可观测—指标** | Prometheus + Grafana | — | 工业标准，Agent 专属 KPI 指标 |
| **可观测—日志** | structlog | 25.x | JSON 结构化，兼容 ELK / Datadog / Cloud Logging |
| **A2A 协同** | Google A2A Protocol | 0.2.x | 跨 Agent / 跨服务标准化任务委托；AgentCard 能力声明；支持同步/流式/轮询 |
| **服务注册/配置** | **Nacos** | 2.x | 服务注册供 A2A 发现；动态配置热更新（无需重启）；支持命名空间隔离多环境 |
| **包管理** | uv | — | 已安装，10-100x 快于 pip，lock 文件可重现 |
| **代码质量** | Ruff + Mypy `--strict` | — | 单工具替代 black / isort / flake8 |
| **测试** | pytest + anyio + pytest-httpx | — | anyio 支持 async 测试，pytest-httpx mock 外部 HTTP |
| **容器化** | Docker 多阶段 + docker-compose | — | Postgres 16 + pgvector + app 一键启动 |
| **CI/CD** | GitHub Actions | — | ci（lint+test）/ integration（nightly）/ release（tag 触发） |

---

## 四、关键设计模式

### 4.1 State 字段必须声明 Reducer

```python
# ✅ 正确：explicit reducer，并行分支安全
errors: Annotated[list[str], operator.add]
messages: Annotated[list[AnyMessage], add_messages]

# ❌ 错误：last-write-wins，并行分支会丢数据
messages: list[AnyMessage]
```

### 4.2 Graph 编译为单例

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    checkpointer = await get_checkpointer()
    app.state.graph = build_react_graph().compile(checkpointer=checkpointer)
    yield
    await checkpointer.aclose()
```

**永远不要在请求 handler 内部编译图**。

### 4.3 工具错误返回 ToolMessage，不抛异常

```python
# ✅ 正确：LLM 感知错误并自动重试
return ToolMessage(content=f"Error: {e}", tool_call_id=tc_id, status="error")

# ❌ 错误：异常传播到图执行器，需要额外 try/except
raise ToolError(str(e))
```

### 4.4 Command 路由（多 Agent）

```python
# 替代枚举 conditional edges，支持动态路由
return Command(goto="researcher", update={"messages": [...]})
```

### 4.5 人工中断（Human-in-the-Loop）

```
graph 执行 → human_node 调用 interrupt("approve: {action}")
→ 状态 checkpoint 挂起
→ API 返回 {"status": "interrupted", "payload": {...}}
→ 调用方 POST Command(resume=True/False)
→ 图从断点继续
```

### 4.6 迭代保护

```python
def should_continue(state: AgentState) -> str:
    if len(state["messages"]) > MAX_ITERATIONS * 2:
        return "end"  # 强制终止，防止无限循环
    if state["messages"][-1].tool_calls:
        return "tools"
    return "end"
```

同时设置 `RunnableConfig["recursion_limit"]` 作为双重保护。

---

## 五、实施阶段

| 阶段 | 内容 | 关键文件 |
|------|------|---------|
| **Phase 1** 基础（Days 1-3） | pyproject.toml + State schema + structlog + MemorySaver | `core/state.py`, `config/settings.py`, `observability/logging.py` |
| **Phase 2** 核心图（Days 4-7） | LLM Factory + ReAct Graph + TavilySearch 工具 + 集成测试 | `graphs/react_graph.py`, `config/llm_config.py`, `tools/search/tavily_search.py` |
| **Phase 3** 记忆持久化（Days 8-11） | Alembic + PostgresSaver + AsyncPostgresStore + 记忆节点 | `persistence/`, `memory/` |
| **Phase 4** 高级 Agent（Days 12-16） | Plan-Execute + Supervisor + 人工中断 + 护栏 | `graphs/plan_execute_graph.py`, `graphs/supervisor_graph.py`, `nodes/human_node.py` |
| **Phase 5** API + 可观测（Days 17-21） | FastAPI 全路由 + **Langfuse** + Prometheus + structlog | `api/`, `observability/langfuse_tracer.py` |
| **Phase 6** A2A + Nacos（Days 22-26） | AgentCard + A2A Server/Client + Nacos 注册/动态配置 | `a2a/`, `config/nacos_config.py` |
| **Phase 7** 生产加固（Days 27-30） | Docker 多阶段 + CI/CD + E2E 测试（含 Nacos + Langfuse） | `docker/`, `.github/workflows/` |

---

## 六、验证方式

```bash
# 单元测试（无 I/O，快速）
uv run pytest tests/unit/ -v

# 集成测试（真实图，in-memory checkpointer）
uv run pytest tests/integration/ -v

# API 测试（同步 + 流式响应）
uv run pytest tests/integration/test_api.py -v

# 持久化验证：checkpoint 保存 → 进程重启 → 同 thread_id 恢复
uv run pytest tests/integration/test_persistence.py -v

# 本地 Docker 全栈验证
docker-compose up -d
curl http://localhost:8000/health
curl http://localhost:8000/readiness

# Langfuse Dashboard：查看 Trace / Span / Generation，确认节点 span 完整，cost 统计正确
# 自托管：docker-compose up -d langfuse → http://localhost:3000
# SaaS：访问 https://cloud.langfuse.com → 项目 "agent-framework"

# A2A 验证
curl http://localhost:8000/.well-known/agent.json         # 获取 AgentCard
curl -X POST http://localhost:8000/a2a \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tasks/send","params":{...},"id":1}'

# Nacos 验证
# 访问 Nacos 控制台 http://localhost:8848/nacos → 确认服务注册、配置下发
```
