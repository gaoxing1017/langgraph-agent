from __future__ import annotations

"""Skill 注册表：将 Python 函数注册为可被 LLM 规划并执行的 Skill。

使用示例：
    from agent_framework.agents.logistics import SkillRegistry

    registry = SkillRegistry()

    @registry.register("calc_shipping_cost", "根据重量和目的地计算运费")
    def calc_shipping(instruction: str) -> str:
        # 解析 instruction，返回结果
        return "运费：¥25"

    # 注入 agent
    agent = LogisticsOrchestratorAgent(settings, skill_registry=registry)
"""

import inspect
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class SkillDef:
    """单个 Skill 的定义。"""
    name: str
    description: str
    fn: Callable[..., Any]                              # (instruction: str) -> str | Awaitable[str]
    examples: list[str] = field(default_factory=list)   # 可选：触发示例，用于 prompt 注入
    required_fields: list[str] = field(default_factory=list)  # 执行前必须具备的字段（供校验提示）
    source: str = "python"                              # "python" | "md"，用于日志/可观测性


class SkillRegistry:
    """Skill 注册表：管理所有已注册的 Skill。"""

    def __init__(self) -> None:
        self._skills: dict[str, SkillDef] = {}

    def register(
        self,
        name: str,
        description: str,
        examples: list[str] | None = None,
    ) -> Callable:
        """装饰器：将函数注册为 Skill。

        Args:
            name:        Skill 唯一标识（英文，无空格），如 "calc_shipping_cost"
            description: 一句话描述，供 LLM 规划时理解（中文）
            examples:    触发示例短语（可选）
        """
        def decorator(fn: Callable) -> Callable:
            self._skills[name] = SkillDef(
                name=name,
                description=description,
                fn=fn,
                examples=examples or [],
            )
            return fn
        return decorator

    def add(self, name: str, description: str, fn: Callable, examples: list[str] | None = None) -> None:
        """非装饰器方式注册 Skill。"""
        self._skills[name] = SkillDef(name=name, description=description, fn=fn, examples=examples or [])

    def get(self, name: str) -> SkillDef | None:
        return self._skills.get(name)

    def list_skills(self) -> list[SkillDef]:
        return list(self._skills.values())

    def is_empty(self) -> bool:
        return len(self._skills) == 0

    def remove(self, name: str) -> bool:
        """删除已注册的 Skill，返回是否存在并被删除。"""
        if name in self._skills:
            del self._skills[name]
            return True
        return False

    def prompt_description(self) -> str:
        """生成注入 LLM 系统提示的 Skill 描述段落。"""
        if not self._skills:
            return ""
        lines = ["- skill_agent        : 执行注册的自定义 Skill（需同时指定 skill_name）"]
        for skill in self._skills.values():
            ex = f"，例如：{'、'.join(skill.examples)}" if skill.examples else ""
            lines.append(f"    · {skill.name} : {skill.description}{ex}")
        return "\n".join(lines)

    async def run(self, name: str, instruction: str, user: str = "orchestrator") -> str:  # noqa: ARG002
        """按名称执行 Skill 并返回结果。"""
        skill = self._skills.get(name)
        if skill is None:
            raise ValueError(f"Skill '{name}' 未注册，已注册：{list(self._skills)}")
        result = skill.fn(instruction)
        if inspect.isawaitable(result):
            result = await result
        return str(result)
