from __future__ import annotations

import re
from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Any


Confidence = str


AGRO_PV_FEATURES: dict[str, Any] = {
    "preset": "agro_pv",
    "required": {
        "physical_rows": True,
        "string_zones": True,
        "strings": True,
        "optimizers": True,
    },
    "optional": {
        "cameras": True,
        "security_devices": True,
        "weather_station": True,
        "weather_sensors": True,
    },
}


def agro_pv_features() -> dict[str, Any]:
    return deepcopy(AGRO_PV_FEATURES)


def optional_feature_enabled(features: dict[str, Any], key: str) -> bool:
    optional = features.get("optional") or {}
    return bool(optional.get(key))


def _source_priority(source_file: str | None) -> int:
    name = (source_file or "").lower()
    if "communication" in name or "_e_30" in name or "site" in name:
        return 0
    if "color" in name or "layout" in name or "electrical" in name or "_e_10" in name or "_e_20" in name:
        return 1
    return 2


def _norm_label(label: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "", (label or "").upper())


def _page_text_has_positioned_label(source_file: str, label: str, assets: list[dict[str, Any]]) -> bool:
    wanted = _norm_label(label)
    for asset in assets:
        if asset.get("source_file") != source_file:
            continue
        existing = _norm_label(str(asset.get("raw_label") or ""))
        if not existing or asset.get("x") is None or asset.get("y") is None:
            continue
        if existing == wanted or wanted in existing or existing in wanted:
            return True
    return False


def _asset_sort_key(asset: dict[str, Any]) -> tuple[Any, ...]:
    confidence_rank = {"high": 0, "medium": 1, "low": 2}.get(str(asset.get("confidence") or ""), 3)
    return (
        _source_priority(asset.get("source_file")),
        confidence_rank,
        str(asset.get("source_file") or ""),
        int(asset.get("page") or 999),
        float(asset.get("y") or 0),
        float(asset.get("x") or 0),
        str(asset.get("raw_label") or ""),
    )


def _next_id(prefix: str, index: int) -> str:
    return f"{prefix}_{index:03d}"


class OptionalAssetParser:
    """Base helper for non-blocking EPL optional assets.

    Subclasses detect assets from positioned PDF text blocks first, then fall
    back to text-only detections when a PDF has searchable text but no usable
    coordinates for a label. Optional assets always carry required=false and
    never generate EPL blocking errors.
    """

    id_prefix = "ASSET"
    group_name = "assets"
    medium_patterns: list[re.Pattern[str]] = []

    def parse(self, text_by_file: dict[str, str], blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        assets = self._parse_positioned(blocks)
        assets.extend(self._parse_text_only(text_by_file, assets))
        return self._assign_ids(sorted(assets, key=_asset_sort_key))

    def _parse_positioned(self, blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        raise NotImplementedError

    def _parse_text_only(
        self,
        text_by_file: dict[str, str],
        positioned_assets: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        assets: list[dict[str, Any]] = []
        for source_file, text in sorted(text_by_file.items(), key=lambda item: (_source_priority(item[0]), item[0])):
            seen_text_only: set[str] = set()
            used_spans: list[tuple[int, int]] = []
            for pattern in self.medium_patterns:
                for match in pattern.finditer(text or ""):
                    span = match.span()
                    if any(max(span[0], used[0]) < min(span[1], used[1]) for used in used_spans):
                        continue
                    used_spans.append(span)
                    raw_label = self._clean_label(match.group(0))
                    key = _norm_label(raw_label)
                    if not raw_label or key in seen_text_only or _page_text_has_positioned_label(source_file, raw_label, positioned_assets):
                        continue
                    seen_text_only.add(key)
                    assets.append(self._make_asset(
                        raw_label=raw_label,
                        source_file=source_file,
                        page=None,
                        x=None,
                        y=None,
                        confidence="medium",
                        text_block=raw_label,
                    ))
        return assets

    def _make_asset(
        self,
        *,
        raw_label: str,
        source_file: str | None,
        page: int | None,
        x: float | None,
        y: float | None,
        confidence: Confidence,
        text_block: str,
    ) -> dict[str, Any]:
        return {
            "id": "",
            "type": self.asset_type(raw_label, text_block),
            "raw_label": raw_label,
            "source_file": source_file,
            "page": page,
            "x": round(float(x), 2) if isinstance(x, (int, float)) else None,
            "y": round(float(y), 2) if isinstance(y, (int, float)) else None,
            "confidence": confidence,
            "required": False,
            "requires_field_validation": True,
        }

    def _assign_ids(self, assets: list[dict[str, Any]]) -> list[dict[str, Any]]:
        for idx, asset in enumerate(assets, start=1):
            asset["id"] = _next_id(self.id_prefix, idx)
        return assets

    def _clean_label(self, label: str) -> str:
        return re.sub(r"\s+", " ", (label or "").strip(" :-_")).strip()

    def asset_type(self, raw_label: str, text_block: str) -> str:
        return self.group_name


class CameraParser(OptionalAssetParser):
    id_prefix = "CAM"
    group_name = "security_camera"

    label_patterns = [
        re.compile(r"\b(?:FIX(?:ED)?\s+CAM(?:ERA)?|FIX\s*CAM)\s*[-_]?\s*\d*\b", re.IGNORECASE),
        re.compile(r"\bPTZ\s*[-_]?\s*\d*\b", re.IGNORECASE),
        re.compile(r"\bCAM(?:ERA)?\s*[-_]?\s*\d*\b", re.IGNORECASE),
        re.compile(r"\bCAB\s*[-_]?\s*\d*\b", re.IGNORECASE),
        re.compile(r"\bRADAR\s*[-_]?\s*\d*\b", re.IGNORECASE),
    ]
    medium_patterns = label_patterns
    low_context_patterns = [
        re.compile(r"\b(?:CCTV|SECURITY\s+CAMERA|SURVEILLANCE)\b", re.IGNORECASE),
    ]

    def _parse_positioned(self, blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        assets: list[dict[str, Any]] = []
        seen_context: set[tuple[str, int, str]] = set()
        for block in sorted(blocks, key=lambda b: (_source_priority(b.get("source_file")), b.get("source_file") or "", b.get("page") or 0)):
            text = str(block.get("text") or "")
            used_spans: list[tuple[int, int]] = []
            for pattern in self.label_patterns:
                for match in pattern.finditer(text):
                    span = match.span()
                    if any(max(span[0], used[0]) < min(span[1], used[1]) for used in used_spans):
                        continue
                    used_spans.append(span)
                    raw_label = self._clean_label(match.group(0))
                    if not raw_label:
                        continue
                    assets.append(self._make_asset(
                        raw_label=raw_label,
                        source_file=block.get("source_file"),
                        page=block.get("page"),
                        x=block.get("x"),
                        y=block.get("y"),
                        confidence="high",
                        text_block=text[:240],
                    ))
            for pattern in self.low_context_patterns:
                if pattern.search(text):
                    key = (str(block.get("source_file") or ""), int(block.get("page") or 0), pattern.pattern)
                    if key in seen_context:
                        continue
                    seen_context.add(key)
                    assets.append(self._make_asset(
                        raw_label=self._clean_label(pattern.search(text).group(0)),  # type: ignore[union-attr]
                        source_file=block.get("source_file"),
                        page=block.get("page"),
                        x=block.get("x"),
                        y=block.get("y"),
                        confidence="low",
                        text_block=text[:240],
                    ))
        return assets

    def asset_type(self, raw_label: str, text_block: str) -> str:
        value = raw_label.upper()
        if "PTZ" in value:
            return "ptz_camera"
        if "FIX" in value or "FIXED" in value:
            return "fixed_camera"
        if "RADAR" in value:
            return "radar_camera"
        return "security_camera"


class WeatherStationParser(OptionalAssetParser):
    id_prefix = "WS"
    group_name = "weather_station"

    label_patterns = [
        re.compile(r"\bSITE\s+WEATHER\s+STATION\b", re.IGNORECASE),
        re.compile(r"\bGMX\s*[-_]?\s*\d*\b", re.IGNORECASE),
        re.compile(r"\bPOA\b", re.IGNORECASE),
        re.compile(r"\bPYRANOMETER\s*[-_]?\s*\d*\b", re.IGNORECASE),
        re.compile(r"\bWIND\s+SENSOR\b", re.IGNORECASE),
        re.compile(r"\bAMBIENT\s+TEMPERATURE(?:\s+SENSOR)?\b", re.IGNORECASE),
        re.compile(r"\bMODULE\s+TEMPERATURE(?:\s+SENSOR)?\b", re.IGNORECASE),
        re.compile(r"\bPT1000\s*[-_]?\s*\d*\b", re.IGNORECASE),
        re.compile(r"\bMT\s*[-_]?\s*\d+\b", re.IGNORECASE),
    ]
    medium_patterns = label_patterns
    low_context_patterns = [
        re.compile(r"\b(?:METEO(?:ROLOGICAL)?\s+STATION|WEATHER\s+MAST)\b", re.IGNORECASE),
    ]

    def parse(self, text_by_file: dict[str, str], blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        assets = super().parse(text_by_file, blocks)
        detected_sensors = sorted({
            self.sensor_name(asset.get("type"))
            for asset in assets
            if self.sensor_name(asset.get("type"))
        })
        for asset in assets:
            asset["sensors"] = detected_sensors if asset.get("type") == "weather_station" else (
                [self.sensor_name(asset.get("type"))] if self.sensor_name(asset.get("type")) else []
            )
        return assets

    def _parse_positioned(self, blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        assets: list[dict[str, Any]] = []
        seen_context: set[tuple[str, int, str]] = set()
        for block in sorted(blocks, key=lambda b: (_source_priority(b.get("source_file")), b.get("source_file") or "", b.get("page") or 0)):
            text = str(block.get("text") or "")
            used_spans: list[tuple[int, int]] = []
            for pattern in self.label_patterns:
                for match in pattern.finditer(text):
                    span = match.span()
                    if any(max(span[0], used[0]) < min(span[1], used[1]) for used in used_spans):
                        continue
                    used_spans.append(span)
                    raw_label = self._clean_label(match.group(0))
                    if not raw_label:
                        continue
                    assets.append(self._make_asset(
                        raw_label=raw_label,
                        source_file=block.get("source_file"),
                        page=block.get("page"),
                        x=block.get("x"),
                        y=block.get("y"),
                        confidence="high",
                        text_block=text[:240],
                    ))
            for pattern in self.low_context_patterns:
                match = pattern.search(text)
                if not match:
                    continue
                key = (str(block.get("source_file") or ""), int(block.get("page") or 0), pattern.pattern)
                if key in seen_context:
                    continue
                seen_context.add(key)
                assets.append(self._make_asset(
                    raw_label=self._clean_label(match.group(0)),
                    source_file=block.get("source_file"),
                    page=block.get("page"),
                    x=block.get("x"),
                    y=block.get("y"),
                    confidence="low",
                    text_block=text[:240],
                ))
        return assets

    def asset_type(self, raw_label: str, text_block: str) -> str:
        value = f"{raw_label} {text_block}".upper()
        if "SITE WEATHER STATION" in value or "GMX" in value or "METEO" in value or "WEATHER MAST" in value:
            return "weather_station"
        if "POA" in value or "PYRANOMETER" in value:
            return "pyranometer"
        if "WIND" in value:
            return "wind_sensor"
        if "AMBIENT" in value:
            return "ambient_temperature_sensor"
        if "MODULE" in value or "PT1000" in value or re.search(r"\bMT\s*[-_]?\s*\d+", value):
            return "module_temperature_sensor"
        return "weather_station"

    @staticmethod
    def sensor_name(asset_type: Any) -> str | None:
        return {
            "pyranometer": "pyranometer",
            "wind_sensor": "wind",
            "ambient_temperature_sensor": "ambient_temperature",
            "module_temperature_sensor": "module_temperature",
        }.get(str(asset_type or ""))


def parse_optional_assets(
    text_by_file: dict[str, str],
    blocks: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    return {
        "security_devices": CameraParser().parse(text_by_file, blocks),
        "weather_assets": WeatherStationParser().parse(text_by_file, blocks),
    }


def build_optional_asset_issues(
    assets: dict[str, list[dict[str, Any]]],
    features: dict[str, Any],
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    security_devices = assets.get("security_devices") or []
    weather_assets = assets.get("weather_assets") or []

    if (optional_feature_enabled(features, "cameras") or optional_feature_enabled(features, "security_devices")) and not security_devices:
        issues.append({
            "severity": "warning",
            "type": "missing_optional_security_devices",
            "message": "No optional camera/security assets were detected in EPL drawings.",
            "blocking": False,
        })

    has_weather_station = any(a.get("type") == "weather_station" for a in weather_assets)
    if optional_feature_enabled(features, "weather_station") and not has_weather_station:
        issues.append({
            "severity": "warning",
            "type": "missing_optional_weather_station",
            "message": "No optional weather station was detected in EPL drawings.",
            "blocking": False,
        })

    for asset in security_devices + weather_assets:
        if asset.get("confidence") == "low":
            issues.append({
                "severity": "warning",
                "type": "low_confidence_optional_asset",
                "asset_id": asset.get("id"),
                "asset_type": asset.get("type"),
                "raw_label": asset.get("raw_label"),
                "source_file": asset.get("source_file"),
                "page": asset.get("page"),
                "blocking": False,
            })

    for group_name, warning_type in (
        ("security_devices", "duplicate_camera_label"),
        ("weather_assets", "duplicate_weather_station_label"),
    ):
        labels = [
            _norm_label(str(a.get("raw_label") or ""))
            for a in assets.get(group_name, [])
            if group_name != "weather_assets" or a.get("type") == "weather_station"
            if a.get("raw_label")
        ]
        for label, count in Counter(labels).items():
            if label and count > 1:
                issues.append({
                    "severity": "warning",
                    "type": warning_type,
                    "label": label,
                    "count": count,
                    "blocking": False,
                })

    return issues


def prepare_optional_asset_map_data(
    assets: dict[str, list[dict[str, Any]]],
    features: dict[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    security_enabled = optional_feature_enabled(features, "cameras") or optional_feature_enabled(features, "security_devices")
    weather_enabled = optional_feature_enabled(features, "weather_station") or optional_feature_enabled(features, "weather_sensors")

    def with_position(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            item
            for item in items
            if isinstance(item.get("x"), (int, float)) and isinstance(item.get("y"), (int, float))
        ]

    return {
        "security_devices": with_position(assets.get("security_devices") or []) if security_enabled else [],
        "weather_assets": with_position(assets.get("weather_assets") or []) if weather_enabled else [],
    }
