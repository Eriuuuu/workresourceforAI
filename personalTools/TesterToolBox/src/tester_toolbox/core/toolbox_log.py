import json
import os
import socket
import threading
import time
from pathlib import Path

from tester_toolbox.config.settings import (
    TOOLBOX_LOG_MAX_FIELD_LENGTH,
    TOOLBOX_LOG_MAX_LIST_ITEMS,
    TOOLBOX_LOG_RETENTION_DAYS,
)
from tester_toolbox.core.common import now_text
from tester_toolbox.core.paths import get_runtime_root


def _fallback_log_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home())
    return Path(base) / "personalTools" / "errorLogClassification" / "logs"


def get_log_dir() -> Path:
    preferred = get_runtime_root() / "logs"
    try:
        preferred.mkdir(parents=True, exist_ok=True)
        probe = preferred / ".write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return preferred
    except OSError:
        fallback = _fallback_log_dir()
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


def get_hostname() -> str:
    try:
        return socket.gethostname()
    except OSError:
        return "unknown"


def _truncate_text(text, limit=TOOLBOX_LOG_MAX_FIELD_LENGTH):
    value = str(text)
    if len(value) <= limit:
        return value
    return value[: limit - 3] + "..."


def normalize_value(value, depth=0):
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, Path):
        return _truncate_text(value)
    if isinstance(value, str):
        return _truncate_text(value)
    if depth >= 3:
        return _truncate_text(repr(value))
    if isinstance(value, (list, tuple, set)):
        items = list(value)[:TOOLBOX_LOG_MAX_LIST_ITEMS]
        normalized = [normalize_value(item, depth + 1) for item in items]
        if len(value) > TOOLBOX_LOG_MAX_LIST_ITEMS:
            normalized.append(f"...(+{len(value) - TOOLBOX_LOG_MAX_LIST_ITEMS} more)")
        return normalized
    if isinstance(value, dict):
        normalized = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= TOOLBOX_LOG_MAX_LIST_ITEMS:
                normalized["..."] = f"(+{len(value) - TOOLBOX_LOG_MAX_LIST_ITEMS} more keys)"
                break
            normalized[str(key)] = normalize_value(item, depth + 1)
        return normalized
    return _truncate_text(value)


def summarize_operation_result(result):
    if result is None:
        return None
    if not isinstance(result, dict):
        return normalize_value(result)
    summary = {}
    for key in ("htmlFile", "jsonFile", "summary"):
        if key in result:
            summary[key] = normalize_value(result[key])
    if summary:
        return summary
    return normalize_value(result)


class ToolboxLog:
    _instance = None
    _init_lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._init_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        self.hostname = get_hostname()
        self.log_dir = get_log_dir()
        self._write_lock = threading.Lock()
        self._last_cleanup_day = None

    def _log_file_for_today(self) -> Path:
        return self.log_dir / f"toolbox-{time.strftime('%Y%m%d')}.jsonl"

    def _maybe_cleanup_old_logs(self):
        today = time.strftime("%Y%m%d")
        if self._last_cleanup_day == today:
            return
        self._last_cleanup_day = today
        if TOOLBOX_LOG_RETENTION_DAYS <= 0:
            return
        cutoff = time.strftime("%Y%m%d", time.localtime(time.time() - TOOLBOX_LOG_RETENTION_DAYS * 86400))
        for path in self.log_dir.glob("toolbox-*.jsonl"):
            date_part = path.stem.replace("toolbox-", "")
            if len(date_part) == 8 and date_part.isdigit() and date_part < cutoff:
                try:
                    path.unlink()
                except OSError:
                    pass

    def record(
        self,
        feature,
        status,
        input_data=None,
        result_data=None,
        error=None,
        duration_ms=None,
        source="gui",
        action="run",
    ):
        entry = {
            "time": now_text(),
            "hostname": self.hostname,
            "source": source,
            "feature": feature,
            "action": action,
            "status": status,
            "input": normalize_value(input_data) if input_data is not None else None,
            "result": normalize_value(result_data) if result_data is not None else None,
            "error": _truncate_text(error) if error else None,
            "duration_ms": duration_ms,
        }
        line = json.dumps(entry, ensure_ascii=False, separators=(",", ":"))
        with self._write_lock:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            with self._log_file_for_today().open("a", encoding="utf-8") as file:
                file.write(line + "\n")
        self._maybe_cleanup_old_logs()

    def operation(self, feature, input_data=None, source="gui", action="run"):
        return _OperationRecorder(self, feature, input_data, source, action)


class _OperationRecorder:
    def __init__(self, logger, feature, input_data, source, action):
        self.logger = logger
        self.feature = feature
        self.input_data = input_data
        self.source = source
        self.action = action
        self._started_at = None
        self._finished = False

    def __enter__(self):
        self._started_at = time.monotonic()
        return self

    def __exit__(self, exc_type, exc, _tb):
        if exc_type is None or self._finished:
            return False
        self.failed(str(exc))
        return False

    def _duration_ms(self):
        if self._started_at is None:
            return None
        return int((time.monotonic() - self._started_at) * 1000)

    def success(self, result_data=None):
        if self._finished:
            return
        self._finished = True
        self.logger.record(
            self.feature,
            "success",
            input_data=self.input_data,
            result_data=summarize_operation_result(result_data),
            duration_ms=self._duration_ms(),
            source=self.source,
            action=self.action,
        )

    def failed(self, error):
        if self._finished:
            return
        self._finished = True
        self.logger.record(
            self.feature,
            "failed",
            input_data=self.input_data,
            error=error,
            duration_ms=self._duration_ms(),
            source=self.source,
            action=self.action,
        )

    def cancelled(self, message=""):
        if self._finished:
            return
        self._finished = True
        self.logger.record(
            self.feature,
            "cancelled",
            input_data=self.input_data,
            error=message or None,
            duration_ms=self._duration_ms(),
            source=self.source,
            action=self.action,
        )


toolbox_log = ToolboxLog()
