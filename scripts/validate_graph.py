"""图流程验证脚本 - 使用 SiliconFlow + DeepSeek-V3 跑通 ReAct 图。

用法：
    uv run python scripts/validate_graph.py
"""

from __future__ import annotations

import asyncio
import sys

from langchain_core.messages import HumanMessage

from agent_framework.config.settings import get_settings
from agent_framework.core.context import AgentContext
from agent_framework.graphs.react_graph import build_react_graph
from agent_framework.persistence.checkpoint_factory import get_checkpointer


CASES = [
    {
        "name": "简单问答（无工具）",
        "message": "用一句话介绍 LangGraph 是什么",
    },
    {
        "name": "多轮上下文保持",
        "messages": [
            "我的名字是小明",
            "你还记得我叫什么名字吗？",
        ],
    },
]


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
        "recursion_limit": 10,
    }


async def run_case_single(graph, settings, name: str, message: str) -> bool:
    print(f"\n{'='*50}")
    print(f"[案例] {name}")
    print(f"[输入] {message}")
    thread_id = f"validate-{name}"
    cfg = _config(thread_id, settings)
    result = await graph.ainvoke(
        {"messages": [HumanMessage(content=message)], "thread_id": thread_id},
        config=cfg,
    )
    messages = result.get("messages", [])
    answer = messages[-1].content if messages else "(无响应)"
    print(f"[输出] {answer[:300]}")
    ok = bool(answer and answer != "(无响应)")
    print(f"[结果] {'PASS' if ok else 'FAIL'}")
    return ok


async def run_case_multi_turn(graph, settings, name: str, messages: list[str]) -> bool:
    print(f"\n{'='*50}")
    print(f"[案例] {name}")
    thread_id = f"validate-multi-{name}"
    cfg = _config(thread_id, settings)
    last_answer = ""
    for msg in messages:
        print(f"[用户] {msg}")
        result = await graph.ainvoke(
            {"messages": [HumanMessage(content=msg)], "thread_id": thread_id},
            config=cfg,
        )
        msgs = result.get("messages", [])
        last_answer = msgs[-1].content if msgs else "(无响应)"
        print(f"[AI]   {last_answer[:300]}")
    ok = bool(last_answer and last_answer != "(无响应)")
    print(f"[结果] {'PASS' if ok else 'FAIL'}")
    return ok


async def main() -> None:
    settings = get_settings()
    print(f"LLM Provider : {settings.LLM_PROVIDER}")
    print(f"Default Model: {settings.DEFAULT_MODEL}")
    print(f"Base URL     : {settings.SILICONFLOW_BASE_URL}")

    checkpointer = await get_checkpointer(settings)
    graph = build_react_graph().compile(checkpointer=checkpointer)

    results = []

    # 案例1：简单问答
    results.append(await run_case_single(
        graph, settings,
        name=CASES[0]["name"],
        message=CASES[0]["message"],
    ))

    # 案例2：多轮上下文
    results.append(await run_case_multi_turn(
        graph, settings,
        name=CASES[1]["name"],
        messages=CASES[1]["messages"],
    ))

    print(f"\n{'='*50}")
    passed = sum(results)
    total = len(results)
    print(f"验证结果: {passed}/{total} PASS")
    if passed < total:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
