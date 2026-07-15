import hashlib
import uuid
from typing import Any, Dict, Optional

from tester_toolbox.config.settings import TOOL_VERSION
from tester_toolbox.core.telemetry.registry import resolve_feature_config, should_collect


def ensure_event_id(entry: Dict[str, Any]) -> str:
    event_id = entry.get("event_id")
    if event_id:
        return str(event_id)
    fingerprint = "|".join(
        [
            str(entry.get("time", "")),
            str(entry.get("hostname", "")),
            str(entry.get("feature", "")),
            str(entry.get("action", "")),
            str(entry.get("status", "")),
            str(entry.get("duration_ms", "")),
        ]
    )
    return hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()[:32]


def build_telemetry_payload(entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    feature_name = entry.get("feature", "")
    action = entry.get("action", "run")
    if not should_collect(feature_name, action):
        return None

    feature_config = resolve_feature_config(feature_name)
    event_id = ensure_event_id(entry)
    return {
        "event_id": event_id,
        "client_time": entry.get("time"),
        "hostname": entry.get("hostname"),
        "source": entry.get("source", "gui"),
        "feature": feature_config.display_name if feature_config.feature_id != "unknown" else feature_name,
        "feature_id": feature_config.feature_id,
        "action": action,
        "status": entry.get("status"),
        "input": entry.get("input") if feature_config.collect_input else None,
        "result": entry.get("result") if feature_config.collect_result else None,
        "error": entry.get("error"),
        "duration_ms": entry.get("duration_ms"),
        "tool_version": TOOL_VERSION,
    }


def new_event_id() -> str:
    return str(uuid.uuid4())
