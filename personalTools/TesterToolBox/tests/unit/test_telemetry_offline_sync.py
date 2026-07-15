import json
import tempfile
import unittest
from pathlib import Path

from tester_toolbox.core.telemetry.backlog_sync import BacklogSync
from tester_toolbox.core.telemetry.pending_store import PendingEventStore
from tester_toolbox.core.telemetry.payload import build_telemetry_payload, ensure_event_id
from tester_toolbox.core.telemetry.uploaded_index import UploadedEventIndex


class TelemetryOfflineSyncTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _write_log(self, entries):
        log_dir = self.root / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "toolbox-20990101.jsonl"
        lines = [json.dumps(entry, ensure_ascii=False) for entry in entries]
        log_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return log_dir

    def test_pending_store_keeps_events_until_removed(self):
        store = PendingEventStore(self.root / "telemetry_pending.jsonl")
        events = [{"event_id": "e1", "feature": "功能错误分析", "status": "success"}]
        store.append_many(events)

        batch = store.read_batch()
        self.assertEqual(len(batch), 1)
        self.assertEqual(store.count(), 1)

        store.remove_event_ids(["e1"])
        self.assertEqual(store.count(), 0)

    def test_pending_store_deduplicates_by_event_id(self):
        store = PendingEventStore(self.root / "telemetry_pending.jsonl")
        event = {"event_id": "e1", "feature": "功能错误分析", "status": "success"}
        store.append_many([event, event])
        self.assertEqual(store.count(), 1)

    def test_uploaded_index_tracks_successful_events(self):
        index = UploadedEventIndex(self.root / "telemetry_uploaded.jsonl")
        index.mark_uploaded(["e1", "e2"])
        self.assertTrue(index.contains("e1"))
        self.assertTrue(index.contains("e2"))
        index.mark_uploaded(["e2", "e3"])
        self.assertTrue(index.contains("e3"))
        self.assertEqual(len(index.event_ids()), 3)

    def test_backlog_sync_finds_only_missing_events(self):
        log_dir = self._write_log(
            [
                {
                    "event_id": "uploaded-1",
                    "time": "2099-01-01 10:00:00",
                    "hostname": "host-a",
                    "feature": "功能错误分析",
                    "action": "run",
                    "status": "success",
                },
                {
                    "event_id": "pending-1",
                    "time": "2099-01-01 10:01:00",
                    "hostname": "host-a",
                    "feature": "性能日志分析",
                    "action": "run",
                    "status": "failed",
                    "error": "timeout",
                },
                {
                    "event_id": "missing-1",
                    "time": "2099-01-01 10:02:00",
                    "hostname": "host-a",
                    "feature": "文本对比",
                    "action": "run",
                    "status": "success",
                },
                {
                    "time": "2099-01-01 10:03:00",
                    "hostname": "host-a",
                    "feature": "应用启动",
                    "action": "launch",
                    "status": "success",
                },
            ]
        )

        sync = BacklogSync(log_dir)
        missing = sync.collect_missing_events(
            uploaded_ids={"uploaded-1"},
            pending_ids={"pending-1"},
            inflight_ids=set(),
        )
        missing_ids = {item["event_id"] for item in missing}
        self.assertEqual(missing_ids, {"missing-1"})

    def test_payload_builder_preserves_existing_event_id(self):
        entry = {
            "event_id": "fixed-id",
            "time": "2099-01-01 10:00:00",
            "hostname": "host-a",
            "feature": "功能错误分析",
            "action": "run",
            "status": "success",
        }
        payload = build_telemetry_payload(entry)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["event_id"], "fixed-id")

    def test_ensure_event_id_is_stable_for_legacy_logs(self):
        entry = {
            "time": "2099-01-01 10:00:00",
            "hostname": "host-a",
            "feature": "功能错误分析",
            "action": "run",
            "status": "success",
            "duration_ms": 1200,
        }
        first = ensure_event_id(entry)
        second = ensure_event_id(entry)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 32)


if __name__ == "__main__":
    unittest.main()
