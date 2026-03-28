"""Generate realistic PVPM 1540X mock measurements for development and demo."""

from __future__ import annotations

import math
import random
from datetime import datetime, timedelta, timezone
from uuid import uuid4


def _iv_curve(voc: float, isc: float, n_points: int = 50) -> list[dict]:
    """Approximate I-V curve using a simple single-diode model."""
    points = []
    for i in range(n_points):
        v = voc * i / (n_points - 1)
        # Simplified: I = Isc * (1 - exp((V - Voc) / (0.026 * 25)))
        exponent = (v - voc) / (0.026 * 25)
        current = max(0.0, isc * (1 - math.exp(exponent)))
        points.append(
            {"pointIndex": i, "voltageV": round(v, 4), "currentA": round(current, 4)}
        )
    return points


def generate_measurements(count: int = 10) -> list[dict]:
    rng = random.Random(42)
    base_time = datetime.now(timezone.utc) - timedelta(days=count)
    measurements = []

    customers = ["Qun Energy", "SolarTech Ltd", "PV Solutions"]
    module_types = ["CS6U-320P", "JAM72S10-380/MR", "LR4-72HBD-430M"]
    sites = ["S.1.1", "S.1.2", "S.2.1", "S.2.2", "S.3.1"]

    for i in range(count):
        voc = rng.uniform(38.0, 42.0)
        isc = rng.uniform(8.8, 9.4)
        ff = rng.uniform(0.74, 0.81)
        vpmax = voc * rng.uniform(0.76, 0.82)
        ipmax = isc * rng.uniform(0.90, 0.95)
        ppk = vpmax * ipmax
        rs = rng.uniform(0.25, 0.55)
        rp = rng.uniform(80.0, 160.0)
        irradiance = rng.uniform(700, 1050)
        tmod = rng.uniform(30.0, 55.0)
        measured_at = base_time + timedelta(hours=i * 4)
        measurement_id = uuid4().hex

        measurements.append(
            {
                "id": measurement_id,
                "externalMeasurementKey": f"PVPM-{measurement_id[:8].upper()}",
                "measuredAt": measured_at.isoformat(),
                "customer": rng.choice(customers),
                "installation": f"Plant-{rng.randint(1, 3):02d}",
                "stringNo": rng.choice(sites),
                "moduleType": rng.choice(module_types),
                "moduleReference": None,
                "modulesSeries": 20,
                "modulesParallel": 1,
                "nominalPowerW": 320.0,
                "ppkWp": round(ppk, 3),
                "rsOhm": round(rs, 4),
                "rpOhm": round(rp, 2),
                "vocV": round(voc, 4),
                "iscA": round(isc, 4),
                "vpmaxV": round(vpmax, 4),
                "ipmaxA": round(ipmax, 4),
                "ffPercent": round(ff * 100, 2),
                "sweepDurationMs": rng.uniform(100.0, 200.0),
                "irradianceWM2": round(irradiance, 1),
                "sensorTempC": round(tmod - 5.0, 1),
                "moduleTempC": round(tmod, 1),
                "irradianceSensorType": "Si-pyranometer",
                "irradianceSensorSerial": f"SEN-{rng.randint(1000, 9999)}",
                "importSource": "mock",
                "syncStatus": "unsynced",
                "notes": None,
                "rawPayloadJson": None,
                "curvePoints": _iv_curve(voc, isc),
            }
        )

    return measurements
