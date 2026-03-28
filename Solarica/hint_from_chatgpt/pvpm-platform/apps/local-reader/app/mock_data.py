from __future__ import annotations
from datetime import datetime, timedelta, UTC
import math
import uuid


def build_curve(voc: float, isc: float, points: int = 25) -> list[dict]:
    result = []
    for i in range(points):
        x = voc * i / (points - 1)
        factor = max(0.0, 1 - (x / voc) ** 2.2)
        y = round(isc * factor, 3)
        result.append({"pointIndex": i, "voltageV": round(x, 3), "currentA": y})
    return result


def generate_measurements(count: int = 25) -> list[dict]:
    base = datetime.now(UTC).replace(microsecond=0)
    items = []
    for i in range(count):
        voc = 47.0 + (i % 5) * 0.6
        isc = 11.8 + (i % 7) * 0.18
        vpmax = round(voc * 0.82, 2)
        ipmax = round(isc * 0.93, 2)
        ppk = round(vpmax * ipmax, 2)
        items.append({
            "id": str(uuid.uuid4()),
            "externalMeasurementKey": f"PVPM-M-{1000+i}",
            "measuredAt": (base - timedelta(hours=i * 6)).isoformat(),
            "customer": f"Customer {1 + (i % 4)}",
            "installation": f"Roof {(i % 3) + 1}",
            "stringNo": f"S-{(i % 8) + 1:02d}",
            "moduleType": f"Mono-{540 + (i % 3) * 5}W",
            "moduleReference": "REF-MONO-2026",
            "modulesSeries": 14,
            "modulesParallel": 1 + (i % 2),
            "nominalPowerW": 540.0,
            "ppkWp": ppk,
            "rsOhm": round(0.16 + (i % 5) * 0.01, 3),
            "rpOhm": round(6200 + i * 33.3, 2),
            "vocV": round(voc, 2),
            "iscA": round(isc, 2),
            "vpmaxV": vpmax,
            "ipmaxA": ipmax,
            "ffPercent": round((ppk / (voc * isc)) * 100, 2),
            "sweepDurationMs": 420 + i,
            "irradianceWM2": 820 + (i % 6) * 25,
            "sensorTempC": 37 + (i % 5) * 1.1,
            "moduleTempC": 41 + (i % 5) * 1.5,
            "irradianceSensorType": "Mono reference cell",
            "irradianceSensorSerial": f"RS-{7000+i}",
            "importSource": "mock",
            "syncStatus": "unsynced" if i % 4 else "synced",
            "notes": None,
            "rawPayloadJson": {
                "source": "mock-driver",
                "sequence": i,
                "device": "PVPM 1540X"
            },
            "curvePoints": build_curve(voc, isc)
        })
    return items
