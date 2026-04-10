# 项目启动与请求执行链路

## 一、启动阶段（进程启动）

```
uvicorn main:app
  └── create_app()                          # api/app.py:73
        ├── get_settings()                  # config/settings.py — 读取 .env
        ├── add_middleware()                # RequestID → Logging → CORS
        ├── include_router()                # health / threads / runs / admin / a2a
        └── lifespan() 注册为 asynccontextmanager

  lifespan() 执行（FastAPI 启动时）         # api/app.py:37
    ├── configure_logging()                 # 结构化日志（structlog）
    ├── NacosConfigManager.start()          # 拉取远程配置 + 注册服务实例
    ├── get_checkpointer(settings)          # memory / postgres checkpointer
    ├── get_postgres_store(settings)        # 长期向量存储
    └── build_react_graph().compile(...)    # 图编译为单例 → app.state.graph
          └── ReActGraphBuilder.build()     # graphs/react_graph.py:29
                ├── StateGraph(AgentState)
                ├── add_node("llm",   llm_node)
                ├── add_node("tools", build_tool_node([]))
                ├── START → "llm"
                ├── "llm" --conditional--> react_router → "tools" | END
                └── "tools" → "llm"
```

---

## 二、请求阶段（POST /api/v1/runs）

```
HTTP POST /api/v1/runs
  └── RequestIDMiddleware          # 注入 X-Request-ID
  └── LoggingMiddleware            # 记录请求/响应耗时

  create_run()                     # api/routes/runs.py:33
    ├── _build_context(body)       # 构建 AgentContext（llm_provider / tools_enabled 等）
    ├── 构造 input_state           # {"messages": [HumanMessage], "thread_id", "request_id"}
    ├── 构造 config                # {"configurable": {thread_id, settings, context}}
    │
    ├── [stream=False] graph.ainvoke(input_state, config)
    └── [stream=True]  graph.astream_events(...)  → SSE text/event-stream
```

---

## 三、图执行阶段（LangGraph 内部）

```
graph.ainvoke / astream_events
  │
  ├─ START
  │
  ├─ llm_node(state, config)              # nodes/llm_node.py:25
  │    ├── get_llm(settings, provider="siliconflow", ...)
  │    │     └── ChatOpenAI(base_url="https://api.siliconflow.cn/v1",
  │    │                    model="deepseek-ai/DeepSeek-V3")
  │    ├── llm.bind_tools(tools)          # 若 configurable["tools"] 非空
  │    └── llm.ainvoke(messages)  →  AIMessage
  │
  ├─ react_router(state)                  # edges/routers.py:22
  │    ├── is_over_iteration_limit?  → END
  │    ├── has_errors?               → END
  │    ├── has_tool_calls?           → "tools"
  │    └── 否则                      → END
  │
  ├─ [有 tool_calls] tools 节点           # langgraph.prebuilt.ToolNode
  │    ├── 并行执行所有 tool_calls
  │    ├── 返回 ToolMessage（含结果或错误）
  │    └── → 回到 llm_node（循环）
  │
  └─ END  →  OutputState{messages, final_answer, errors}
```

---

## 四、响应阶段

```
graph 返回 result
  └── create_run()
        ├── 提取 result["messages"] → [MessageOutput]
        └── 返回 RunResponse{run_id, thread_id, status, messages, final_answer, errors}
```

---

## 关键数据流

```
.env (LLM_PROVIDER=siliconflow)
  → Settings
    → lifespan → app.state.{graph, checkpointer, store, settings}
      → create_run → AgentContext + config["configurable"]
        → llm_node → get_llm() → ChatOpenAI(siliconflow)
          → DeepSeek-V3 API 调用
            → AIMessage → react_router → tools? → loop / END
```

---

## 关键文件索引

| 职责 | 文件 |
|------|------|
| 应用工厂 & 生命周期 | `src/agent_framework/api/app.py` |
| 配置加载 | `src/agent_framework/config/settings.py` |
| LLM 工厂 | `src/agent_framework/config/llm_config.py` |
| 图构建 | `src/agent_framework/graphs/react_graph.py` |
| LLM 节点 | `src/agent_framework/nodes/llm_node.py` |
| 工具节点 | `src/agent_framework/nodes/tool_node.py` |
| 条件路由 | `src/agent_framework/edges/routers.py` |
| 状态定义 | `src/agent_framework/core/state.py` |
| Run 路由 | `src/agent_framework/api/routes/runs.py` |
