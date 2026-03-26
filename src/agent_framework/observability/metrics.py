"""Prometheus 指标定义。

所有指标遵循 Prometheus 命名约定：
  <namespace>_<name>_<unit>（snake_case，不使用 camelCase）

指标在模块导入时注册。/metrics 端点
（由 prometheus_client 的 WSGI app 或 make_asgi_app() 提供）负责抓取。

标签说明：
  agent_type  — "react" | "plan_execute" | "supervisor"
  status      — "completed" | "error" | "interrupted"
  tool_name   — 已注册的工具名称（如 "tavily_search"）
  provider    — "openai" | "anthropic" | "deepseek"
  token_type  — "prompt" | "completion"
"""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

# 智能体级别指标
agent_invocations_total = Counter(
    "agent_invocations_total",
    "智能体调用总次数",
    ["agent_type", "status"],
)

agent_latency_seconds = Histogram(
    "agent_latency_seconds",
    "智能体调用延迟（秒）",
    ["agent_type"],
)

# 工具级别指标
tool_calls_total = Counter(
    "tool_calls_total",
    "工具调用总次数",
    ["tool_name", "status"],
)

tool_latency_seconds = Histogram(
    "tool_latency_seconds",
    "工具调用延迟（秒）",
    ["tool_name"],
)

# LLM 指标
llm_tokens_total = Counter(
    "llm_tokens_total",
    "LLM 消耗的 token 总数",
    ["provider", "model", "token_type"],
)

llm_requests_total = Counter(
    "llm_requests_total",
    "LLM API 请求总次数",
    ["provider", "model", "status"],
)

# 线程指标
active_threads = Gauge(
    "active_threads",
    "当前活跃的对话线程数",
)
