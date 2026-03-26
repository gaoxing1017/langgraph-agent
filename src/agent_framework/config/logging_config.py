from __future__ import annotations

"""structlog 日志配置。

在应用启动时调用一次 configure_logging()（在 FastAPI lifespan 中）。
之后在代码库任意位置使用 structlog.get_logger(__name__) 获取日志器。
生产环境使用 JSON 渲染；开发环境使用带颜色的控制台渲染。
"""

import logging
import sys

import structlog


def configure_logging(log_level: str = "INFO", json_logs: bool = False) -> None:
    """配置 structlog，支持生产环境的可选 JSON 渲染。"""
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if json_logs:
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=shared_processors + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # 抑制噪声较多的第三方日志器
    for noisy in ["httpx", "httpcore", "asyncio"]:
        logging.getLogger(noisy).setLevel(logging.WARNING)
