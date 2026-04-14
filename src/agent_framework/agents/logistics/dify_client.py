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

import re

import structlog
from agent_framework.agents.logistics.base_client import SubAgentClient
from agent_framework.agents.logistics.state import LogisticsAgentType

logger = structlog.get_logger(__name__)

# ── Mock 信息提取工具 ──────────────────────────────────────────────────────────

def _extract_sku(text: str) -> str:
    """从指令中提取第一个 SKU 编码。"""
    m = re.search(r'(SKU[-\s]?\w+)', text, re.IGNORECASE)
    return m.group(1).upper().replace(" ", "-") if m else "SKU-UNKNOWN"


def _extract_qty(text: str) -> tuple[str, str]:
    """提取数量和单位。优先带单位的数字，其次补充信息中的裸数字。"""
    m = re.search(r'(\d+)\s*(台|件|个|箱|套|批|pcs)', text, re.IGNORECASE)
    if m:
        return m.group(1), m.group(2)
    supp = re.search(r'补充信息[^0-9]*(\d+)', text)
    if supp:
        return supp.group(1), "台"
    return "1", "台"


def _extract_receiver(text: str) -> str:
    """提取收货方名称。"""
    m = re.search(
        r'收货(?:方|人|信息|单位|公司)?[：:\s]*([^\n，,。【]{2,20})',
        text,
    )
    if m:
        return m.group(1).strip()
    m = re.search(r'客户[：:\s]*([^\n，,。【]{2,20})', text)
    return m.group(1).strip() if m else "客户公司"


def _extract_order_no(text: str) -> str:
    """提取订单号。"""
    m = re.search(r'((?:SO|PO|ORD)[- _]?[A-Z0-9\-]{3,20})', text, re.IGNORECASE)
    return m.group(1).upper() if m else "SO-UNKNOWN"


def _gen_order_no(seed: str) -> str:
    """根据指令内容生成确定性订单号（同一指令每次相同）。"""
    h = abs(hash(seed[:60])) % 90000 + 10000
    return f"SO-2024-{h}"


class DifyClient(SubAgentClient):
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
        logger.debug("dify_mock_response", agent_type=self.agent_type, instruction=instruction[:80])
        handlers = {
            LogisticsAgentType.PLACE_ORDER:     self._mock_place_order,
            LogisticsAgentType.REVIEW_ORDER:    self._mock_review_order,
            LogisticsAgentType.ORDER_QUERY:     self._mock_order_query,
            LogisticsAgentType.CUSTOMER_QUERY:  self._mock_customer_query,
            LogisticsAgentType.PRODUCT_QUERY:   self._mock_product_query,
            LogisticsAgentType.EXCEPTION_ORDER: self._mock_exception_order,
        }
        handler = handlers.get(self.agent_type)
        return handler(instruction) if handler else f"[Mock] {self.agent_type} 已处理：{instruction[:60]}"

    # ── 各 Agent mock 实现 ──────────────────────────────────────────────────────

    def _mock_place_order(self, instruction: str) -> str:
        sku      = _extract_sku(instruction)
        qty, unit = _extract_qty(instruction)
        receiver = _extract_receiver(instruction)
        order_no = _gen_order_no(instruction)
        unit_price = 6800
        total = int(qty) * unit_price
        return (
            f"【下单Agent】创建订单成功。\n"
            f"订单号：{order_no}\n"
            f"收货方：{receiver}\n"
            f"商品明细：\n"
            f"  · {sku} × {qty}{unit}，单价 ¥{unit_price:,}，小计 ¥{total:,}\n"
            f"订单金额：¥{total:,}\n"
            f"支付方式：月结\n"
            f"期望交货日期：2024-02-10\n"
            f"订单状态：待审核"
        )

    def _mock_review_order(self, instruction: str) -> str:
        order_no  = _extract_order_no(instruction)
        sku       = _extract_sku(instruction)
        qty, unit = _extract_qty(instruction)
        # SKU 可能来自 inject_predecessor_context 注入；若未注入则用通用描述
        sku_text  = sku if sku != "SKU-UNKNOWN" else "所需商品"
        stock     = int(qty) + 80
        return (
            f"【审单Agent】审核完成。\n"
            f"订单号：{order_no}\n"
            f"审核结论：通过\n"
            f"审核项目：\n"
            f"  ✅ 客户信用等级：A级，历史无欠款\n"
            f"  ✅ 库存核查：{sku_text} 可用库存 {stock}{unit}（需 {qty}{unit}），库存充足\n"
            f"  ✅ 价格核查：报价符合合同价格表\n"
            f"  ✅ 收货地址：已在白名单内，无合规风险\n"
            f"  ✅ 付款条件：月结符合授信额度\n"
            f"审核人：系统自动审核\n"
            f"审核时间：2024-01-20 14:32:05"
        )

    def _mock_order_query(self, instruction: str) -> str:
        order_no  = _extract_order_no(instruction)
        waybill   = f"SF{abs(hash(order_no)) % 9000000000 + 1000000000}"
        # 尝试从 instruction / 历史注入中提取 SKU；无则仅展示物流信息
        sku       = _extract_sku(instruction)
        sku_line  = f"商品明细：{sku}\n" if sku != "SKU-UNKNOWN" else ""
        return (
            f"【订单查询Agent】查询完成。\n"
            f"订单号：{order_no}\n"
            f"订单状态：已出库，运输中\n"
            f"{sku_line}"
            f"承运商：顺丰速运\n"
            f"运单号：{waybill}\n"
            f"当前位置：上海转运中心（2024-01-21 09:20）\n"
            f"预计到货：2024-01-22 18:00"
        )

    def _mock_customer_query(self, instruction: str) -> str:
        # 尝试提取客户名称或编号
        m = re.search(r'(CUS[-\s]?\w+)', instruction, re.IGNORECASE)
        cus_id   = m.group(1).upper() if m else "CUS-10086"
        m2       = re.search(r'客户[：:\s]*([^\n，,。【]{2,20})', instruction)
        cus_name = m2.group(1).strip() if m2 else "上海顺丰科技有限公司"
        return (
            f"【客户查询Agent】查询完成。\n"
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

    def _mock_product_query(self, instruction: str) -> str:
        sku = _extract_sku(instruction)
        # 根据 SKU 编号推断商品名（简单映射，未知则用通用名）
        _SKU_NAMES = {
            "SKU-1001": ("笔记本电脑（商务旗舰款）", "¥6,800", "3C数码"),
            "SKU-2033": ("无线鼠标（人体工学款）",   "¥120",   "3C配件"),
            "SKU-3021": ("液晶显示器（27寸 4K）",    "¥3,200", "3C数码"),
        }
        name, price, category = _SKU_NAMES.get(sku, ("通用商品", "¥999", "其他"))
        return (
            f"【商品查询Agent】查询完成。\n"
            f"商品编号：{sku}\n"
            f"商品名称：{name}\n"
            f"商品分类：{category}\n"
            f"含税单价：{price}\n"
            f"库存状态：上海仓可用 86件，北京仓可用 34件\n"
            f"最小起订量：1件\n"
            f"质保政策：整机1年，上门服务"
        )

    def _mock_exception_order(self, instruction: str) -> str:
        order_no  = _extract_order_no(instruction)
        exc_match = re.search(r'(破损|丢件|延误|短货|质量|异常|货损|缺货)', instruction)
        exc_type  = exc_match.group(1) if exc_match else "异常"
        return (
            f"【异常单处理Agent】处理完成。\n"
            f"关联订单：{order_no}\n"
            f"异常类型：{exc_type}\n"
            f"处理结果：\n"
            f"  1. 已拍照取证并上传理赔系统\n"
            f"  2. 已向承运商发起索赔，预计赔付 5-7 个工作日\n"
            f"  3. 已安排补发，新运单号：SF{abs(hash(order_no)) % 9000000000 + 1000000000}\n"
            f"  4. 订单状态已更新为「补发处理中」\n"
            f"责任方：承运商\n"
            f"跟进人：物流客服-张敏（分机 8821）"
        )
