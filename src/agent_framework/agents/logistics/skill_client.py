from __future__ import annotations

"""SkillClient：将 SkillRegistry 中单个 Skill 包装为 SubAgentClient。"""

from agent_framework.agents.logistics.base_client import SubAgentClient
from agent_framework.agents.logistics.skill_registry import SkillRegistry


class SkillClient(SubAgentClient):
    """将已注册 Skill 封装为 SubAgentClient，供 dispatch_node 统一调用。"""

    def __init__(self, skill_registry: SkillRegistry, skill_name: str) -> None:
        self._registry = skill_registry
        self._skill_name = skill_name

    async def run(self, instruction: str, user: str = "orchestrator") -> str:
        return await self._registry.run(self._skill_name, instruction, user)
