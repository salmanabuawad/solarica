"""CSV and JSON export helpers."""

from __future__ import annotations

import csv
import io
import json

from .repository import list_measurements

_CSV_COLUMNS = [
    "id", "measuredAt", "customer", "installation", "stringNo",
    "moduleType", "ppkWp", "rsOhm", "rpOhm", "vocV", "iscA",
    "vpmaxV", "ipmaxA", "ffPercent", "irradianceWM2", "moduleTempC",
    "sensorTempC", "irradianceSensorType", "irradianceSensorSerial",
    "importSource", "syncStatus",
]


def export_csv() -> bytes:
    measurements = list_measurements()
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=_CSV_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for m in measurements:
        writer.writerow({k: m.get(k, "") for k in _CSV_COLUMNS})
    return buf.getvalue().encode("utf-8")


def export_json() -> bytes:
    measurements = list_measurements()
    # Exclude rawPayloadJson to keep response compact
    for m in measurements:
        m.pop("rawPayloadJson", None)
    return json.dumps(measurements, indent=2, default=str).encode("utf-8")
