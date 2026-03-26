# Agent Framework

基于 LangGraph 的生产级 AI Agent 框架，支持 ReAct、Plan-Execute、多 Agent 协同三种模式，集成 Langfuse 可观测、A2A 跨 Agent 协议与 Nacos 服务注册/动态配置。

---

## 目录

- [特性概览](#特性概览)
- [技术栈](#技术栈)
- [快速开始](#快速开始)
- [项目结构](#项目结构)
- [核心模块](#核心模块)
  - [Agent 类型](#agent-类型)
  - [记忆系统](#记忆系统)
  - [工具清单](#工具清单)
  - [A2A 协同](#a2a-协同)
  - [Nacos 集成](#nacos-集成)
  - [可观测性](#可观测性)
- [API 文档](#api-文档)
- [配置说明](#配置说明)
- [开发指南](#开发指南)
- [部署](#部署)
- [测试](#测试)

---

## 特性概览

- **三种 Agent 模式**：ReAct（工具调用循环）、Plan-Execute（分步规划执行）、Supervisor（多 Agent 协调）
- **四层记忆系统**：短期（线程级）/ 长期（跨会话）/ 情节（摘要压缩）/ 语义（向量检索）
- **A2A 协议**：基于 Google A2A Protocol，支持跨服务 Agent 任务委托与能力声明
- **Nacos 集成**：服务注册发现 + 动态配置热更新（无需重启）
- **Langfuse 追踪**：Trace/Span/Generation 三级链路，支持私有化部署
- **流式响应**：SSE 实时流式输出，基于 `astream_events`
- **人工中断**：`interrupt()` 机制支持任务暂停与人工审批恢复
- **多 LLM 支持**：OpenAI / Anthropic / DeepSeek / Zhipu，统一工厂切换

---

## 技术栈

| 层级 | 技术 | 版本 |
|------|------|------|
| Agent 框架 | LangGraph + LangChain | 1.0.5 + 1.2.x |
| API 服务 | FastAPI + Uvicorn | 0.115+ |
| 数据存储 | PostgreSQL 16 + pgvector | — |
| Checkpoint | AsyncPostgresSaver / MemorySaver | — |
| 追踪 | Langfuse | 3.x（支持自托管） |
| 指标 | Prometheus + Grafana | — |
| 日志 | structlog | 25.x |
| A2A 协同 | Google A2A Protocol | 0.2.x |
| 服务注册 | Nacos | 2.x |
| 包管理 | uv | — |
| 容器化 | Docker + docker-compose | — |

---

## 快速开始

### 前置条件

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) 包管理器
- Docker & Docker Compose（可选，用于完整栈启动）

### 1. 克隆并安装依赖

```bash
git clone <repo-url>
cd langgraph

# 一键初始化（安装依赖 + 复制 .env + 数据库迁移）
bash scripts/bootstrap.sh
```

### 2. 配置环境变量

```bash
# 编辑 .env，填写必要配置
vim .env
```

最小配置（仅需 OpenAI Key 即可启动）：

```env
OPENAI_API_KEY=sk-...
```

### 3. 启动开发服务器

```bash
make dev
# → http://localhost:8000
# → http://localhost:8000/docs  (Swagger UI)
```

### 4. 完整栈启动（含 Postgres / Nacos / Langfuse）

```bash
make docker-up
# Postgres:  localhost:5432
# Nacos:     http://localhost:8848/nacos  (nacos/nacos)
# Langfuse:  http://localhost:3000
# App:       http://localhost:8000
```

### 5. 快速验证

```bash
# 健康检查
curl http://localhost:8000/health

# 查看 AgentCard（A2A 能力声明）
curl http://localhost:8000/.well-known/agent.json

# 发起一次 Agent 对话
curl -X POST http://localhost:8000/api/v1/runs \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "What is 2+2?"}],
    "user_id": "demo"
  }'

# 流式响应
curl -X POST http://localhost:8000/api/v1/runs \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{
    "messages": [{"role": "user", "content": "Explain quantum computing"}],
    "stream": true
  }'
```

---

## 项目结构

```
langgraph/
├── src/
│   └── agent_framework/
│       ├── config/          # 配置：Settings, LLM Factory, Nacos, 日志
│       ├── core/            # 核心：AgentState, AgentContext, 错误体系
│       ├── graphs/          # 图定义：ReAct / Plan-Execute / Supervisor
│       │   └── subgraphs/   # 专家子图：research / execution
│       ├── nodes/           # 节点：llm / tool / planner / executor / router / memory / human / guard
│       ├── edges/           # 路由：条件边函数 + 断言谓词
│       ├── agents/          # Agent 封装：BaseAgent + 3 类型 + 3 专家
│       ├── tools/           # 工具：Registry + 7 工具实现
│       ├── memory/          # 记忆：4 层 + Manager
│       ├── persistence/     # 持久化：Checkpointer + Store + Alembic
│       ├── api/             # API：FastAPI 路由 + Schema
│       ├── a2a/             # A2A：AgentCard + Server + Client + TaskManager
│       └── observability/   # 可观测：Langfuse + Prometheus + structlog
├── tests/
│   ├── unit/                # 单元测试（无 I/O）
│   ├── integration/         # 集成测试
│   └── e2e/                 # 端到端测试
├── scripts/                 # bootstrap.sh / seed_db.py / generate_openapi.py
├── docker/                  # Dockerfile / docker-compose.yml
├── docs/                    # 补充文档
├── .env.example             # 环境变量模板
├── pyproject.toml           # 依赖声明（uv）
├── langgraph.json           # LangGraph Server 入口
├── alembic.ini              # 数据库迁移配置
└── Makefile                 # 常用命令快捷入口
```

---

## 核心模块

### Agent 类型

#### ReAct Agent（默认）

LLM + 工具调用的紧密循环，适合通用问答与工具使用场景。

```
START → llm → [has_tool_calls?] → tools → llm → ... → END
```

```python
from agent_framework.agents.react_agent import ReActAgent
from agent_framework.tools.registry import ToolRegistry

registry = ToolRegistry()
registry.register(tavily_search, category="search")

agent = ReActAgent(settings, tool_registry=registry)
agent.build_graph(checkpointer=checkpointer)

result = await agent.ainvoke(
    input_state={"messages": [HumanMessage(content="Search for LangGraph tutorials")]},
    context={"user_id": "user-1", "tools_enabled": ["tavily_search"]},
    thread_id="thread-abc",
)
```

#### Plan-Execute Agent

先生成结构化计划，再逐步执行，适合复杂多步骤任务。

```
START → planner → execute_step → llm + tools → [more steps?] → execute_step → ... → END
```

#### Supervisor Agent（多 Agent）

协调者模式：Supervisor 将任务委托给专家子图（Researcher / Coder / Analyst）。

```
START → supervisor → [researcher | coder | analyst] → supervisor → ... → END
```

---

### 记忆系统

| 层级 | 作用域 | 实现 |
|------|--------|------|
| **短期记忆** | 线程内对话连续性 | `MemorySaver` / `AsyncPostgresSaver` |
| **长期记忆** | 跨会话用户事实 | `AsyncPostgresStore` namespace `(user_id, "facts")` |
| **情节记忆** | 历史会话摘要压缩 | 对话摘要 → Store namespace `(user_id, "episodes")` |
| **语义记忆** | 向量相似度检索 | `AsyncPostgresStore` + pgvector `IndexConfig` |

```python
from agent_framework.memory.manager import MemoryManager

manager = MemoryManager(store=store, llm=llm)

# 检索上下文（自动联合长期 + 情节记忆）
context = await manager.retrieve_context(user_id="user-1", query="Python async patterns")

# 存储事实
await manager.store_fact(user_id="user-1", key="preference", content="Prefers concise answers")

# 创建情节记忆（会话结束时调用）
await manager.create_episode(messages=messages, user_id="user-1", session_id="sess-xyz")
```

---

### 工具清单

| 类别 | 工具 | 描述 |
|------|------|------|
| 搜索 | `tavily_search` | Tavily 网络搜索（实时信息） |
| 搜索 | `wikipedia_search` | Wikipedia 词条查询 |
| 代码 | `python_repl` | 沙箱 Python 代码执行 |
| RAG | `vector_retriever` | 向量知识库检索 |
| RAG | `index_document` | 文档摄取与向量化 |
| 外部 | `http_get` | 通用 HTTP GET 请求 |
| 外部 | `sql_query` | 只读 SQL 查询 |

**注册工具：**

```python
from agent_framework.tools.registry import ToolRegistry
from agent_framework.tools.search.tavily_search import tavily_search

registry = ToolRegistry()
registry.register(tavily_search, category="search")

# 动态白名单（多租户隔离）
enabled = registry.get_enabled(["tavily_search"])
```

---

### A2A 协同

基于 [Google A2A Protocol](https://google.github.io/A2A/)，实现跨服务 Agent 标准化任务委托。

**AgentCard 声明（能力发现）：**

```bash
GET /.well-known/agent.json
```

```json
{
  "name": "agent-framework",
  "version": "1.0.0",
  "url": "http://localhost:8000",
  "skills": [
    {"id": "react_agent", "name": "ReAct Agent", ...},
    {"id": "research", "name": "Web Research", ...}
  ]
}
```

**任务委托：**

```bash
POST /a2a
{
  "jsonrpc": "2.0",
  "method": "tasks/send",
  "params": {
    "message": {"role": "user", "content": "Research LangGraph best practices"},
    "sessionId": "sess-001"
  },
  "id": 1
}
```

**A2A Client（向其他 Agent 委托）：**

```python
from agent_framework.a2a.client import A2AClient

# 通过 Nacos 发现目标 Agent 地址
url = await nacos_manager.get_service_url("researcher-agent")
client = A2AClient(base_url=url)

task = await client.send_task("Summarize recent AI papers", session_id="sess-1")
print(task.artifacts[0].content)
```

---

### Nacos 集成

**双重职责：动态配置 + 服务注册**

```env
NACOS_ENABLED=true
NACOS_SERVER_ADDRESSES=127.0.0.1:8848
NACOS_NAMESPACE=dev
NACOS_DATA_ID=agent-framework.yaml
NACOS_SERVICE_NAME=agent-framework
```

**Nacos 配置文件（agent-framework.yaml）示例：**

```yaml
DEFAULT_MODEL: gpt-4o-mini
DEFAULT_TEMPERATURE: 0.1
MAX_ITERATIONS: 15
LANGFUSE_ENABLED: true
```

配置变更后**无需重启**，应用自动热更新。服务注册后，其他 Agent 通过服务名发现此实例的 A2A 地址。

---

### 可观测性

#### Langfuse 追踪

```env
LANGFUSE_ENABLED=true
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=http://localhost:3000   # 自托管
```

每次 Agent 调用自动生成 Trace，包含：
- 完整节点执行链路（Span）
- LLM 请求/响应（Generation）+ token 用量
- 工具调用耗时
- 用户 ID / 会话 ID 绑定

#### Prometheus 指标

```
GET /metrics
```

| 指标 | 类型 | 说明 |
|------|------|------|
| `agent_invocations_total` | Counter | Agent 调用总次数（按状态） |
| `agent_latency_seconds` | Histogram | 调用延迟分布 |
| `tool_calls_total` | Counter | 工具调用次数（按工具名/状态） |
| `llm_tokens_total` | Counter | Token 消耗（按 provider/model/类型） |
| `active_threads` | Gauge | 当前活跃会话数 |

#### 结构化日志

每条日志自动附带上下文字段：

```json
{
  "timestamp": "2026-03-25T12:00:00Z",
  "level": "info",
  "event": "Agent invoke",
  "thread_id": "thread-abc",
  "run_id": "run-xyz",
  "node_name": "llm_node",
  "user_id": "user-1"
}
```

---

## API 文档

启动后访问 **http://localhost:8000/docs** 查看完整 Swagger UI。

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/health` | 存活探针 |
| `GET` | `/readiness` | 就绪探针 |
| `POST` | `/api/v1/threads` | 创建会话线程 |
| `GET` | `/api/v1/threads/{thread_id}` | 查询线程状态 |
| `DELETE` | `/api/v1/threads/{thread_id}` | 删除线程 |
| `POST` | `/api/v1/runs` | 执行 Agent（同步/流式） |
| `GET` | `/api/v1/runs/{run_id}` | 查询运行结果 |
| `GET` | `/api/v1/admin/graph` | 图结构内省 |
| `GET` | `/.well-known/agent.json` | A2A AgentCard |
| `POST` | `/a2a` | A2A JSON-RPC 入口 |

---

## 配置说明

所有配置通过环境变量或 `.env` 文件注入，支持 Nacos 动态覆盖。

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `ENVIRONMENT` | `development` | 环境标识（development/staging/production） |
| `LLM_PROVIDER` | `openai` | LLM 提供商 |
| `DEFAULT_MODEL` | `gpt-4o` | 默认模型名 |
| `OPENAI_API_KEY` | — | OpenAI API Key |
| `ANTHROPIC_API_KEY` | — | Anthropic API Key |
| `DEEPSEEK_API_KEY` | — | DeepSeek API Key |
| `DATABASE_URL` | `postgresql+asyncpg://...` | PostgreSQL 连接串 |
| `CHECKPOINTER_TYPE` | `memory` | `memory`（开发）或 `postgres`（生产） |
| `LANGFUSE_ENABLED` | `false` | 是否启用 Langfuse 追踪 |
| `LANGFUSE_HOST` | `http://localhost:3000` | Langfuse 服务地址（支持自托管） |
| `NACOS_ENABLED` | `false` | 是否启用 Nacos |
| `NACOS_SERVER_ADDRESSES` | `127.0.0.1:8848` | Nacos 地址 |
| `TAVILY_API_KEY` | — | Tavily 搜索 API Key |
| `MAX_ITERATIONS` | `20` | 单次调用最大迭代轮数 |

完整变量列表参见 [.env.example](.env.example)。

---

## 开发指南

### 常用命令

```bash
make install        # 安装所有依赖（含 extras）
make dev            # 启动开发服务器（热重载）
make lint           # Ruff 代码检查
make format         # Ruff 格式化
make typecheck      # Mypy 类型检查
make test           # 运行全部测试
make test-unit      # 仅运行单元测试
make migrate        # 执行数据库迁移
make docker-up      # 启动完整 Docker 栈
make docker-down    # 停止 Docker 栈
```

### 新增工具

1. 在 `src/agent_framework/tools/<category>/` 下创建工具文件
2. 使用 `@tool` 装饰器定义异步函数，编写清晰的 docstring（LLM 依赖此描述选择工具）
3. 在应用启动时通过 `ToolRegistry.register()` 注册

```python
# tools/search/my_tool.py
from langchain_core.tools import tool

@tool
async def my_search(query: str) -> str:
    """Search using my custom API. Args: query: search query string."""
    ...
```

### 新增 Agent 图

1. 继承 `BaseGraphBuilder`，实现 `build()` 方法
2. 在 `langgraph.json` 中注册图入口
3. 在 `api/app.py` lifespan 中编译为单例

### State 设计规则

```python
# ✅ list 字段必须声明 Reducer
errors: Annotated[list[str], operator.add]
messages: Annotated[list[AnyMessage], add_messages]

# ❌ 不声明 Reducer 在并行分支下会丢数据
messages: list[AnyMessage]
```

---

## 部署

### Docker 生产部署

```bash
# 构建生产镜像
docker build -f docker/Dockerfile -t agent-framework:latest .

# 运行
docker run -p 8000:8000 --env-file .env agent-framework:latest
```

### 启用 PostgreSQL Checkpoint（生产必须）

```bash
# 安装 postgres 扩展
uv sync --extra postgres

# .env 配置
CHECKPOINTER_TYPE=postgres
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/agent_framework
```

### 启用 Langfuse 自托管

```bash
# docker-compose 已包含 langfuse 服务
make docker-up

# .env 配置
LANGFUSE_ENABLED=true
LANGFUSE_HOST=http://langfuse:3000   # Docker 网络内
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
```

---

## 测试

```bash
# 单元测试（无外部依赖，快速）
make test-unit

# 集成测试（真实图执行，in-memory checkpointer）
make test-integration

# E2E 测试（需要完整 Docker 栈 + API Keys）
make docker-up
uv run pytest tests/e2e/ -v

# 生成覆盖率报告
uv run pytest tests/unit/ tests/integration/ --cov=agent_framework --cov-report=html
```

---

## License

MIT
