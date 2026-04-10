from __future__ import annotations

"""通过 Pydantic-Settings 管理应用配置。

所有配置值均从环境变量或 .env 文件读取。
Nacos 可在运行时通过热重载覆盖配置值（参见 nacos_config.py）。
"""

from typing import Literal
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """集中式应用配置。

    优先级（由高到低）：
      1. 环境变量
      2. .env 文件
      3. Nacos 动态配置（由 NacosConfigManager 在运行时应用）
      4. 此处定义的字段默认值
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 应用基础配置
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = "logs"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000

    # 大语言模型配置
    LLM_PROVIDER: Literal["openai", "anthropic", "deepseek", "zhipu", "siliconflow"] = "openai"
    OPENAI_API_KEY: SecretStr | None = None
    ANTHROPIC_API_KEY: SecretStr | None = None
    DEEPSEEK_API_KEY: SecretStr | None = None
    SILICONFLOW_API_KEY: SecretStr | None = None
    SILICONFLOW_BASE_URL: str = "https://api.siliconflow.cn/v1"
    DEFAULT_MODEL: str = "gpt-4o"
    DEFAULT_TEMPERATURE: float = 0.0
    DEFAULT_MAX_TOKENS: int = 4096

    # 数据库配置
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/agent_framework"
    DB_USER: str = "postgres"
    DB_PASS: str = "postgres"
    DB_HOST: str = "localhost"
    DB_NAME: str = "agent_framework"

    # Langfuse 可观测性配置
    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_SECRET_KEY: SecretStr = SecretStr("")
    LANGFUSE_HOST: str = "http://localhost:3000"
    LANGFUSE_ENABLED: bool = False

    # Nacos 服务注册与配置中心
    NACOS_SERVER_ADDRESSES: str = "127.0.0.1:8848"
    NACOS_NAMESPACE: str = "dev"
    NACOS_USERNAME: str = "nacos"
    NACOS_PASSWORD: str = "nacos"
    NACOS_DATA_ID: str = "agent-framework.yaml"
    NACOS_GROUP: str = "DEFAULT_GROUP"
    NACOS_SERVICE_NAME: str = "agent-framework"
    NACOS_SERVICE_PORT: int = 8000
    NACOS_ENABLED: bool = False

    # A2A 协议配置
    A2A_AGENT_NAME: str = "agent-framework"
    A2A_AGENT_VERSION: str = "1.0.0"
    A2A_BASE_URL: str = "http://localhost:8000"

    # 记忆与会话配置
    CHECKPOINTER_TYPE: Literal["memory", "postgres"] = "memory"
    MAX_CONVERSATION_TURNS: int = 50
    MEMORY_SUMMARIZE_THRESHOLD: int = 20
    MAX_ITERATIONS: int = 20

    # 搜索工具配置
    TAVILY_API_KEY: SecretStr | None = None

    # 安全配置
    SECRET_KEY: str = "change-me-in-production"

    # Dify 集成配置（物流子 Agent）
    # DIFY_MOCK_MODE=True 时使用内置 mock 响应，无需真实 Dify 服务
    DIFY_MOCK_MODE: bool = True
    DIFY_ORDER_AGENT_URL: str = "http://localhost/v1"
    DIFY_ORDER_AGENT_KEY: SecretStr = SecretStr("")
    DIFY_TRACKING_AGENT_URL: str = "http://localhost/v1"
    DIFY_TRACKING_AGENT_KEY: SecretStr = SecretStr("")
    DIFY_INVENTORY_AGENT_URL: str = "http://localhost/v1"
    DIFY_INVENTORY_AGENT_KEY: SecretStr = SecretStr("")
    DIFY_TRANSPORT_AGENT_URL: str = "http://localhost/v1"
    DIFY_TRANSPORT_AGENT_KEY: SecretStr = SecretStr("")
    DIFY_WAREHOUSE_AGENT_URL: str = "http://localhost/v1"
    DIFY_WAREHOUSE_AGENT_KEY: SecretStr = SecretStr("")
    DIFY_SUPPLIER_AGENT_URL: str = "http://localhost/v1"
    DIFY_SUPPLIER_AGENT_KEY: SecretStr = SecretStr("")
    DIFY_CUSTOMS_AGENT_URL: str = "http://localhost/v1"
    DIFY_CUSTOMS_AGENT_KEY: SecretStr = SecretStr("")
    DIFY_ANALYTICS_AGENT_URL: str = "http://localhost/v1"
    DIFY_ANALYTICS_AGENT_KEY: SecretStr = SecretStr("")

    # 协调器配置
    ORCHESTRATOR_MAX_ITERATIONS: int = 10
    ORCHESTRATOR_TASK_TIMEOUT: int = 60        # 单个 Dify 任务超时（秒）
    ORCHESTRATOR_KEEP_LAST_MESSAGES: int = 20  # 消息裁剪保留数（约 10 轮）
    ORCHESTRATOR_TASK_HISTORY_SIZE: int = 20   # task_history 最大保留轮数

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"


def get_settings() -> Settings:
    """创建并返回 Settings 实例（首次调用时读取 .env 文件）。"""
    return Settings()
