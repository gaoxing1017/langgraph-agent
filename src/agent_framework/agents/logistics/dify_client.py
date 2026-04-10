from __future__ import annotations

"""Dify 工作流 API 客户端。

封装对 Dify Workflow Run API 的 HTTP 调用。
DIFY_MOCK_MODE=True 时返回预设的 mock 响应，用于开发/测试阶段。
"""

import structlog
from agent_framework.agents.logistics.state import LogisticsAgentType

logger = structlog.get_logger(__name__)

# Mock 响应库：Key 为 agent_type，Value 为响应模板
_MOCK_RESPONSES: dict[LogisticsAgentType, str] = {
    LogisticsAgentType.ORDER: (
        "【订单Agent响应】查询完成。\n"
        "订单信息：状态=已发货，创建时间=2024-01-10，"
        "收货地址=上海市浦东新区张江高科，预计到货=2024-01-13。"
    ),
    LogisticsAgentType.TRACKING: (
        "【追踪Agent响应】追踪完成。\n"
        "最新位置：上海转运中心（2024-01-11 14:30），"
        "当前状态=运输中，预计送达=2024-01-13 10:00，承运商=顺丰速运，运单号=SF1234567890。"
    ),
    LogisticsAgentType.INVENTORY: (
        "【库存Agent响应】库存查询完成。\n"
        "SKU-001 可用库存=500件，上海仓=300件，北京仓=200件，"
        "安全库存=100件，状态=充足。"
    ),
    LogisticsAgentType.TRANSPORT: (
        "【运输Agent响应】调度完成。\n"
        "已匹配承运商：顺丰速运（评分4.8），预计时效=次日达，"
        "报价=28.5元/单，运力充足，已创建调度单 TMS-20240111-001。"
    ),
    LogisticsAgentType.WAREHOUSE: (
        "【仓储Agent响应】操作完成。\n"
        "入库单 WH-2024-001 已创建，分配库位=A区-03-02，"
        "预计入库时间=2024-01-12 09:00，操作员=系统自动分配。"
    ),
    LogisticsAgentType.SUPPLIER: (
        "【供应商Agent响应】供应商信息查询完成。\n"
        "供应商A：交货期=7天，最近30天准时率=96.5%，待处理PO=3笔，"
        "建议：优先级正常，无异常预警。"
    ),
    LogisticsAgentType.CUSTOMS: (
        "【清关Agent响应】合规检查完成。\n"
        "HS编码=8471.30，关税税率=0%（自贸区协议），"
        "所需文件：商业发票✓ 装箱单✓ 原产地证书⚠待上传，"
        "预计清关时间=1-2个工作日。"
    ),
    LogisticsAgentType.ANALYTICS: (
        "【分析Agent响应】分析完成。\n"
        "本月供应链KPI：准时交付率=94.2%（目标95%，略低），"
        "库存周转率=8.3次/年，平均运输时效=1.8天，"
        "异常预警：华东区承运商延误率上升3.2%，建议增加备用运力。"
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
        base = _MOCK_RESPONSES.get(self.agent_type, f"[Mock] {self.agent_type} 已处理指令")
        logger.debug("dify_mock_response", agent_type=self.agent_type, instruction=instruction[:80])
        return base
