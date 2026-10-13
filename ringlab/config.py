"""Explicit local or HTTPS deployment settings, independent of request headers."""
from __future__ import annotations

import os
import ipaddress
from dataclasses import dataclass
from urllib.parse import urlsplit


@dataclass(frozen=True)
class Settings:
    host: str = "127.0.0.1"
    port: int = 8765
    public_origin: str | None = None
    trusted_proxies: str = "127.0.0.1"
    prediction_workers: int = 1
    prediction_queue: int = 7
    recognition_queue: int = 3
    upload_timeout: float = 20
    task_timeout: float = 45
    prediction_rate: int = 60
    recognition_rate: int = 10
    rate_clients: int = 4096
    cv_threads: int = 2
    connections: int = 32

    def __post_init__(self):
        for name in ("port", "prediction_workers", "prediction_rate", "recognition_rate",
                     "rate_clients", "cv_threads", "connections"):
            if getattr(self, name) < 1:
                raise ValueError(f"{name} 必须大于零")
        if self.port > 65535 or min(self.prediction_queue, self.recognition_queue) < 0:
            raise ValueError("端口或排队上限无效")
        if not (0 < self.upload_timeout <= 300 and 0 < self.task_timeout <= 300):
            raise ValueError("超时必须为 0～300 秒之间的有限数字")
        if self.public_origin:
            parsed = urlsplit(self.public_origin)
            if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
                    or parsed.path or parsed.query or parsed.fragment):
                raise ValueError("正式 Origin 必须为 https://域名[:端口]，不带路径或结尾斜线")
            parsed.port
        if self.host not in ("127.0.0.1", "localhost", "::1") and not self.public_origin:
            raise ValueError("非本机监听需配置 RINGLAB_PUBLIC_ORIGIN 正式 HTTPS 来源")
        if "*" in self.trusted_proxies:
            raise ValueError("代理信任范围不能使用 *，请填写实际代理 IP 或网段")
        for proxy in self.trusted_proxies.split(","):
            if proxy.strip():
                ipaddress.ip_network(proxy.strip(), strict=False)

    @property
    def allowed_origins(self):
        if self.public_origin:
            return {self.public_origin}
        return {f"http://127.0.0.1:{self.port}", f"http://localhost:{self.port}"}

    @classmethod
    def from_env(cls):
        defaults = cls()
        values = {}
        for name in cls.__dataclass_fields__:
            value = os.environ.get("RINGLAB_" + name.upper())
            if value is not None:
                original = getattr(defaults, name)
                if name.endswith("timeout"):
                    values[name] = float(value)
                elif isinstance(original, int):
                    values[name] = int(value)
                else:
                    values[name] = value or None if name == "public_origin" else value
        return cls(**values)
