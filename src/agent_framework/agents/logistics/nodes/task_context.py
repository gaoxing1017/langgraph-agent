from __future__ import annotations

"""多任务上下文注入与字段校验工具。

职责：
1. inject_predecessor_context() — 从已完成任务的结果中提取关键实体，
   注入到后续 PENDING 任务的 instruction 前缀。
2. validate_task_fields()        — 校验单个任务是否具备执行所需的必要字段，
   同时考虑用户原始消息和同批次前置任务能否提供缺失字段。

这两个函数同时被 validate_tasks_node 和 dispatch_node 使用，
确保"预校验"与"执行前校验"使用统一规则。
"""

import re

from agent_framework.agents.logistics.state import LogisticsAgentType, SubTask, TaskStatus

# ── 字段提取规则 ───────────────────────────────────────────────────────────────
# 定义每种 agent 类型完成后，从其结果中能提取哪些字段（label, regex）
EXTRACTION_RULES: dict[LogisticsAgentType, list[tuple[str, str]]] = {
    LogisticsAgentType.PLACE_ORDER: [
        ("订单号", r"((?:SO|PO|ORD)[- _]?[A-Z0-9\-]{3,20})"),
        ("SKU编码", r"(SKU[-\s]?\w+)"),
    ],
    LogisticsAgentType.REVIEW_ORDER: [
        ("订单号", r"((?:SO|PO|ORD)[- _]?[A-Z0-9\-]{3,20})"),
    ],
    LogisticsAgentType.ORDER_QUERY: [
        ("订单号", r"((?:SO|PO|ORD)[- _]?[A-Z0-9\-]{3,20})"),
        ("运单号", r"((?:SF|YT|JD|TMS)[A-Z0-9\-]{5,20})"),
        ("SKU编码", r"(SKU[-\s]?\w+)"),
    ],
    LogisticsAgentType.EXCEPTION_ORDER: [
        ("订单号", r"((?:SO|PO|ORD)[- _]?[A-Z0-9\-]{3,20})"),
    ],
    LogisticsAgentType.CUSTOMER_QUERY: [
        ("客户编码", r"(CUS[-\s]?\w+)"),
    ],
    LogisticsAgentType.PRODUCT_QUERY: [
        ("SKU编码", r"(SKU[-\s]?\w+)"),
    ],
}

# ── 字段校验规则 ───────────────────────────────────────────────────────────────
# 每种 agent 类型执行前必须具备的字段（pattern 匹配 instruction 或 user_message）
REQUIRED_FIELDS: dict[LogisticsAgentType, list[tuple[str, str]]] = {
    LogisticsAgentType.PLACE_ORDER: [
        (r"SKU[-\s]?\w+|商品|产品", "商品/SKU编码"),
        (r"\d+\s*(?:台|件|个|箱|套|批|单位|pcs)|补充信息[^0-9]*\d+", "商品数量"),
        (r"收货(?:方|人|信息|地址|单位|公司)|收件(?:方|人)|收货|客户|买家", "收货方信息"),
    ],
    LogisticsAgentType.REVIEW_ORDER: [
        (r"(SO|PO|ORD)[- _]?\w{3,}|订单\s*(?:号|编号|ID)", "订单号"),
    ],
    LogisticsAgentType.EXCEPTION_ORDER: [
        (r"(SO|PO|ORD)[- _]?\w{3,}|订单\s*(?:号|编号|ID)", "订单号"),
        (r"破损|丢件|延误|短货|质量|异常|投诉|补发|货损|缺货", "异常描述"),
    ],
    LogisticsAgentType.ORDER_QUERY: [
        (r"(SO|PO|ORD)[- _]?\w{3,}|订单\s*(?:号|编号|ID)", "订单号"),
    ],
    LogisticsAgentType.CUSTOMER_QUERY: [
        (r"CUS[-\s]?\w+|客户\s*(?:编码|ID|号|名称)|买家|客户", "客户编码/名称"),
    ],
    LogisticsAgentType.PRODUCT_QUERY: [
        (r"SKU[-\s]?\w+|商品\s*(?:编码|ID|号)|产品\s*(?:编码|ID)|商品|产品", "商品/SKU编码"),
    ],
}


def inject_predecessor_context(
    task: SubTask,
    all_tasks: list[SubTask],
    current_turn: int,
) -> SubTask:
    """将当前轮次所有已完成任务的关键实体注入到 task.instruction 前缀。

    只注入 task 尚未包含的字段，避免重复。
    返回注入后的新 SubTask（原对象不变）。
    """
    completed = [
        t for t in all_tasks
        if t.turn == current_turn and t.status == TaskStatus.COMPLETED and t.result
    ]
    if not completed:
        return task

    prefixes: list[str] = []
    for done in completed:
        for label, pattern in EXTRACTION_RULES.get(done.agent_type, []):
            matches = re.findall(pattern, done.result, re.IGNORECASE)
            if not matches:
                continue
            value = matches[0]
            # 只在 task instruction 尚未包含该值时注入
            if value.lower() not in task.instruction.lower():
                prefixes.append(f"【{done.agent_type.value} 结果】{label}：{value}")

    if not prefixes:
        return task

    prefix_text = "\n".join(prefixes) + "\n"
    return task.model_copy(update={"instruction": prefix_text + task.instruction})


def validate_task_fields(
    task: SubTask,
    all_tasks: list[SubTask],
    user_message: str = "",
    check_instruction: bool = True,
) -> list[str]:
    """校验 task 是否具备所有必要字段，返回缺失字段名称列表。

    check_instruction=True（默认，dispatch 阶段）：
        校验文本 = task.instruction + user_message
        此时 instruction 中可能已追加了用户补充信息（【补充信息】...）。
    check_instruction=False（validate_tasks 阶段）：
        校验文本 = user_message only，避免 LLM 推断的默认值（如"数量为 1"）误判为已提供。

    若某字段由同批次中排在前面的任务类型负责提供，则跳过该字段（不报缺失）。
    """
    rules = REQUIRED_FIELDS.get(task.agent_type, [])
    if not rules:
        return []

    combined = (task.instruction + "\n" + user_message) if check_instruction else user_message
    task_index = next(
        (i for i, t in enumerate(all_tasks) if t.task_id == task.task_id), -1
    )

    # 前置任务能提供的字段集合：已完成 or 排在前面的 PENDING 任务
    provided_labels: set[str] = set()
    for i, t in enumerate(all_tasks):
        if i >= task_index:
            break
        for label, _ in EXTRACTION_RULES.get(t.agent_type, []):
            provided_labels.add(label)

    missing: list[str] = []
    for pattern, field_name in rules:
        if re.search(pattern, combined, re.IGNORECASE):
            continue  # 文本中已有
        if field_name in provided_labels:
            continue  # 前置任务会提供
        missing.append(field_name)

    return missing
