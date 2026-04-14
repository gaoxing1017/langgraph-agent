from __future__ import annotations

"""LLM 直接处理子 Agent 客户端。

无需外部服务，直接用 LLM 处理指令并返回结果。
适用于：
  - 开发/测试环境快速验证编排逻辑
  - 简单查询类任务（不需要访问真实数据库）
  - 作为其他 Agent 不可用时的降级兜底

系统提示 (system_prompt) 定义该 Agent 的角色和能力，
用户消息 (instruction) 来自 analyze_and_plan 生成的子任务指令。
"""

import structlog

from agent_framework.agents.logistics.base_client import SubAgentClient

logger = structlog.get_logger(__name__)


class LLMSubAgent(SubAgentClient):
    """用 LLM 直接处理子任务的客户端。

    Args:
        system_prompt: 定义此 Agent 角色的系统提示
        settings:      应用配置（用于获取 LLM provider/model）
        provider:      覆盖 settings 中的 LLM_PROVIDER
        model:         覆盖 settings 中的 DEFAULT_MODEL
        temperature:   LLM temperature，默认 0.0
        name:          Agent 名称，用于日志
    """

    def __init__(
        self,
        system_prompt: str,
        settings=None,
        provider: str | None = None,
        model: str | None = None,
        temperature: float = 0.0,
        name: str = "llm_sub_agent",
    ) -> None:
        self._system_prompt = system_prompt
        self._settings = settings
        self._provider = provider
        self._model = model
        self._temperature = temperature
        self._name = name

    async def run(self, instruction: str, user: str = "orchestrator") -> str:
        from langchain_core.messages import HumanMessage, SystemMessage

        from agent_framework.config.llm_config import get_llm
        from agent_framework.config.settings import get_settings

        settings = self._settings or get_settings()
        llm = get_llm(
            settings,
            provider=self._provider,
            model=self._model,
            temperature=self._temperature,
        )

        logger.info("llm_sub_agent_call", name=self._name, instruction=instruction[:80])
        try:
            response = await llm.ainvoke([
                SystemMessage(content=self._system_prompt),
                HumanMessage(content=instruction),
            ])
            result = str(response.content)
            logger.info("llm_sub_agent_done", name=self._name, result_len=len(result))
            return result
        except Exception as exc:
            logger.error("llm_sub_agent_failed", name=self._name, error=str(exc))
            raise
