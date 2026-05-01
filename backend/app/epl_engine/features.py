from __future__ import annotations

from copy import deepcopy
from typing import Any


PROJECT_TYPES = {"fixed_ground", "tracker", "floating", "agro_pv", "hybrid", "unknown"}
CREATABLE_PROJECT_TYPES = {"fixed_ground", "tracker", "floating", "hybrid"}

FEATURES = [
    "physical_rows",
    "string_zones",
    "strings",
    "optimizers",
    "modules",
    "inverters",
    "icb",
    "dccb",
    "bess",
    "pcs",
    "cable_trenches",
    "communication",
    "grounding",
    "trackers",
    "piers",
    "floating_assets",
    "security_devices",
    "cameras",
    "weather_station",
    "weather_sensors",
    "gps_capture",
]


FEATURE_PRESETS: dict[str, dict[str, str]] = {
    "floating": {
        "floating_assets": "required",
        "strings": "required",
        "inverters": "required",
        "icb": "optional",
        "bess": "optional",
        "pcs": "optional",
        "cable_trenches": "optional",
        "communication": "optional",
        "grounding": "optional",
        "security_devices": "optional",
        "cameras": "optional",
        "weather_station": "optional",
        "weather_sensors": "optional",
    },
    "agro_pv": {
        "physical_rows": "required",
        "string_zones": "required",
        "strings": "required",
        "optimizers": "required",
        "modules": "required",
        "inverters": "required",
        "icb": "optional",
        "bess": "optional",
        "pcs": "optional",
        "cable_trenches": "optional",
        "communication": "optional",
        "grounding": "optional",
        "security_devices": "optional",
        "cameras": "optional",
        "weather_station": "optional",
        "weather_sensors": "optional",
    },
    "tracker": {
        "trackers": "required",
        "piers": "required",
        "strings": "required",
        "dccb": "optional",
        "inverters": "required",
        "cable_trenches": "optional",
        "grounding": "optional",
        "weather_station": "optional",
        "weather_sensors": "optional",
    },
    "fixed_ground": {
        "physical_rows": "required",
        "strings": "required",
        "modules": "required",
        "inverters": "required",
        "cable_trenches": "optional",
        "grounding": "optional",
    },
    # Hybrid is deliberately disabled by default. The UI/API can enable the
    # relevant features explicitly once the user decides what the hybrid site
    # contains.
    "hybrid": {},
    "unknown": {},
}


def normalize_project_type(project_type: str | None) -> str:
    value = str(project_type or "unknown").strip().lower()
    return value if value in PROJECT_TYPES else "unknown"


def feature_preset(project_type: str | None) -> dict[str, str]:
    normalized = normalize_project_type(project_type)
    preset = {feature: "disabled" for feature in FEATURES}
    preset.update(FEATURE_PRESETS.get(normalized, {}))
    return preset


def merge_enabled_features(project_type: str | None, enabled_features: dict[str, Any] | None = None) -> dict[str, str]:
    merged = feature_preset(project_type)
    for feature, state in (enabled_features or {}).items():
        if feature not in merged:
            continue
        normalized_state = str(state or "").lower()
        if normalized_state in {"required", "optional", "disabled"}:
            merged[feature] = normalized_state
        elif isinstance(state, bool):
            merged[feature] = "optional" if state else "disabled"
    return merged


def features_by_state(features: dict[str, str]) -> dict[str, dict[str, bool]]:
    return {
        "required": {key: True for key, state in features.items() if state == "required"},
        "optional": {key: True for key, state in features.items() if state == "optional"},
        "disabled": {key: True for key, state in features.items() if state == "disabled"},
    }


def enabled(feature_config: dict[str, str], feature: str) -> bool:
    return feature_config.get(feature) in {"required", "optional"}


def required(feature_config: dict[str, str], feature: str) -> bool:
    return feature_config.get(feature) == "required"


def feature_payload(project_type: str | None, enabled_features: dict[str, Any] | None = None) -> dict[str, Any]:
    normalized = normalize_project_type(project_type)
    merged = merge_enabled_features(normalized, enabled_features)
    return {
        "project_type": normalized,
        "enabled_features": merged,
        "features_by_state": features_by_state(merged),
        "presets": deepcopy(FEATURE_PRESETS),
        "all_features": list(FEATURES),
    }
