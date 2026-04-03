"""
Lightweight in-process event bus.
Events are accumulated in a list and returned with the API response.
No external message broker required.
"""
from __future__ import annotations
from datetime import datetime
from typing import Any


class EventBus:
    def __init__(self) -> None:
        self._events: list[dict[str, Any]] = []

    def emit(self, event_type: str, payload: dict[str, Any]) -> None:
        self._events.append({
            "event": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "payload": payload,
        })

    def events(self) -> list[dict[str, Any]]:
        return list(self._events)
