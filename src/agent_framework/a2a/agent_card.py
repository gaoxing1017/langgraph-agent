from __future__ import annotations

from typing import Any

from agent_framework.config.settings import Settings


def build_agent_card(settings: Settings) -> dict[str, Any]:
    """构建描述此智能体能力的 A2A AgentCard JSON。"""
    return {
        "name": settings.A2A_AGENT_NAME,
        "version": settings.A2A_AGENT_VERSION,
        "description": "Production-ready LangGraph AI Agent with ReAct, Plan-Execute, and Supervisor capabilities.",
        "url": settings.A2A_BASE_URL,
        "defaultInputMode": "text",
        "defaultOutputMode": "text",
        "skills": [
            {
                "id": "react_agent",
                "name": "ReAct Agent",
                "description": "General-purpose agent with tool calling capabilities.",
                "inputModes": ["text"],
                "outputModes": ["text"],
            },
            {
                "id": "plan_execute_agent",
                "name": "Plan and Execute Agent",
                "description": "Agent that breaks complex tasks into steps and executes them.",
                "inputModes": ["text"],
                "outputModes": ["text"],
            },
            {
                "id": "research",
                "name": "Web Research",
                "description": "Search the web and summarize findings.",
                "inputModes": ["text"],
                "outputModes": ["text"],
            },
        ],
    }
