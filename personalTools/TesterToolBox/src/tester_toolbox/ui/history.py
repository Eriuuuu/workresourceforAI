import json
import os
from pathlib import Path

from tester_toolbox.config.settings import DIRECTORY_HISTORY_LIMIT


class HistoryStore:
    def __init__(self):
        base = os.environ.get("APPDATA") or str(Path.home())
        self.path = Path(base) / "personalTools" / "errorLogClassification" / "settings.json"
        self.data = self._load()

    def _load(self):
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _cap(self, limit):
        return limit or DIRECTORY_HISTORY_LIMIT

    def get_list(self, key, limit=None):
        values = self.data.get(key, [])
        if not isinstance(values, list):
            return []
        result = []
        for value in values:
            text = str(value).strip()
            if text and text not in result:
                result.append(text)
        return result[: self._cap(limit)]

    def remember(self, list_key, last_key, path, limit=None):
        normalized = (path or "").strip()
        if not normalized:
            return self.get_list(list_key, limit)
        history = [normalized] + self.get_list(list_key, limit)
        unique = []
        for item in history:
            if item and item not in unique:
                unique.append(item)
        cap = self._cap(limit)
        self.data[list_key] = unique[:cap]
        self.data[last_key] = normalized
        self.save()
        return self.data[list_key]

    def remember_value(self, list_key, value, limit=None):
        normalized = (value or "").strip()
        if not normalized:
            return self.get_list(list_key, limit)
        history = [normalized] + self.get_list(list_key, limit)
        unique = []
        for item in history:
            if item and item not in unique:
                unique.append(item)
        cap = self._cap(limit)
        self.data[list_key] = unique[:cap]
        self.save()
        return self.data[list_key]

    def remember_snapshot(self, list_key, snapshot, limit=None):
        if snapshot is None:
            return self.get_snapshots(list_key, limit)
        history = [snapshot] + self.get_snapshots(list_key, limit)
        unique = []
        seen = set()
        for item in history:
            key = json.dumps(item, ensure_ascii=False, sort_keys=True)
            if key in seen:
                continue
            seen.add(key)
            unique.append(item)
        cap = self._cap(limit)
        self.data[list_key] = unique[:cap]
        self.save()
        return self.data[list_key]

    def get_snapshots(self, key, limit=None):
        values = self.data.get(key, [])
        if not isinstance(values, list):
            return []
        return values[: self._cap(limit)]

    def get_last(self, key):
        return str(self.data.get(key, "") or "").strip()

    def set_object(self, key, value):
        self.data[key] = value
        self.save()

    def get_object(self, key, default=None):
        value = self.data.get(key, default)
        return default if value is None else value
