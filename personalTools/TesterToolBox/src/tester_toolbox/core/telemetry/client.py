import json
import urllib.error
import urllib.request
from typing import List

from tester_toolbox.core.telemetry.errors import TelemetryUploadError

_RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}


def _classify_http_status(status_code: int) -> bool:
    if status_code in _RETRYABLE_STATUS_CODES:
        return True
    if status_code >= 500:
        return True
    return False


class TelemetryClient:
    def __init__(self, api_base_url: str, api_key: str = "", timeout_seconds: float = 10.0):
        self.api_base_url = api_base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def post_batch(self, events: List[dict]) -> dict:
        if not events:
            return {"inserted": 0, "duplicates": 0, "total": 0}

        payload = json.dumps({"events": events}, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            f"{self.api_base_url}/toolbox/events/batch",
            data=payload,
            headers=self._build_headers(),
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                body = response.read().decode("utf-8")
                return json.loads(body) if body else {}
        except urllib.error.HTTPError as exc:
            retryable = _classify_http_status(exc.code)
            message = self._read_http_error_body(exc)
            raise TelemetryUploadError(
                message or f"HTTP {exc.code}",
                retryable=retryable,
                status_code=exc.code,
            ) from exc
        except urllib.error.URLError as exc:
            raise TelemetryUploadError(str(exc.reason or exc), retryable=True) from exc
        except TimeoutError as exc:
            raise TelemetryUploadError("request timeout", retryable=True) from exc
        except OSError as exc:
            raise TelemetryUploadError(str(exc), retryable=True) from exc

    def _read_http_error_body(self, exc: urllib.error.HTTPError) -> str:
        try:
            body = exc.read().decode("utf-8", errors="replace").strip()
        except OSError:
            return ""
        if not body:
            return ""
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            return body[:200]
        if isinstance(parsed, dict):
            detail = parsed.get("detail")
            if detail is not None:
                return str(detail)
        return body[:200]

    def _build_headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-Toolbox-Key"] = self.api_key
        return headers
