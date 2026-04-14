from __future__ import annotations

"""商品信息查询 Skill。

从指令中提取 SKU 编码，返回商品详情、价格与库存信息。
"""

import re

_SKU_NAMES: dict[str, tuple[str, str, str]] = {
    "SKU-1001": ("笔记本电脑（商务旗舰款）", "¥6,800", "3C数码"),
    "SKU-2033": ("无线鼠标（人体工学款）",   "¥120",   "3C配件"),
    "SKU-3021": ("液晶显示器（27寸 4K）",    "¥3,200", "3C数码"),
}


def _extract_sku(text: str) -> str:
    m = re.search(r'(SKU[-\s]?\w+)', text, re.IGNORECASE)
    return m.group(1).upper().replace(" ", "-") if m else "SKU-UNKNOWN"


def query_product_info(instruction: str) -> str:
    """查询商品详情、规格参数、价格与库存状态。

    Args:
        instruction: 包含商品编码或名称的自然语言指令

    Returns:
        商品信息摘要文本
    """
    sku = _extract_sku(instruction)
    name, price, category = _SKU_NAMES.get(sku, ("通用商品", "¥999", "其他"))
    return (
        f"【商品查询Skill】查询完成。\n"
        f"商品编号：{sku}\n"
        f"商品名称：{name}\n"
        f"商品分类：{category}\n"
        f"含税单价：{price}\n"
        f"库存状态：上海仓可用 86件，北京仓可用 34件\n"
        f"最小起订量：1件\n"
        f"质保政策：整机1年，上门服务"
    )
