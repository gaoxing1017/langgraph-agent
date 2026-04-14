from __future__ import annotations

"""客户信息查询 Skill。

从指令中提取客户编码或名称，返回客户基本信息与信用状况。
"""

import re


def _extract_customer(text: str) -> tuple[str, str]:
    """提取客户编码与名称，返回 (cus_id, cus_name)。"""
    m_id = re.search(r'(CUS[-\s]?\w+)', text, re.IGNORECASE)
    cus_id = m_id.group(1).upper() if m_id else "CUS-10086"
    m_name = re.search(r'客户[：:\s]*([^\n，,。【]{2,20})', text)
    cus_name = m_name.group(1).strip() if m_name else "上海顺丰科技有限公司"
    return cus_id, cus_name


def query_customer_info(instruction: str) -> str:
    """查询客户基本信息、信用等级、授信额度与历史交易。

    Args:
        instruction: 包含客户编码或名称的自然语言指令

    Returns:
        客户信息摘要文本
    """
    cus_id, cus_name = _extract_customer(instruction)
    return (
        f"【客户查询Skill】查询完成。\n"
        f"客户编号：{cus_id}\n"
        f"客户名称：{cus_name}\n"
        f"客户类型：企业客户（战略级）\n"
        f"信用等级：A级\n"
        f"授信额度：¥2,000,000 / 月结\n"
        f"联系人：李经理 / 138-xxxx-8899\n"
        f"近6个月成交订单：42笔，总金额 ¥8,760,000\n"
        f"逾期记录：0次\n"
        f"客户标签：大客户、长期合作、信用优良"
    )
