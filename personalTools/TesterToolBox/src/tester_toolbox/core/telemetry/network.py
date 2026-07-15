import json
import threading
import time
from typing import List, Optional, Set
from urllib.parse import urlparse

import urllib.error
import urllib.request


class NetworkMonitor:
    """带缓存的 API 连通性探测，避免断网时反复阻塞上传。"""

    def __init__(
        self,
        online_ttl_seconds: float = 15.0,
        offline_ttl_seconds: float = 30.0,
        timeout_seconds: float = 3.0,
    ):
        self.online_ttl_seconds = online_ttl_seconds
        self.offline_ttl_seconds = offline_ttl_seconds
        self.timeout_seconds = timeout_seconds
        self._lock = threading.Lock()
        self._last_result = False
        self._last_checked_at = 0.0
        self._last_api_base_url = ""

    def is_online(self, api_base_url: str, force: bool = False) -> bool:
        api_base_url = api_base_url.rstrip("/")
        with self._lock:
            if (
                not force
                and self._last_api_base_url == api_base_url
                and self._last_checked_at > 0
            ):
                ttl = (
                    self.online_ttl_seconds
                    if self._last_result
                    else self.offline_ttl_seconds
                )
                if time.monotonic() - self._last_checked_at < ttl:
                    return self._last_result

            result = self._probe(api_base_url)
            self._last_result = result
            self._last_checked_at = time.monotonic()
            self._last_api_base_url = api_base_url
            return result

    def notify_service_unavailable(self):
        """上传失败时标记服务不可用，避免在接口宕机时持续发起请求。"""
        with self._lock:
            self._last_result = False
            self._last_checked_at = time.monotonic()

    def _probe(self, api_base_url: str) -> bool:
        health_url = f"{api_base_url}/health"
        request = urllib.request.Request(health_url, method="GET")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                return 200 <= response.status < 300
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            # 健康检查不可用时，退化为探测主机端口是否可连通。
            return self._probe_socket(api_base_url)

    def _probe_socket(self, api_base_url: str) -> bool:
        parsed = urlparse(api_base_url)
        host = parsed.hostname
        if not host:
            return False
        port = parsed.port
        if port is None:
            port = 443 if parsed.scheme == "https" else 80
        try:
            import socket

            with socket.create_connection((host, port), timeout=self.timeout_seconds):
                return True
        except OSError:
            return False
