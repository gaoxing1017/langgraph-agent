"""FastAPI 应用工厂。

启动序列（lifespan）：
  1. 配置结构化日志
  2. Nacos：拉取远程配置并注册服务实例
  3. 持久化：创建 checkpointer 和长期存储
  4. 图：将 ReAct 图作为单例编译（存储于 app.state.graph）

关闭序列（lifespan 清理）：
  1. Nacos：注销服务实例
  2. 关闭 checkpointer 和 store 连接
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agent_framework.agents.logistics.agent import LogisticsOrchestratorAgent
from agent_framework.api.middleware import LoggingMiddleware, RequestIDMiddleware
from agent_framework.api.routes import admin, health, runs, threads
from agent_framework.api.routes import a2a as a2a_routes
from agent_framework.config.logging_config import configure_logging
from agent_framework.config.nacos_config import NacosConfigManager
from agent_framework.config.settings import Settings, get_settings
from agent_framework.graphs.react_graph import build_react_graph
from agent_framework.persistence.checkpoint_factory import get_checkpointer
from agent_framework.persistence.postgres_store import get_postgres_store

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """管理整个服务生命周期内的应用级资源。

    此处初始化的所有资源均可通过路由处理器中的
    request.app.state.* 以及 api/dependencies.py 中的依赖注入访问。
    """
    settings: Settings = app.state.settings
    configure_logging(settings.LOG_LEVEL, json_logs=settings.is_production, log_dir=settings.LOG_DIR)

    # Nacos：拉取配置并注册服务
    nacos = NacosConfigManager(settings)
    await nacos.start()
    app.state.nacos = nacos

    # 持久化初始化
    checkpointer = await get_checkpointer(settings)
    store = await get_postgres_store(settings)
    app.state.checkpointer = checkpointer
    app.state.store = store

    # 将图作为单例编译一次
    graph = build_react_graph().compile(checkpointer=checkpointer, store=store)
    app.state.graph = graph

    # 物流协调器 Agent
    logistics_agent = LogisticsOrchestratorAgent(settings)
    logistics_agent.build_graph(checkpointer=checkpointer, store=store)
    app.state.logistics_agent = logistics_agent

    logger.info("应用启动完成", environment=settings.ENVIRONMENT)
    yield

    # 优雅关闭
    await nacos.deregister()
    if hasattr(checkpointer, "aclose"):
        await checkpointer.aclose()
    if store and hasattr(store, "aclose"):
        await store.aclose()
    logger.info("应用关闭完成")


def create_app(settings: Settings | None = None) -> FastAPI:
    """创建并配置 FastAPI 应用。

    Args:
        settings: 覆盖配置（在测试中很有用）。默认从环境变量/.env 文件加载。
    Returns:
        已挂载所有中间件和路由的 FastAPI 实例。
    """
    _settings = settings or get_settings()

    app = FastAPI(
        title="Agent Framework API",
        version="1.0.0",
        description="Production-ready LangGraph AI Agent Framework",
        lifespan=lifespan,
    )

    app.state.settings = _settings

    # 中间件注册
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # TODO: 生产环境中限制为已知来源
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(RequestIDMiddleware)

    # 路由挂载
    app.include_router(health.router)
    app.include_router(threads.router)
    app.include_router(runs.router)
    app.include_router(admin.router)
    app.include_router(a2a_routes.router)

    return app
