# Agent Framework - Claude Context

## Project Overview

Production-ready LangGraph AI Agent framework with FastAPI, PostgreSQL, Langfuse observability, A2A protocol support, and Nacos service registry.

## Tech Stack

- **Framework**: LangGraph 1.0 + LangChain 1.2
- **API**: FastAPI + uvicorn
- **LLM**: OpenAI GPT-4o (primary), Anthropic Claude (secondary), DeepSeek (cost-optimized)
- **Storage**: PostgreSQL 16 + pgvector
- **Observability**: Langfuse (tracing) + Prometheus (metrics) + structlog (logging)
- **A2A**: Google A2A Protocol
- **Config/Registry**: Nacos 2.x
- **Package manager**: uv

## Key Design Rules

1. All list fields in AgentState MUST use Annotated reducers
2. Compile graphs ONCE at startup in FastAPI lifespan, never in request handlers
3. Tool errors return ToolMessage (not exceptions) so LLM can retry
4. AgentContext is NOT persisted in checkpoints - use for per-invocation config only
5. Use Command(goto=...) for multi-agent routing instead of enumerating conditional edges
6. 任务完成后生成任务总结文档到 doc 目录下

## Package Management

Always use `uv` to add/remove packages. Never use pip directly.
