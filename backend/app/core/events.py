"""In-process event bus.

Modules publish canonical events (see `docs/ARCHITECTURE.md` for the full
list); any subscriber registered at import time reacts synchronously.

Single-process / single-worker only.  When the deployment moves to
multi-worker uvicorn (or jobs in a separate process) swap the
implementation for Redis pub/sub or Postgres `LISTEN`/`NOTIFY` — every
call-site uses `event_bus.publish(...)` / `event_bus.subscribe(...)`, so
the contract stays the same.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Callable

Handler = Callable[[dict[str, Any]], None]


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[str, list[Handler]] = defaultdict(list)

    def subscribe(self, event_name: str, handler: Handler) -> None:
        self._handlers[event_name].append(handler)

    def publish(self, event_name: str, payload: dict[str, Any]) -> None:
        # Copy the handler list so a subscriber can (un)subscribe inside
        # another subscriber without mutating the iteration target.
        for h in list(self._handlers.get(event_name, [])):
            try:
                h(payload)
            except Exception as exc:  # noqa: BLE001 — one bad handler shouldn't sink the bus
                import logging
                logging.getLogger(__name__).warning(
                    "event handler for %s raised: %s", event_name, exc,
                )


event_bus = EventBus()
