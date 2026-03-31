"""PlanExecuteGraph 流程验证 - SiliconFlow + DeepSeek-V3

用法：
    uv run python scripts/validate_plan_execute.py
"""

from __future__ import annotations

import asyncio
import sys

from langchain_core.messages import HumanMessage

from agent_framework.config.settings import get_settings
from agent_framework.core.context import AgentContext
from agent_framework.graphs.plan_execute_graph import build_plan_execute_graph
from agent_framework.persistence.checkpoint_factory import get_checkpointer


def _config(thread_id: str, settings) -> dict:
    context: AgentContext = {
        "llm_provider": "siliconflow",
        "model_name": settings.DEFAULT_MODEL,
    }
    return {
        "configurable": {
            "thread_id": thread_id,
            "settings": settings,
            "context": context,
        },
        "recursion_limit": 40,
    }


async def run_case(graph, settings, name: str, message: str) -> bool:
    print(f"\n{'='*55}")
    print(f"[案例] {name}")
    print(f"[输入] {message}")

    thread_id = f"pe-validate-{name}"
    cfg = _config(thread_id, settings)

    result = await graph.ainvoke(
        {"messages": [HumanMessage(content=message)], "thread_id": thread_id},
        config=cfg,
    )

    # plan/current_step 不在 OutputState 中，从日志确认执行；
    # 验证以 AI 响应数量和无错误为准。
    messages = result.get("messages", [])
    errors = result.get("errors", [])

    ai_messages = [m for m in messages if hasattr(m, "type") and m.type == "ai"]
    print(f"\n[AI响应数] {len(ai_messages)}（每个计划步骤对应一条）")
    if ai_messages:
        print(f"[最终输出] {ai_messages[-1].content[:400]}")

    if errors:
        print(f"[错误] {errors}")

    ok = len(ai_messages) > 0 and not errors
    print(f"\n[结果] {'PASS' if ok else 'FAIL'}")
    return ok


async def main() -> None:
    settings = get_settings()
    print(f"LLM Provider : {settings.LLM_PROVIDER}")
    print(f"Default Model: {settings.DEFAULT_MODEL}")

    checkpointer = await get_checkpointer(settings)
    graph = build_plan_execute_graph().compile(checkpointer=checkpointer)

    cases = [
        {
            "name": "简单任务分解",
            "message": "写一篇关于人工智能发展历史的简短介绍，包含三个关键时间节点",
        },
        {
            "name": "多步骤推理",
            "message": "计算从1加到100的总和",
        },
    ]

    results = []
    for case in cases:
        ok = await run_case(graph, settings, **case)
        results.append(ok)

    print(f"\n{'='*55}")
    passed = sum(results)
    total = len(results)
    print(f"验证结果: {passed}/{total} PASS")
    if passed < total:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
