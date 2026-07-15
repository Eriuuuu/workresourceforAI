import queue
import threading
import time
from typing import List, Optional, Set

from tester_toolbox.core.telemetry.backlog_sync import BacklogSync
from tester_toolbox.core.telemetry.client import TelemetryClient
from tester_toolbox.core.telemetry.config import TelemetrySettings, load_telemetry_settings
from tester_toolbox.core.telemetry.errors import TelemetryUploadError
from tester_toolbox.core.telemetry.network import NetworkMonitor
from tester_toolbox.core.telemetry.payload import build_telemetry_payload
from tester_toolbox.core.telemetry.pending_store import PendingEventStore
from tester_toolbox.core.telemetry.uploaded_index import UploadedEventIndex


class TelemetryUploader:
    def __init__(self):
        self._queue: queue.Queue[dict] = queue.Queue()
        self._pending_store = PendingEventStore()
        self._uploaded_index = UploadedEventIndex()
        self._settings = load_telemetry_settings()
        self._network = NetworkMonitor(
            online_ttl_seconds=self._settings.network_online_ttl_seconds,
            offline_ttl_seconds=self._settings.network_offline_ttl_seconds,
        )
        self._backlog_sync = BacklogSync()
        self._client = TelemetryClient(self._settings.api_base_url, self._settings.api_key)
        self._thread: Optional[threading.Thread] = None
        self._started = False
        self._start_lock = threading.Lock()
        self._inflight_ids: Set[str] = set()
        self._inflight_lock = threading.Lock()

    def enqueue(self, entry: dict):
        if not self._settings.enabled:
            return
        payload = build_telemetry_payload(entry)
        if payload is None:
            return
        self._ensure_started()
        self._queue.put(payload)

    def _ensure_started(self):
        with self._start_lock:
            if self._started:
                return
            self._started = True
            thread = threading.Thread(target=self._worker_loop, name="telemetry-uploader", daemon=True)
            self._thread = thread
            thread.start()

    def _worker_loop(self):
        self._uploaded_index.ensure_loaded()
        self._sync_backlog()

        buffer: List[dict] = []
        last_flush = time.monotonic()
        last_backlog_scan = time.monotonic()

        while True:
            now = time.monotonic()
            online = self._network.is_online(self._settings.api_base_url)

            if now - last_backlog_scan >= self._settings.backlog_scan_interval_seconds:
                self._sync_backlog()
                last_backlog_scan = now

            try:
                timeout = min(0.5, max(0.1, self._settings.flush_interval_seconds))
                buffer.append(self._queue.get(timeout=timeout))
            except queue.Empty:
                pass

            should_flush = bool(buffer) and (
                len(buffer) >= self._settings.batch_size
                or now - last_flush >= self._settings.flush_interval_seconds
            )
            has_pending = self._pending_store.count() > 0
            if should_flush or (online and has_pending):
                if online:
                    self._flush_online(buffer)
                    buffer = []
                else:
                    self._spool_offline(buffer)
                    buffer = []
                last_flush = now

    def _flush_online(self, buffer: List[dict]):
        while True:
            pending_batch = self._pending_store.read_batch(self._settings.batch_size)
            if not pending_batch:
                break
            if not self._upload_events(pending_batch, from_pending=True):
                if buffer:
                    self._pending_store.append_many(buffer)
                return

        if buffer:
            if not self._upload_events(buffer, from_pending=False):
                self._pending_store.append_many(buffer)

    def _spool_offline(self, buffer: List[dict]):
        if buffer:
            self._pending_store.append_many(buffer)

    def _upload_events(self, events: List[dict], from_pending: bool) -> bool:
        event_ids = [event["event_id"] for event in events if event.get("event_id")]
        if not event_ids:
            return True

        self._track_inflight(event_ids)
        try:
            return self._upload_events_with_retry(events, from_pending=from_pending)
        finally:
            self._untrack_inflight(event_ids)

    def _upload_events_with_retry(self, events: List[dict], from_pending: bool) -> bool:
        max_retries = self._settings.upload_max_retries
        base_delay = self._settings.upload_retry_base_seconds
        last_error: Optional[TelemetryUploadError] = None

        for attempt in range(max_retries):
            try:
                self._client.post_batch(events)
                event_ids = [event["event_id"] for event in events if event.get("event_id")]
                self._uploaded_index.mark_uploaded(event_ids)
                self._pending_store.remove_event_ids(event_ids)
                return True
            except TelemetryUploadError as exc:
                last_error = exc
                if not exc.retryable:
                    break
                if attempt < max_retries - 1:
                    time.sleep(base_delay * (2 ** attempt))
                    continue
                break
            except Exception as exc:
                last_error = TelemetryUploadError(str(exc), retryable=True)
                if attempt < max_retries - 1:
                    time.sleep(base_delay * (2 ** attempt))
                    continue
                break

        if last_error is None or last_error.retryable:
            self._network.notify_service_unavailable()
        if not from_pending:
            self._pending_store.append_many(events)
        return False

    def _sync_backlog(self):
        if not self._settings.enabled:
            return

        uploaded_ids = self._uploaded_index.event_ids()
        pending_ids = self._pending_store.event_ids()
        inflight_ids = self._get_inflight_ids()
        missing = self._backlog_sync.collect_missing_events(uploaded_ids, pending_ids, inflight_ids)
        if not missing:
            return

        online = self._network.is_online(self._settings.api_base_url)
        if online:
            for index in range(0, len(missing), self._settings.batch_size):
                batch = missing[index : index + self._settings.batch_size]
                if not self._upload_events(batch, from_pending=False):
                    remaining = missing[index + self._settings.batch_size :]
                    if remaining:
                        self._pending_store.append_many(remaining)
                    break
        else:
            self._pending_store.append_many(missing)

    def _track_inflight(self, event_ids: List[str]):
        with self._inflight_lock:
            self._inflight_ids.update(event_ids)

    def _untrack_inflight(self, event_ids: List[str]):
        with self._inflight_lock:
            self._inflight_ids.difference_update(event_ids)

    def _get_inflight_ids(self) -> Set[str]:
        with self._inflight_lock:
            return set(self._inflight_ids)


telemetry_uploader = TelemetryUploader()
