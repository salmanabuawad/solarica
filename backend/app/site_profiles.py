from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path


DEFAULT_PROFILE = {
    "name": "default",
    "construction": {
        "keywords": [
            "site plan",
            "overall layout",
            "general arrangement",
            "electrical cable plan",
            "color map",
        ],
        "candidate_pages": list(range(8)),
        "fallback_pages": [0, 1],
        "zoom": 2.2,
    },
    "ramming": {
        "keywords": [
            "ramming",
            "piering",
            "piering plan",
            "pile plan",
            "foundation plan",
        ],
        "candidate_pages": list(range(6)),
        "fallback_pages": [0],
        "zoom": 2.8,
    },
    "overlay": {
        "keywords": [
            "color map",
            "block",
            "block plan",
            "color",
        ],
        "candidate_pages": [0],
        "fallback_pages": [0],
        "zoom": 2.2,
    },
    "heuristics": {
        "blocks": {
            "color_ranges": {
                "red": [((0, 90, 90), (12, 255, 255)), ((170, 90, 90), (179, 255, 255))],
                "green": [((35, 60, 60), (90, 255, 255))],
                "blue": [((90, 60, 60), (135, 255, 255))],
                "yellow": [((18, 80, 80), (38, 255, 255))],
                "pink": [((140, 50, 80), (170, 255, 255))],
            },
            "close_kernel": [3, 3],
            "close_iterations": 2,
            "contour_area_min": 800,
            "polygon_area_min": 1000,
            "approx_epsilon_ratio": 0.0025,
            "row_bucket_height": 180,
            "sheet_base": 200,
            "sheet_cap": 18,
        },
        "trackers": {
            "binary_threshold": 205,
            "open_kernel": [3, 35],
            "dilate_kernel": [3, 11],
            "fragment_min_height": 120,
            "fragment_max_width": 70,
            "cluster_eps": 38,
            "cluster_min_samples": 2,
            "bbox_padding": 18,
            "tracker_min_height": 160,
        },
        "piers": {
            "primary_color_ranges": [((0, 80, 80), (12, 255, 255)), ((170, 80, 80), (179, 255, 255))],
            "primary_open_kernel": [3, 3],
            "primary_dilate_kernel": [5, 5],
            "primary_area_min": 20,
            "primary_area_max": 400,
            "fallback_threshold": 180,
            "fallback_open_kernel": [2, 5],
            "fallback_area_min": 8,
            "fallback_area_max": 160,
            "fallback_min_height": 5,
            "fallback_max_width": 20,
            "min_points_before_fallback": 3,
            "merge_gap": 8,
        },
        "vector": {
            "cell_size": 12.0,
            "anchor_max_rings": 3,
            "axis_min_distance": 5.0,
            "axis_max_distance": 30.0,
            "bbox_padding": 5.0,
        },
    },
}


BUILTIN_PROFILES = {
    "ashalim3": {
        "match_terms": ["ashalim", "nextcom"],
        "construction": {
            "candidate_pages": list(range(12)),
            "fallback_pages": [0, 1, 2],
        },
        "ramming": {
            "candidate_pages": [0],
            "fallback_pages": [0],
        },
    },
    "qun": {
        "match_terms": ["qun"],
        "overlay": {
            "candidate_pages": [0],
            "fallback_pages": [0],
            "keywords": ["color map", "block", "color"],
        },
    },
    "hmd": {
        "match_terms": ["hmd"],
        "construction": {
            "keywords": [
                "electrical cable plan",
                "site plan",
                "general arrangement",
            ],
            "candidate_pages": [0],
            "fallback_pages": [0],
        },
        "overlay": {
            "keywords": [
                "electrical cable plan",
                "color map",
            ],
            "candidate_pages": [0],
            "fallback_pages": [0],
        },
    },
}


def _deep_merge(base, override):
    merged = deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def _detect_profile_name(input_paths):
    haystack = " ".join(Path(path).name.lower() for path in input_paths if path)
    best_name = "default"
    best_score = 0
    for name, profile in BUILTIN_PROFILES.items():
        score = sum(1 for term in profile.get("match_terms", []) if term in haystack)
        if score > best_score:
            best_name = name
            best_score = score
    return best_name


def load_site_profile(profile_name="auto", input_paths=None, config_path=None):
    input_paths = input_paths or []
    detected_name = _detect_profile_name(input_paths)
    selected_name = detected_name if profile_name in (None, "", "auto") else profile_name

    if selected_name != "default" and selected_name not in BUILTIN_PROFILES:
        raise ValueError(f"Unknown site profile: {selected_name}")

    profile = _deep_merge(DEFAULT_PROFILE, BUILTIN_PROFILES.get(selected_name, {}))
    profile["name"] = selected_name
    profile["detected_name"] = detected_name

    if config_path:
        raw = json.loads(Path(config_path).read_text(encoding="utf-8"))
        base_name = raw.pop("extends", profile["name"])
        if base_name != profile["name"]:
            if base_name != "default" and base_name not in BUILTIN_PROFILES:
                raise ValueError(f"Unknown profile in config extends: {base_name}")
            profile = _deep_merge(DEFAULT_PROFILE, BUILTIN_PROFILES.get(base_name, {}))
            profile["name"] = base_name
        profile = _deep_merge(profile, raw)
        profile["config_path"] = str(Path(config_path).resolve())

    return profile
