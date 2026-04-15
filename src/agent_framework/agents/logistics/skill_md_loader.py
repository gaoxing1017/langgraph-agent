from __future__ import annotations

"""Skill MD 动态加载器。

支持从 `.md` 文件中动态加载 LLM 驱动的 Skill，无需编写 Python 代码。

文件格式（YAML frontmatter + body）：
    ---
    name: calc_shipping_cost
    description: 根据重量和目的地计算运费报价
    examples:
      - "计算从上海到北京 10kg 的快递费用"
    required_fields:
      - "重量或体积"
      - "目的地"
    ---

    你是专业的物流运费计算助手。...（LLM system prompt）

加载后，Skill 的 fn 是一个 async 闭包，执行时将 body 作为 system prompt、
将 instruction 作为 user message 调用 LLM，返回 LLM 的回答文本。
"""

from pathlib import Path
from typing import Any, Callable

import structlog
import yaml

from agent_framework.agents.logistics.skill_registry import SkillDef, SkillRegistry
from agent_framework.config.settings import Settings

logger = structlog.get_logger(__name__)


# ── LLM Skill 函数工厂 ──────────────────────────────────────────────────────────

def _make_llm_skill_fn(system_prompt: str, skill_name: str, settings: Settings) -> Callable[..., Any]:
    """返回 async 闭包：以 md body 为 system prompt、instruction 为 user message 调用 LLM。

    使用延迟导入，避免循环依赖并支持在非 LLM 测试环境中加载此模块。
    """
    async def _skill_fn(instruction: str) -> str:
        from langchain_core.messages import HumanMessage, SystemMessage  # noqa: PLC0415
        from agent_framework.config.llm_config import get_llm  # noqa: PLC0415

        llm = get_llm(settings)
        logger.debug("skill_md_llm_invoke", skill_name=skill_name, instruction_preview=instruction[:80])
        response = await llm.ainvoke([SystemMessage(content=system_prompt), HumanMessage(content=instruction)])
        return str(response.content)

    return _skill_fn


# ── 加载器主体 ──────────────────────────────────────────────────────────────────

class SkillMDLoader:
    """从 .md 文件动态加载 Skill 到 SkillRegistry。

    实例持有 _path_to_name 映射，用于热重载时处理文件删除事件。
    """

    def __init__(self) -> None:
        self._path_to_name: dict[str, str] = {}  # 绝对路径字符串 → skill name

    def parse_md_file(self, path: Path, settings: Settings) -> SkillDef | None:
        """解析单个 .md 文件，返回 SkillDef；解析失败时记录警告并返回 None。

        文件结构：
          - 以 `---` 开头的 YAML frontmatter（含 name、description 等字段）
          - `---` 之后的正文作为 LLM system prompt
        """
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as exc:
            logger.warning("skill_md_read_error", path=str(path), error=str(exc))
            return None

        # 拆分 frontmatter 与 body
        parts = content.split("---", 2)
        if len(parts) < 3 or parts[0].strip():
            logger.warning("skill_md_no_frontmatter", path=str(path))
            return None

        yaml_str, body = parts[1], parts[2].strip()

        # 解析 YAML frontmatter
        try:
            meta: dict = yaml.safe_load(yaml_str) or {}
        except yaml.YAMLError as exc:
            logger.warning("skill_md_parse_error", path=str(path), error=str(exc))
            return None

        name = meta.get("name", "")
        description = meta.get("description", "")

        if not name or not isinstance(name, str):
            logger.warning("skill_md_missing_name", path=str(path))
            return None
        if not description or not isinstance(description, str):
            logger.warning("skill_md_missing_description", path=str(path), skill=name)
            return None
        if not body:
            logger.warning("skill_md_empty_body", path=str(path), skill=name)
            return None

        examples: list[str] = [str(e) for e in (meta.get("examples") or [])]
        required_fields: list[str] = [str(f) for f in (meta.get("required_fields") or [])]

        return SkillDef(
            name=name,
            description=description,
            fn=_make_llm_skill_fn(body, name, settings),
            examples=examples,
            required_fields=required_fields,
            source="md",
        )

    def load_directory(
        self,
        directory: Path | str,
        registry: SkillRegistry,
        settings: Settings,
    ) -> int:
        """扫描目录中的所有 .md 文件，加载到 registry。

        md skills 会覆盖同名 Python skills。
        返回成功加载的 Skill 数量。
        """
        directory = Path(directory)
        if not directory.is_dir():
            logger.warning("skill_md_dir_not_found", directory=str(directory))
            return 0

        count = 0
        for path in sorted(directory.glob("*.md")):
            skill = self.parse_md_file(path, settings)
            if skill is None:
                continue
            registry.add(
                name=skill.name,
                description=skill.description,
                fn=skill.fn,
                examples=skill.examples,
            )
            # 记录 required_fields 和 source（add() 不支持这些字段，直接写回）
            if skill_def := registry.get(skill.name):
                skill_def.required_fields = skill.required_fields
                skill_def.source = skill.source
            abs_path = str(path.resolve())
            self._path_to_name[abs_path] = skill.name
            logger.info("skill_md_loaded", skill=skill.name, path=str(path))
            count += 1

        return count

    async def watch_directory(
        self,
        directory: Path | str,
        registry: SkillRegistry,
        settings: Settings,
    ) -> None:
        """监听目录中的 .md 文件变化，实时更新 registry（热重载）。

        依赖 `watchfiles` 库（可选）。未安装时记录警告并直接返回。
        作为 asyncio.Task 运行，收到 CancelledError 时自动退出。
        """
        try:
            from watchfiles import Change, awatch  # noqa: PLC0415
        except ImportError:
            logger.warning("skill_md_watchfiles_not_installed", hint="pip install watchfiles")
            return

        directory = Path(directory)
        logger.info("skill_md_watcher_started", directory=str(directory))

        def _is_md(change: Change, path: str) -> bool:  # noqa: ARG001
            return path.endswith(".md")

        async for changes in awatch(str(directory), watch_filter=_is_md):
            for change_type, path_str in changes:
                abs_path = str(Path(path_str).resolve())

                if change_type in (Change.added, Change.modified):
                    skill = self.parse_md_file(Path(path_str), settings)
                    if skill is None:
                        continue
                    registry.add(
                        name=skill.name,
                        description=skill.description,
                        fn=skill.fn,
                        examples=skill.examples,
                    )
                    if skill_def := registry.get(skill.name):
                        skill_def.required_fields = skill.required_fields
                        skill_def.source = skill.source
                    self._path_to_name[abs_path] = skill.name
                    logger.info("skill_md_reloaded", skill=skill.name, path=path_str, change=change_type.name)

                elif change_type == Change.deleted:
                    name = self._path_to_name.pop(abs_path, None)
                    if name and registry.remove(name):
                        logger.info("skill_md_removed", skill=name, path=path_str)
