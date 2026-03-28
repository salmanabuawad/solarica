from __future__ import annotations
import requests
from .driver_factory import get_driver
from .repository import upsert_measurement, list_measurements, count_unsynced, mark_synced, set_sync_state, get_sync_state
from .config import settings


def seed_from_driver() -> int:
    driver = get_driver()
    items = driver.fetch_measurements()
    for item in items:
        upsert_measurement(item)
    set_sync_state('import_state', 'completed')
    set_sync_state('last_imported_count', str(len(items)))
    return len(items)


def get_import_status() -> dict:
    return {
        'state': get_sync_state('import_state', 'idle'),
        'lastImportedCount': int(get_sync_state('last_imported_count', '0') or 0),
        'unsyncedCount': count_unsynced(),
    }


def upload_unsynced() -> dict:
    items = [item for item in list_measurements() if item.get('syncStatus') != 'synced']
    if not items:
        return {'uploaded': 0}
    payload = {
        'device': get_driver().fetch_device_info(),
        'measurements': items,
    }
    try:
        response = requests.post(f"{settings.backend_base_url}/api/v1/import/batch", json=payload, timeout=10)
        response.raise_for_status()
        mark_synced([item['id'] for item in items])
        return {'uploaded': len(items)}
    except Exception as exc:
        return {'uploaded': 0, 'error': str(exc)}
