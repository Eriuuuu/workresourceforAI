import configparser
import os
from dataclasses import dataclass
from pathlib import Path

from tester_toolbox.config.settings import (
    TELEMETRY_API_BASE_URL,
    TELEMETRY_API_KEY,
    TELEMETRY_BACKLOG_SCAN_INTERVAL_SECONDS,
    TELEMETRY_BATCH_SIZE,
    TELEMETRY_ENABLED,
    TELEMETRY_FLUSH_INTERVAL_SECONDS,
    TELEMETRY_NETWORK_CHECK_OFFLINE_TTL_SECONDS,
    TELEMETRY_NETWORK_CHECK_ONLINE_TTL_SECONDS,
    TELEMETRY_UPLOAD_MAX_RETRIES,
    TELEMETRY_UPLOAD_RETRY_BASE_SECONDS,
)
from tester_toolbox.core.paths import get_runtime_root


@dataclass(frozen=True)
class TelemetrySettings:
    enabled: bool
    api_base_url: str
    api_key: str
    batch_size: int
    flush_interval_seconds: float
    backlog_scan_interval_seconds: float
    network_online_ttl_seconds: float
    network_offline_ttl_seconds: float
    upload_max_retries: int
    upload_retry_base_seconds: float


def _load_ini_settings() -> dict:
    candidates = [
        get_runtime_root() / "telemetry.ini",
        Path(os.environ.get("APPDATA", "")) / "personalTools" / "TesterToolBox" / "telemetry.ini",
    ]
    for path in candidates:
        if not path.exists():
            continue
        parser = configparser.ConfigParser()
        parser.read(path, encoding="utf-8")
        if not parser.has_section("telemetry"):
            continue
        section = parser["telemetry"]
        return {
            "enabled": section.get("enabled"),
            "api_base_url": section.get("api_base_url"),
            "api_key": section.get("api_key"),
            "batch_size": section.get("batch_size"),
            "flush_interval_seconds": section.get("flush_interval_seconds"),
            "backlog_scan_interval_seconds": section.get("backlog_scan_interval_seconds"),
            "network_online_ttl_seconds": section.get("network_online_ttl_seconds"),
            "network_offline_ttl_seconds": section.get("network_offline_ttl_seconds"),
            "upload_max_retries": section.get("upload_max_retries"),
            "upload_retry_base_seconds": section.get("upload_retry_base_seconds"),
        }
    return {}


def _as_bool(value, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _as_int(value, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value, default: float) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def load_telemetry_settings() -> TelemetrySettings:
    ini_values = _load_ini_settings()
    env_enabled = os.environ.get("TESTER_TOOLBOX_TELEMETRY_ENABLED")
    env_api_base_url = os.environ.get("TESTER_TOOLBOX_API_URL")
    env_api_key = os.environ.get("TESTER_TOOLBOX_API_KEY")

    enabled = _as_bool(
        env_enabled if env_enabled is not None else ini_values.get("enabled"),
        TELEMETRY_ENABLED,
    )
    api_base_url = (
        env_api_base_url
        or ini_values.get("api_base_url")
        or TELEMETRY_API_BASE_URL
    ).rstrip("/")
    api_key = env_api_key or ini_values.get("api_key") or TELEMETRY_API_KEY
    batch_size = _as_int(ini_values.get("batch_size"), TELEMETRY_BATCH_SIZE)
    flush_interval_seconds = _as_float(
        ini_values.get("flush_interval_seconds"),
        TELEMETRY_FLUSH_INTERVAL_SECONDS,
    )
    backlog_scan_interval_seconds = _as_float(
        ini_values.get("backlog_scan_interval_seconds"),
        TELEMETRY_BACKLOG_SCAN_INTERVAL_SECONDS,
    )
    network_online_ttl_seconds = _as_float(
        ini_values.get("network_online_ttl_seconds"),
        TELEMETRY_NETWORK_CHECK_ONLINE_TTL_SECONDS,
    )
    network_offline_ttl_seconds = _as_float(
        ini_values.get("network_offline_ttl_seconds"),
        TELEMETRY_NETWORK_CHECK_OFFLINE_TTL_SECONDS,
    )
    upload_max_retries = _as_int(ini_values.get("upload_max_retries"), TELEMETRY_UPLOAD_MAX_RETRIES)
    upload_retry_base_seconds = _as_float(
        ini_values.get("upload_retry_base_seconds"),
        TELEMETRY_UPLOAD_RETRY_BASE_SECONDS,
    )
    return TelemetrySettings(
        enabled=enabled,
        api_base_url=api_base_url,
        api_key=api_key,
        batch_size=max(1, batch_size),
        flush_interval_seconds=max(1.0, flush_interval_seconds),
        backlog_scan_interval_seconds=max(10.0, backlog_scan_interval_seconds),
        network_online_ttl_seconds=max(5.0, network_online_ttl_seconds),
        network_offline_ttl_seconds=max(5.0, network_offline_ttl_seconds),
        upload_max_retries=max(1, upload_max_retries),
        upload_retry_base_seconds=max(0.2, upload_retry_base_seconds),
    )
