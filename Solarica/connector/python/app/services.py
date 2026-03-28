"""Business logic: import from driver, sync to backend."""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Optional

import requests

from .config import settings
from .driver_factory import get_driver
from .repository import (
    count_unsynced,
    get_sync_state,
    list_measurements,
    mark_synced,
    set_sync_state,
    upsert_measurement,
)


_import_lock = threading.Lock()


def seed_from_driver() -> int:
    """Pull measurements from the active driver and cache them locally.

    Runs the actual file scan/parse in a background thread so the HTTP
    request returns quickly (avoids gateway timeouts on large folders).
    The caller receives the final count when the thread finishes; if
    another import is already running the call blocks until it completes.
    """
    if not _import_lock.acquire(timeout=0):
        # already running — return current count
        return int(get_sync_state("last_imported_count", "0") or 0)

    try:
        set_sync_state("import_state", "running")
        driver = get_driver()
        items = driver.fetch_measurements()
        count = 0
        for item in items:
            upsert_measurement(item)
            count += 1
        set_sync_state("import_state", "completed")
        set_sync_state("last_imported_count", str(count))
        return count
    except Exception:
        set_sync_state("import_state", "error")
        raise
    finally:
        _import_lock.release()


def get_import_status() -> dict:
    return {
        "state": get_sync_state("import_state", "idle"),
        "lastImportedCount": int(get_sync_state("last_imported_count", "0") or 0),
        "unsyncedCount": count_unsynced(),
        "watcherActive": _watcher_active(),
    }


def upload_unsynced() -> dict:
    """Push locally cached, unsynced measurements to the cloud backend (v1 camelCase format)."""
    unsynced = [m for m in list_measurements() if m.get("syncStatus") != "synced"]
    if not unsynced:
        return {"uploaded": 0}

    device_info = get_driver().detect()
    url = f"{settings.backend_base_url.rstrip('/')}/api/v1/import/batch"

    try:
        response = requests.post(
            url,
            json={
                "device": {
                    "deviceSerial": device_info.get("deviceSerial"),
                    "deviceModel": device_info.get("deviceModel"),
                    "firmwareVersion": device_info.get("firmwareVersion"),
                },
                "measurements": unsynced,
            },
            timeout=15,
        )
        response.raise_for_status()
        mark_synced([m["id"] for m in unsynced])
        return {"uploaded": len(unsynced)}
    except Exception as exc:
        return {"uploaded": 0, "error": str(exc)}


# ---------------------------------------------------------------------------
# Background file watcher
# ---------------------------------------------------------------------------

_watcher_thread: Optional[threading.Thread] = None
_watcher_stop = threading.Event()
_watcher_lock = threading.Lock()


def _watcher_active() -> bool:
    return _watcher_thread is not None and _watcher_thread.is_alive()


def start_watcher(interval_seconds: int = 5) -> bool:
    """Start a background thread that auto-imports new files from the watch folder."""
    global _watcher_thread
    with _watcher_lock:
        if _watcher_active():
            return False  # already running
        _watcher_stop.clear()

        def _loop():
            driver = get_driver()
            folder_attr = getattr(driver, "_watch_folder", None)
            seen_files: dict[str, float] = {}  # path -> mtime

            while not _watcher_stop.is_set():
                try:
                    if folder_attr is not None:
                        folder: Path = driver._watch_folder  # type: ignore[attr-defined]
                        if folder.exists():
                            from .drivers.vendor_export_driver import _ALL_EXTS, _parse_file
                            for path in sorted(folder.iterdir()):
                                if not path.is_file() or path.suffix.lower() not in _ALL_EXTS:
                                    continue
                                mtime = path.stat().st_mtime
                                prev = seen_files.get(str(path))
                                if prev is None or mtime > prev:
                                    seen_files[str(path)] = mtime
                                    try:
                                        items = _parse_file(path)
                                        count = 0
                                        for item in items:
                                            upsert_measurement(item)
                                            count += 1
                                        if count:
                                            set_sync_state("import_state", "completed")
                                            set_sync_state("last_imported_count", str(count))
                                            print(f"[Watcher] Auto-imported {count} record(s) from {path.name}")
                                    except Exception as exc:
                                        print(f"[Watcher] Error parsing {path.name}: {exc}")
                except Exception as exc:
                    print(f"[Watcher] Error: {exc}")

                _watcher_stop.wait(interval_seconds)

        _watcher_thread = threading.Thread(target=_loop, daemon=True, name="file-watcher")
        _watcher_thread.start()
        set_sync_state("import_state", "watching")
        return True


def stop_watcher() -> bool:
    """Stop the background file watcher."""
    global _watcher_thread
    with _watcher_lock:
        if not _watcher_active():
            return False
        _watcher_stop.set()
        _watcher_thread = None  # type: ignore[assignment]
        set_sync_state("import_state", "idle")
        return True
