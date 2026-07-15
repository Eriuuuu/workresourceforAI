import json
import threading
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set

from tester_toolbox.core.paths import get_runtime_root


class PendingEventStore:
    """待上传事件队列。仅在确认上传成功后才从文件中删除。"""

    def __init__(self, path: Optional[Path] = None):
        self.path = path or (get_runtime_root() / "logs" / "telemetry_pending.jsonl")
        self._lock = threading.Lock()
        self._migrate_legacy_pending_file()

    def append_many(self, events: List[dict]):
        if not events:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            existing_ids = self._read_event_ids_unlocked()
            lines = []
            for event in events:
                event_id = event.get("event_id")
                if not event_id or event_id in existing_ids:
                    continue
                existing_ids.add(event_id)
                lines.append(json.dumps(event, ensure_ascii=False, separators=(",", ":")))
            if not lines:
                return
            with self.path.open("a", encoding="utf-8") as file:
                for line in lines:
                    file.write(line + "\n")

    def read_batch(self, limit: int = 200) -> List[dict]:
        with self._lock:
            if not self.path.exists():
                return []
            events = self._read_events_unlocked()
            return events[:limit]

    def event_ids(self) -> Set[str]:
        with self._lock:
            return self._read_event_ids_unlocked()

    def count(self) -> int:
        with self._lock:
            return len(self._read_events_unlocked())

    def remove_event_ids(self, event_ids: Iterable[str]):
        remove_ids = {event_id for event_id in event_ids if event_id}
        if not remove_ids:
            return
        with self._lock:
            if not self.path.exists():
                return
            events = self._read_events_unlocked()
            remaining = [event for event in events if event.get("event_id") not in remove_ids]
            if len(remaining) == len(events):
                return
            if remaining:
                content = "\n".join(
                    json.dumps(event, ensure_ascii=False, separators=(",", ":"))
                    for event in remaining
                )
                self.path.write_text(content + "\n", encoding="utf-8")
            else:
                self.path.unlink(missing_ok=True)

    def _read_events_unlocked(self) -> List[dict]:
        if not self.path.exists():
            return []
        events: List[dict] = []
        seen: Set[str] = set()
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            event_id = event.get("event_id")
            if not event_id or event_id in seen:
                continue
            seen.add(event_id)
            events.append(event)
        return events

    def _read_event_ids_unlocked(self) -> Set[str]:
        return {event.get("event_id") for event in self._read_events_unlocked() if event.get("event_id")}

    def _migrate_legacy_pending_file(self):
        legacy = self.path.parent / "pending_events.jsonl"
        if legacy.exists() and not self.path.exists():
            try:
                legacy.rename(self.path)
            except OSError:
                pass
