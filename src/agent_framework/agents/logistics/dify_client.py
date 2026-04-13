from __future__ import annotations

"""Dify 工作流 API 客户端。

封装对 Dify Workflow Run API 的 HTTP 调用。
DIFY_MOCK_MODE=True 时返回预设的 mock 响应，用于开发/测试阶段。

当前支持的 Agent 类型：
  - place_order_agent      : 下单 Agent
  - review_order_agent     : 审单 Agent
  - exception_order_agent  : 异常单处理 Agent
  - order_query_agent      : 订单信息查询 Agent
  - customer_query_agent   : 客户信息查询 Agent
  - product_query_agent    : 商品信息查询 Agent
"""

import structlog
from agent_framework.agents.logistics.state import LogisticsAgentType

logger = structlog.get_logger(__name__)

# ── Mock 响应库 ────────────────────────────────────────────────────────────────
_MOCK_RESPONSES: dict[LogisticsAgentType, str] = {

    # ── 下单 Agent ─────────────────────────────────────────────────────────────
    LogisticsAgentType.PLACE_ORDER: (
        "【下单Agent】创建订单成功。\n"
        "订单号：SO-2024-20480\n"
        "收货方：上海顺丰科技有限公司\n"
        "收货地址：上海市浦东新区科苑路399号\n"
        "商品明细：\n"
        "  · SKU-1001 笔记本电脑 × 50台，单价 ¥6,800，小计 ¥340,000\n"
        "  · SKU-2033 无线鼠标   × 50个，单价 ¥120，   小计 ¥6,000\n"
        "订单金额：¥346,000\n"
        "支付方式：月结\n"
        "期望交货日期：2024-02-05\n"
        "备注：易碎品，请轻拿轻放\n"
        "订单状态：待审核"
    ),

    # ── 审单 Agent ─────────────────────────────────────────────────────────────
    LogisticsAgentType.REVIEW_ORDER: (
        "【审单Agent】审核完成。\n"
        "订单号：SO-2024-20480\n"
        "审核结论：通过\n"
        "审核项目：\n"
        "  ✅ 客户信用等级：A级，历史欠款为零\n"
        "  ✅ 库存核查：SKU-1001 可用库存 120台（需50台），SKU-2033 可用库存 200个（需50个），库存充足\n"
        "  ✅ 价格核查：报价符合当期合同价格表（2024年Q1版本）\n"
        "  ✅ 收货地址：已在白名单内，无合规风险\n"
        "  ✅ 付款条件：月结符合客户授权信用额度 ¥500,000\n"
        "审核人：系统自动审核\n"
        "审核时间：2024-01-20 14:32:05"
    ),

    # ── 异常单处理 Agent ────────────────────────────────────────────────────────
    LogisticsAgentType.EXCEPTION_ORDER: (
        "【异常单处理Agent】异常处理完成。\n"
        "关联订单：SO-2024-20391\n"
        "异常类型：货物破损（运输途中）\n"
        "异常描述：收货方反馈箱体破损3件，SKU-3021 液晶显示器 × 3台疑似外力冲击受损\n"
        "处理结果：\n"
        "  1. 已拍照取证并上传理赔系统（凭证ID：CLM-20240120-001）\n"
        "  2. 已向顺丰速运发起索赔申请，预计赔付周期 5-7 个工作日\n"
        "  3. 已为客户补发备用机 × 3台，新运单号：SF9988776655\n"
        "  4. 订单异常标记已解除，状态更新为「补发处理中」\n"
        "责任方：承运商（顺丰速运）\n"
        "预计赔付金额：¥10,200\n"
        "跟进人：物流客服-张敏（分机 8821）"
    ),

    # ── 客户信息查询 Agent ──────────────────────────────────────────────────────
    LogisticsAgentType.CUSTOMER_QUERY: (
        "【客户查询Agent】查询完成。\n"
        "客户编号：CUS-10086\n"
        "客户名称：上海顺丰科技有限公司\n"
        "客户类型：企业客户（战略级）\n"
        "信用等级：A级\n"
        "授信额度：¥2,000,000 / 月结\n"
        "已用额度：¥346,000（当月）\n"
        "可用额度：¥1,654,000\n"
        "联系人：李经理 / 138-xxxx-8899 / li@sf-tech.com\n"
        "收货地址（默认）：上海市浦东新区科苑路399号 3号楼仓库\n"
        "近6个月交易记录：\n"
        "  · 成交订单：42笔，总金额 ¥8,760,000\n"
        "  · 退货率：0.8%\n"
        "  · 平均回款周期：28天\n"
        "  · 逾期记录：0次\n"
        "客户标签：大客户、长期合作、信用优良\n"
        "备注：VIP客户，优先处理，专属客服-王芳（分机 6601）"
    ),

    # ── 商品信息查询 Agent ──────────────────────────────────────────────────────
    LogisticsAgentType.PRODUCT_QUERY: (
        "【商品查询Agent】查询完成。\n"
        "商品编号：SKU-1001\n"
        "商品名称：笔记本电脑（商务旗舰款）\n"
        "品牌/型号：联想 ThinkPad X1 Carbon Gen 11\n"
        "商品分类：3C数码 > 笔记本电脑\n"
        "规格参数：\n"
        "  · CPU：Intel Core i7-1365U\n"
        "  · 内存：16GB LPDDR5\n"
        "  · 硬盘：512GB NVMe SSD\n"
        "  · 屏幕：14英寸 2.8K IPS，60Hz\n"
        "  · 重量：1.12kg\n"
        "价格信息：\n"
        "  · 含税单价：¥6,800\n"
        "  · 合同价（A级客户）：¥6,500\n"
        "  · 最小起订量：1台\n"
        "库存状态：\n"
        "  · 上海仓可用：86台\n"
        "  · 北京仓可用：34台\n"
        "  · 在途补货：200台（预计2024-01-25到仓）\n"
        "物流属性：普货，长途可空运，整箱装载数：20台/箱\n"
        "质保政策：整机1年，电池6个月，上门服务\n"
        "备注：热销商品，建议提前备货"
    ),

    # ── 订单信息查询 Agent ──────────────────────────────────────────────────────
    LogisticsAgentType.ORDER_QUERY: (
        "【订单查询Agent】查询完成。\n"
        "订单号：SO-2024-20480\n"
        "订单状态：已出库，运输中\n"
        "创建时间：2024-01-20 10:15:33\n"
        "审核通过：2024-01-20 14:32:05\n"
        "出库时间：2024-01-20 18:00:00\n"
        "商品明细：\n"
        "  · SKU-1001 笔记本电脑 × 50台\n"
        "  · SKU-2033 无线鼠标   × 50个\n"
        "订单金额：¥346,000\n"
        "承运商：顺丰速运\n"
        "运单号：SF1234567890\n"
        "当前位置：上海转运中心（2024-01-21 09:20）\n"
        "预计到货：2024-01-22 12:00\n"
        "收货地址：上海市浦东新区科苑路399号\n"
        "收货联系人：李经理 / 138-xxxx-8899"
    ),
}


class DifyClient:
    """调用 Dify Workflow Run API 的异步客户端。

    Args:
        base_url:   Dify 服务地址（含 /v1 前缀，如 http://dify.example.com/v1）
        api_key:    对应 Dify App 的 API Key
        agent_type: 用于 mock 模式下返回对应预设响应
        mock_mode:  True 时跳过 HTTP 调用，直接返回 mock 响应
        timeout:    单次请求超时秒数
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        agent_type: LogisticsAgentType,
        mock_mode: bool = True,
        timeout: int = 60,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.agent_type = agent_type
        self.mock_mode = mock_mode
        self.timeout = timeout

    async def run(self, instruction: str, user: str = "orchestrator") -> str:
        """执行 Dify 工作流并返回文本结果。

        Args:
            instruction: 传递给 Dify 工作流的自然语言指令
            user:        Dify 侧的用户标识（用于审计）

        Returns:
            工作流输出的文本结果
        """
        if self.mock_mode:
            return self._mock(instruction)

        try:
            import httpx
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    f"{self.base_url}/workflows/run",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "inputs": {"query": instruction},
                        "response_mode": "blocking",
                        "user": user,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                outputs = data.get("data", {}).get("outputs", {})
                result = outputs.get("result") or outputs.get("text") or str(outputs)
                logger.info(
                    "dify_workflow_completed",
                    agent_type=self.agent_type,
                    workflow_run_id=data.get("workflow_run_id"),
                )
                return result
        except Exception as exc:
            logger.error("dify_workflow_failed", agent_type=self.agent_type, error=str(exc))
            raise

    def _mock(self, instruction: str) -> str:
        base = _MOCK_RESPONSES.get(self.agent_type, f"[Mock] {self.agent_type} 已处理指令：{instruction[:60]}")
        logger.debug("dify_mock_response", agent_type=self.agent_type, instruction=instruction[:80])
        return base
