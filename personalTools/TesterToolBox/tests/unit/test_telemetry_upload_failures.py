import tempfile
import unittest
from pathlib import Path

from tester_toolbox.core.telemetry.client import _classify_http_status
from tester_toolbox.core.telemetry.config import TelemetrySettings
from tester_toolbox.core.telemetry.errors import TelemetryUploadError
from tester_toolbox.core.telemetry.network import NetworkMonitor
from tester_toolbox.core.telemetry.pending_store import PendingEventStore
from tester_toolbox.core.telemetry.uploader import TelemetryUploader


class TelemetryUploadFailureTests(unittest.TestCase):
    def test_http_503_is_retryable(self):
        self.assertTrue(_classify_http_status(503))

    def test_http_401_is_not_retryable(self):
        self.assertFalse(_classify_http_status(401))

    def test_service_unavailable_marks_network_offline(self):
        monitor = NetworkMonitor(online_ttl_seconds=60, offline_ttl_seconds=60)
        monitor._last_result = True
        monitor._last_checked_at = 1
        monitor._last_api_base_url = "http://localhost:8000/api/v1"
        monitor.notify_service_unavailable()
        self.assertFalse(monitor.is_online("http://localhost:8000/api/v1"))

    def test_upload_retries_then_keeps_pending(self):
        temp_dir = tempfile.TemporaryDirectory()
        root = Path(temp_dir.name)
        try:
            uploader = TelemetryUploader()
            uploader._pending_store = PendingEventStore(root / "telemetry_pending.jsonl")
            uploader._settings = TelemetrySettings(
                enabled=True,
                api_base_url="http://localhost:8000/api/v1",
                api_key="",
                batch_size=20,
                flush_interval_seconds=5,
                backlog_scan_interval_seconds=60,
                network_online_ttl_seconds=15,
                network_offline_ttl_seconds=30,
                upload_max_retries=3,
                upload_retry_base_seconds=0.01,
            )
            events = [
                {
                    "event_id": "retry-1",
                    "client_time": "2099-01-01 10:00:00",
                    "hostname": "host-a",
                    "source": "gui",
                    "feature": "功能错误分析",
                    "feature_id": "error_analysis",
                    "action": "run",
                    "status": "success",
                }
            ]
            calls = {"count": 0}

            def failing_post(_events):
                calls["count"] += 1
                raise TelemetryUploadError("service unavailable", retryable=True, status_code=503)

            uploader._client.post_batch = failing_post
            result = uploader._upload_events(events, from_pending=False)

            self.assertFalse(result)
            self.assertEqual(calls["count"], 3)
            self.assertEqual(uploader._pending_store.count(), 1)
        finally:
            temp_dir.cleanup()

    def test_non_retryable_error_spools_without_extra_retries(self):
        temp_dir = tempfile.TemporaryDirectory()
        root = Path(temp_dir.name)
        try:
            uploader = TelemetryUploader()
            uploader._pending_store = PendingEventStore(root / "telemetry_pending.jsonl")
            uploader._settings = TelemetrySettings(
                enabled=True,
                api_base_url="http://localhost:8000/api/v1",
                api_key="wrong",
                batch_size=20,
                flush_interval_seconds=5,
                backlog_scan_interval_seconds=60,
                network_online_ttl_seconds=15,
                network_offline_ttl_seconds=30,
                upload_max_retries=3,
                upload_retry_base_seconds=0.01,
            )
            events = [
                {
                    "event_id": "auth-1",
                    "client_time": "2099-01-01 10:00:00",
                    "hostname": "host-a",
                    "source": "gui",
                    "feature": "功能错误分析",
                    "feature_id": "error_analysis",
                    "action": "run",
                    "status": "success",
                }
            ]
            calls = {"count": 0}

            def auth_fail(_events):
                calls["count"] += 1
                raise TelemetryUploadError("invalid key", retryable=False, status_code=401)

            uploader._client.post_batch = auth_fail
            result = uploader._upload_events(events, from_pending=False)

            self.assertFalse(result)
            self.assertEqual(calls["count"], 1)
            self.assertEqual(uploader._pending_store.count(), 1)
        finally:
            temp_dir.cleanup()


if __name__ == "__main__":
    unittest.main()
