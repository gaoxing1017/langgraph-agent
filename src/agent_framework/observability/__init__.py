"""可观测性栈：链路追踪、指标和结构化日志。

三个互补的层次：
  Langfuse   — LLM 感知的分布式追踪（Trace → Span → Generation）
  Prometheus — 通过 GET /metrics 暴露的时间序列指标
  structlog  — 绑定了请求/线程上下文的结构化 JSON 日志

启动时配置三者：
    configure_logging(settings.LOG_LEVEL, json_logs=settings.is_production)
    handler = get_langfuse_handler(settings, thread_id=..., user_id=...)
    # 在 RunnableConfig callbacks= 列表中传入 handler
"""

from agent_framework.observability.callbacks import AgentCallbackHandler
from agent_framework.observability.langfuse_tracer import get_langfuse_handler
from agent_framework.observability.logging import configure_logging

__all__ = ["AgentCallbackHandler", "get_langfuse_handler", "configure_logging"]
