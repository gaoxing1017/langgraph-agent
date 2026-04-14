from __future__ import annotations

"""订单状态查询 Skill。

从指令中提取订单号，返回模拟的物流/订单状态信息。
在 DIFY_MOCK_MODE 下直接返回本地构造的结果；
实际环境中可替换为真实 OMS 接口调用。
"""

import re


def _extract_order_no(text: str) -> str:
    m = re.search(r'((?:SO|PO|ORD)[- _]?[A-Z0-9\-]{3,20})', text, re.IGNORECASE)
    return m.group(1).upper() if m else "SO-UNKNOWN"


def _extract_sku(text: str) -> str:
    m = re.search(r'(SKU[-\s]?\w+)', text, re.IGNORECASE)
    return m.group(1).upper().replace(" ", "-") if m else ""


def query_order_status(instruction: str) -> str:
    """查询订单当前状态与物流信息。

    Args:
        instruction: 包含订单号的自然语言指令

    Returns:
        订单状态与物流摘要文本
    """
    order_no = _extract_order_no(instruction)
    waybill  = f"SF{abs(hash(order_no)) % 9000000000 + 1000000000}"
    sku      = _extract_sku(instruction)
    sku_line = f"商品明细：{sku}\n" if sku else ""

    return (
        f"【订单查询Skill】查询完成。\n"
        f"订单号：{order_no}\n"
        f"订单状态：已出库，运输中\n"
        f"{sku_line}"
        f"承运商：顺丰速运\n"
        f"运单号：{waybill}\n"
        f"当前位置：上海转运中心（2024-01-21 09:20）\n"
        f"预计到货：2024-01-22 18:00"
    )
