from __future__ import annotations

"""默认 Skill 注册表工厂。

将内置 Skill（如订单状态查询）注册到 SkillRegistry，
并在 FastAPI lifespan 中注入 LogisticsOrchestratorAgent。
"""

from agent_framework.agents.logistics.skill_registry import SkillRegistry
from agent_framework.agents.logistics.skills.customer_query import query_customer_info
from agent_framework.agents.logistics.skills.order_query import query_order_status
from agent_framework.agents.logistics.skills.product_query import query_product_info


def build_default_skill_registry() -> SkillRegistry:
    """创建并返回内置 Skill 的注册表。"""
    registry = SkillRegistry()
    registry.add(
        name="query_order_status",
        description="查询订单当前状态与物流信息（需提供订单号）",
        fn=query_order_status,
        examples=["查一下订单 SO-001 的物流状态", "SO-2024-12345 到哪了"],
    )
    registry.add(
        name="query_product_info",
        description="查询商品详情、规格参数、含税单价与库存状态（需提供商品编码/SKU）",
        fn=query_product_info,
        examples=["SKU-1001 的价格是多少", "查一下 SKU-3021 的库存"],
    )
    registry.add(
        name="query_customer_info",
        description="查询客户基本信息、信用等级、授信额度与历史成交（需提供客户编码或名称）",
        fn=query_customer_info,
        examples=["查一下客户 CUS-001 的信用等级", "顺丰科技的授信额度"],
    )
    return registry
