from __future__ import annotations

import re
from typing import Any


class OptionalAssetParser:
    """Shared EPL-only helper for non-blocking optional assets."""

    asset_group = "optional_assets"

    def classify(self, raw_label: str, context: str = "") -> dict[str, Any]:
        raise NotImplementedError

    def payload(self, optional_asset_type: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        return {
            "optional_asset_type": optional_asset_type,
            "asset_group": self.asset_group,
            "required": False,
            "requires_field_validation": True,
            **(extra or {}),
        }


class CameraParser(OptionalAssetParser):
    asset_group = "security_devices"

    def classify(self, raw_label: str, context: str = "") -> dict[str, Any]:
        hay = f"{raw_label or ''} {context or ''}".upper()
        if "PTZ" in hay:
            subtype = "ptz_camera"
        elif "FIX" in hay or "FIXED" in hay:
            subtype = "fixed_camera"
        elif "RADAR" in hay:
            subtype = "radar_camera"
        elif "CAM" in hay:
            subtype = "security_camera"
        else:
            subtype = "security_device"
        return self.payload(subtype)


class WeatherStationParser(OptionalAssetParser):
    asset_group = "weather_assets"

    def classify(self, raw_label: str, context: str = "") -> dict[str, Any]:
        hay = f"{raw_label or ''} {context or ''}".upper()
        sensors: list[str] = []
        if any(token in hay for token in ("SITE WEATHER STATION", "W.S", " WS", "GMX")):
            subtype = "weather_station"
        elif "POA" in hay or "PYRANOMETER" in hay:
            subtype = "pyranometer"
            sensors.append("pyranometer")
        elif "WIND" in hay:
            subtype = "wind_sensor"
            sensors.append("wind")
        elif "AMBIENT" in hay:
            subtype = "ambient_temperature_sensor"
            sensors.append("ambient_temperature")
        elif "MODULE" in hay or "PT1000" in hay or re.search(r"\bMT\b", hay):
            subtype = "module_temperature_sensor"
            sensors.append("module_temperature")
        else:
            subtype = "weather_sensor"
        if subtype == "weather_station" and not sensors:
            sensors = ["pyranometer", "wind", "ambient_temperature", "module_temperature"]
        return self.payload(subtype, {"sensors": sensors})


CAMERA_PARSER = CameraParser()
WEATHER_STATION_PARSER = WeatherStationParser()
