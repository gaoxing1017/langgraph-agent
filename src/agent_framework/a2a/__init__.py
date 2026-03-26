"""A2A（Agent-to-Agent）协议实现。

基于 Google A2A Protocol 规范。使此智能体能够：
  - 通过 AgentCard 广播自身能力（GET /.well-known/agent.json）
  - 接收来自其他智能体的任务委派（POST /a2a）
  - 将任务委派给远程智能体（A2AClient）

服务发现使用 Nacos：每个智能体将其 /a2a 端点 URL
作为元数据注册，以便 A2AClient 按服务名称解析地址。
"""

from agent_framework.a2a.client import A2AClient
from agent_framework.a2a.schemas import AgentCard, Artifact, Task, TaskState
from agent_framework.a2a.task_manager import TaskManager

__all__ = ["A2AClient", "TaskManager", "Task", "TaskState", "Artifact", "AgentCard"]
