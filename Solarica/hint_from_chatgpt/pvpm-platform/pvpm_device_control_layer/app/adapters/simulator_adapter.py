from __future__ import annotations

from datetime import datetime
from typing import Any

from app.adapters.base import PVPMAdapter
from app.models.schemas import DeviceInfo


class SimulatorAdapter(PVPMAdapter):
    def __init__(self) -> None:
        self._open = False
        self._metadata: dict[str, Any] = {}

    def detect_device(self) -> DeviceInfo:
        return DeviceInfo(
            connected=True,
            transport="simulator",
            port="SIMULATED",
            vendor="OpenAI Demo",
            device_model="PVPM1540X",
            serial_number="03223",
            detail="Simulator adapter active",
        )

    def open(self) -> None:
        self._open = True

    def close(self) -> None:
        self._open = False

    def apply_metadata(self, site_name: str | None, part_name: str | None, module_part_number: str | None) -> bool:
        self._metadata = {
            "site_name": site_name,
            "part_name": part_name,
            "module_part_number": module_part_number,
        }
        return True

    def trigger_measurement(self) -> None:
        if not self._open:
            raise RuntimeError("Adapter is not open")

    def fetch_result(self) -> dict[str, Any]:
        if not self._open:
            raise RuntimeError("Adapter is not open")

        curve = []
        isc = 12.9
        voc = 820.0
        for i in range(0, 95):
            u = round(voc * i / 94, 3)
            ia = round(max(0.0, isc * (1 - (u / voc) ** 3)), 6)
            curve.append({"u_v": u, "i_a": ia, "p_w": round(u * ia, 6)})

        best = max(curve, key=lambda p: p["p_w"])
        return {
            "measured_at": datetime.utcnow().isoformat(),
            "device": {
                "model_serial": "PVPM1540X03223",
                "sensor": "SOZ-03 #18250",
            },
            "metadata_applied_to_device": True,
            "metadata": self._metadata,
            "metrics": {
                "isc": isc,
                "uoc": voc,
                "ipmax": best["i_a"],
                "upmax": best["u_v"],
                "pmax": best["p_w"],
                "fill_factor": round(best["p_w"] / (isc * voc), 6),
                "t_sens": 39.8,
                "t_mod": 45.1,
                "e_eff": 884.0,
            },
            "curve": curve,
            "raw_bytes": b"UIKenn0File_SIMULATED_RESULT",
        }
