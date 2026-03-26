from __future__ import annotations

import asyncio
import logging
import socket
from typing import Any

import yaml

from agent_framework.config.settings import Settings

logger = logging.getLogger(__name__)


class NacosConfigManager:
    """Nacos 动态配置与服务注册管理器。"""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: Any = None
        self._registered = False

    async def start(self) -> None:
        """拉取初始配置、订阅配置变更并注册服务实例。"""
        if not self._settings.NACOS_ENABLED:
            logger.info("Nacos 已禁用，跳过初始化")
            return

        try:
            import nacos  # type: ignore[import]

            self._client = nacos.NacosClient(
                self._settings.NACOS_SERVER_ADDRESSES,
                namespace=self._settings.NACOS_NAMESPACE,
                username=self._settings.NACOS_USERNAME,
                password=self._settings.NACOS_PASSWORD,
            )

            # 拉取初始配置
            config_str = self._client.get_config(
                self._settings.NACOS_DATA_ID,
                self._settings.NACOS_GROUP,
            )
            if config_str:
                await self._apply_config(config_str)

            # 订阅配置变更
            self._client.add_config_watcher(
                self._settings.NACOS_DATA_ID,
                self._settings.NACOS_GROUP,
                self._on_config_change,
            )

            # 注册服务实例
            host = socket.gethostbyname(socket.gethostname())
            self._client.add_naming_instance(
                self._settings.NACOS_SERVICE_NAME,
                host,
                self._settings.NACOS_SERVICE_PORT,
                metadata={
                    "a2a_url": f"http://{host}:{self._settings.NACOS_SERVICE_PORT}/a2a",
                    "version": self._settings.A2A_AGENT_VERSION,
                },
            )
            self._registered = True
            logger.info(
                "Nacos 初始化完成",
                extra={"service": self._settings.NACOS_SERVICE_NAME, "host": host},
            )
        except ImportError:
            logger.warning("nacos-sdk-python 未安装，Nacos 已禁用")
        except Exception as exc:
            logger.error("Nacos 初始化失败", extra={"error": str(exc)})

    def _on_config_change(self, args: Any) -> None:
        """Nacos 配置变更时触发的回调函数。"""
        config_str = args.get("raw_string", "") if isinstance(args, dict) else str(args)
        # 将配置应用调度为后台任务，避免阻塞 Nacos 回调线程
        asyncio.create_task(self._apply_config(config_str))

    async def _apply_config(self, config_str: str) -> None:
        """解析 YAML 配置并更新 settings 字段。"""
        try:
            config: dict[str, Any] = yaml.safe_load(config_str) or {}
            for key, value in config.items():
                # Nacos 配置键为小写（YAML 约定）；Settings 字段为大写
                upper_key = key.upper()
                if hasattr(self._settings, upper_key):
                    setattr(self._settings, upper_key, value)
            logger.info("Nacos 配置已应用", extra={"keys": list(config.keys())})
        except Exception as exc:
            logger.error("应用 Nacos 配置失败", extra={"error": str(exc)})

    async def get_service_url(self, service_name: str) -> str:
        """通过 Nacos 发现健康的服务实例 URL。"""
        if self._client is None:
            raise RuntimeError("Nacos 客户端未初始化")
        instances = self._client.list_naming_instance(service_name, healthy_only=True)
        if not instances or not instances.get("hosts"):
            raise RuntimeError(f"服务 {service_name} 无健康实例")
        host_info = instances["hosts"][0]
        return f"http://{host_info['ip']}:{host_info['port']}"

    async def deregister(self) -> None:
        """优雅地从 Nacos 注销当前服务实例。"""
        if self._client and self._registered:
            try:
                host = socket.gethostbyname(socket.gethostname())
                self._client.remove_naming_instance(
                    self._settings.NACOS_SERVICE_NAME,
                    host,
                    self._settings.NACOS_SERVICE_PORT,
                )
                logger.info("Nacos 服务注销成功")
            except Exception as exc:
                logger.error("Nacos 注销失败", extra={"error": str(exc)})
