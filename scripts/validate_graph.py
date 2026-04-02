"""图流程验证脚本 - 使用 SiliconFlow + DeepSeek-V3 跑通 ReAct 图。

用法：
    uv run python scripts/validate_graph.py
"""

from __future__ import annotations

import asyncio
import os
import sys

from dotenv import load_dotenv
load_dotenv()  # 将 .env 写入 os.environ，供工具直接读取

from langchain_core.messages import HumanMessage

import structlog

from agent_framework.config.logging_config import configure_logging
from agent_framework.config.settings import get_settings
from agent_framework.core.context import AgentContext
from agent_framework.graphs.react_graph import ReActGraphBuilder
from agent_framework.persistence.checkpoint_factory import get_checkpointer
from agent_framework.tools.search.tavily_search import tavily_search

logger = structlog.get_logger(__name__)


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


def _config(thread_id: str, settings, tools: list | None = None) -> dict:
    context: AgentContext = {
        "llm_provider": "siliconflow",
        "model_name": settings.DEFAULT_MODEL,
    }
    return {
        "configurable": {
            "thread_id": thread_id,
            "settings": settings,
            "context": context,
            "tools": tools or [],
        },
        "recursion_limit": 10,
    }


async def run_case_single(graph, settings, name: str, message: str, tools: list | None = None) -> bool:
    print(f"\n{'='*50}")
    print(f"[案例] {name}")
    print(f"[输入] {message}")
    thread_id = f"validate-{name}"
    cfg = _config(thread_id, settings, tools=tools)
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


async def run_case_tavily(graph, settings) -> bool:
    name = "Tavily 实网搜索"
    message = "搜索：'LangGraph latest release 2025'，并总结结果。"
    print(f"\n{'='*50}")
    print(f"[案例] {name}")
    print(f"[输入] {message}")
    thread_id = "validate-tavily"
    # Qwen2.5-72B 在 SiliconFlow 上工具调用兼容性优于 DeepSeek-V3
    cfg = _config(thread_id, settings, tools=[tavily_search])
    cfg["configurable"]["context"] = {
        "llm_provider": "siliconflow",
        "model_name": "Qwen/Qwen2.5-72B-Instruct",
    }

    tool_called = False
    tool_result = ""
    final_answer = ""

    async for event in graph.astream_events(
        {"messages": [HumanMessage(content=message)], "thread_id": thread_id},
        config=cfg,
        version="v2",
    ):
        kind = event["event"]
        if kind == "on_tool_start":
            tool_called = True
            inp = event.get("data", {}).get("input", {})
            print(f"[工具调用] {event['name']}({inp})")
            logger.info("Tavily 工具被调用", tool=event["name"], input=inp)
        elif kind == "on_tool_end":
            tool_result = str(event.get("data", {}).get("output", ""))[:200]
            print(f"[工具返回] {tool_result}")
            logger.info("Tavily 工具返回", output=tool_result)
        elif kind == "on_chain_end" and event.get("name") == "LangGraph":
            output = event.get("data", {}).get("output", {})
            msgs = output.get("messages", [])
            if msgs:
                final_answer = msgs[-1].content

    print(f"[最终回答] {final_answer[:300]}")
    ok = tool_called and bool(final_answer)
    print(f"[结果] {'PASS' if ok else 'FAIL'} (工具调用: {'是' if tool_called else '否'})")
    return ok


async def main() -> None:
    settings = get_settings()
    configure_logging(settings.LOG_LEVEL, log_dir=settings.LOG_DIR)
    logger.info("validate_graph 启动", provider=settings.LLM_PROVIDER, model=settings.DEFAULT_MODEL, log_dir=settings.LOG_DIR)

    print(f"LLM Provider : {settings.LLM_PROVIDER}")
    print(f"Default Model: {settings.DEFAULT_MODEL}")
    print(f"Base URL     : {settings.SILICONFLOW_BASE_URL}")
    print(f"Log Dir      : {settings.LOG_DIR}")

    checkpointer = await get_checkpointer(settings)

    # 无工具图（案例 1-2）
    graph = ReActGraphBuilder().build().compile(checkpointer=checkpointer)
    # 带 Tavily 工具图（案例 3）
    graph_with_tools = ReActGraphBuilder(tools=[tavily_search]).build().compile(checkpointer=checkpointer)

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

    # 案例3：Tavily 实网搜索（逐步跟踪）
    results.append(await run_case_tavily(graph_with_tools, settings))

    print(f"\n{'='*50}")
    passed = sum(results)
    total = len(results)
    print(f"验证结果: {passed}/{total} PASS")
    if passed < total:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
