"""自定义 LangGraph channel 辅助工具。

LangGraph 使用"channel"来决定多个节点更新同一键时如何合并状态。
对于列表/字典字段，务必使用 Annotated[T, reducer]；
裸类型使用最后写入优先（last-write-wins）语义，
在并行分支上会静默丢弃数据。
"""

from __future__ import annotations

import operator
from typing import Annotated

# 重新导出 add_messages，使调用方可以与 AppendList 一同从此处导入
from langgraph.graph.message import add_messages  # noqa: F401

# AppendList：只追加不覆盖的列表 channel。
# 适用于需要跨节点累积值的字段（如 errors、已完成步骤列表）。
# operator.add 将列表拼接而非替换。
AppendList = Annotated[list, operator.add]
