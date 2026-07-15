import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set

from tester_toolbox.config.settings import TOOLBOX_LOG_RETENTION_DAYS
from tester_toolbox.core.telemetry.payload import build_telemetry_payload, ensure_event_id
from tester_toolbox.core.toolbox_log import get_log_dir


class BacklogSync:
    """扫描本地审计日志，补齐未上传且不在 pending 中的事件。"""

    def __init__(self, log_dir: Optional[Path] = None):
        self.log_dir = log_dir or get_log_dir()

    def collect_missing_events(
        self,
        uploaded_ids: Set[str],
        pending_ids: Set[str],
        inflight_ids: Set[str],
    ) -> List[dict]:
        missing: List[dict] = []
        seen: Set[str] = set()

        for path in sorted(self.log_dir.glob("toolbox-*.jsonl")):
            if not self._is_within_retention(path):
                continue
            for entry in self._iter_log_entries(path):
                payload = build_telemetry_payload(entry)
                if payload is None:
                    continue
                event_id = ensure_event_id(entry)
                if event_id in seen:
                    continue
                seen.add(event_id)
                if event_id in uploaded_ids or event_id in pending_ids or event_id in inflight_ids:
                    continue
                missing.append(payload)
        return missing

    def _is_within_retention(self, path: Path) -> bool:
        if TOOLBOX_LOG_RETENTION_DAYS <= 0:
            return True
        date_part = path.stem.replace("toolbox-", "")
        if len(date_part) != 8 or not date_part.isdigit():
            return True
        import time

        cutoff = time.strftime(
            "%Y%m%d",
            time.localtime(time.time() - TOOLBOX_LOG_RETENTION_DAYS * 86400),
        )
        return date_part >= cutoff

    def _iter_log_entries(self, path: Path) -> Iterable[Dict]:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue
