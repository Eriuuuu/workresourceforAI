import json
import threading
import time
from pathlib import Path
from typing import Iterable, Optional, Set

from tester_toolbox.core.paths import get_runtime_root


class UploadedEventIndex:
    """已成功上传事件的索引，append-only，用于与本地审计日志对账。"""

    def __init__(self, path: Optional[Path] = None):
        self.path = path or (get_runtime_root() / "logs" / "telemetry_uploaded.jsonl")
        self._lock = threading.Lock()
        self._loaded = False
        self._event_ids: Set[str] = set()

    def ensure_loaded(self):
        with self._lock:
            self._load_unlocked()

    def _load_unlocked(self):
        if self._loaded:
            return
        self._event_ids = self._read_ids_unlocked()
        self._loaded = True

    def event_ids(self) -> Set[str]:
        with self._lock:
            self._load_unlocked()
            return set(self._event_ids)

    def contains(self, event_id: str) -> bool:
        with self._lock:
            self._load_unlocked()
            return event_id in self._event_ids

    def mark_uploaded(self, event_ids: Iterable[str]):
        ids = [event_id for event_id in event_ids if event_id]
        if not ids:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        uploaded_at = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        with self._lock:
            self._load_unlocked()
            with self.path.open("a", encoding="utf-8") as file:
                for event_id in ids:
                    if event_id in self._event_ids:
                        continue
                    self._event_ids.add(event_id)
                    record = {"event_id": event_id, "uploaded_at": uploaded_at}
                    file.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")

    def _read_ids_unlocked(self) -> Set[str]:
        if not self.path.exists():
            return set()
        event_ids: Set[str] = set()
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            event_id = record.get("event_id")
            if event_id:
                event_ids.add(event_id)
        return event_ids
