from __future__ import annotations

import csv
import json
import re
import shutil
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

from app.epl_engine.features import (
    PROJECT_TYPES,
    enabled,
    feature_preset,
    merge_enabled_features,
    required,
)
from app.epl_engine.parsers.optional_assets import CAMERA_PARSER, WEATHER_STATION_PARSER
from app.epl_engine.site_parsers import get_site_parser

try:
    import fitz  # PyMuPDF
except Exception:  # pragma: no cover
    fitz = None


CONFIDENCE_HIGH = "high"
CONFIDENCE_MEDIUM = "medium"


@dataclass(frozen=True)
class PdfJob:
    path: Path
    source_file: str
    project_folder: str


DETECTORS: dict[str, re.Pattern[str]] = {
    "s_string": re.compile(r"\bS\.\d+\.\d+\.\d+\b", re.IGNORECASE),
    "string_zone": re.compile(r"\b\d+\s+STRINGS\b", re.IGNORECASE),
    "split_ab_id": re.compile(r"(?<![\w.])\d+(?:\.\d+){4}[AB]\b", re.IGNORECASE),
    "dccb": re.compile(r"\bDCCB[_\s-]?\d+(?:\.\d+)+\b", re.IGNORECASE),
    "icb": re.compile(r"\b(?:BE[-\s]?)?ICB[-\s]?(?:area[-\s]?)?\d+(?:\.\d+)?\b", re.IGNORECASE),
    "sungrow_mvs": re.compile(r"\b(?:SG350HX|SUNGROW|MVS6400|MVS5140|ST5015)\b", re.IGNORECASE),
    "solaredge_inverter": re.compile(r"\b(?:SOLAREDGE\s*330\s*kW|SE330)\b", re.IGNORECASE),
    "bess": re.compile(r"\bBESS(?:[-\s]?[A-Za-z0-9.]+)?\b", re.IGNORECASE),
    "pcs": re.compile(r"\b(?:PCSK|PCS(?:[-\s]?[A-Za-z0-9.]+)?)\b", re.IGNORECASE),
    "camera_security": re.compile(
        r"\b(?:CAB\s*[-_]?\s*\d+(?:[-_,]?\s*(?:RADAR|PTZ))?|PTZ\s*[-_]?\s*\d*|FIX(?:ED)?\s+CAM(?:ERA)?\s*[-_]?\s*\d*|FIX\s*CAM\s*[-_]?\s*\d*|CAM(?:ERA)?\s*[-_]?\s*\d*|RADAR\s*[-_]?\s*\d*)\b",
        re.IGNORECASE,
    ),
    "weather_sensor": re.compile(
        r"\b(?:SITE\s+WEATHER\s+STATION|W\.S|WS|POA|GMX|MT\s*[-_]?\s*\d*|PYRANOMETER|PT1000|WIND\s+SENSOR|AMBIENT\s+TEMPERATURE(?:\s+SENSOR)?|MODULE\s+TEMPERATURE(?:\s+SENSOR)?)\b",
        re.IGNORECASE,
    ),
    "trench_cable": re.compile(
        r"\b(?:B0|B1|B2|B4|B5|B6|B7|B8|B9|A1|A2|D1|S1|C4|T2|IECo|MV\s+TRENCH|DC\s+STRING\s+CABLE|DC\+AC\s+CABLE|SECURITY|SENSOR)\b",
        re.IGNORECASE,
    ),
    "grounding": re.compile(r"\b(?:GROUNDING|CU\s+GROUNDING|C-CLAMP|BARE\s+35\s*mm2|BARE\s+70\s*mm2|PVC\s+70\s*mm2)\b", re.IGNORECASE),
    "tracker_structure": re.compile(r"\b(?:TRACKER[-\s]?[A-Za-z0-9.]*|TYPE\s+[A-Z]|NCU|NEXTRACKER|PIER|P(?:1[0-9]|[1-9]))\b", re.IGNORECASE),
    "gate_boundary": re.compile(r"\b(?:FARMER'?S\s+GATE|GATE|ENTRANCE|FENCE|PLOT\s+BOUNDARY|BUILDING\s+BOUNDARY|GRAVEL\s+ROAD|SCENIC\s+BUFFER)\b", re.IGNORECASE),
    "floating_fpv": re.compile(r"\b(?:FPV|FLOATING|FLOATER|ANCHOR|MOORING|SHORE)\b", re.IGNORECASE),
    # Keep this after split_ab_id and s_string in output ordering. Its
    # negative lookbehind prevents S.x.x.x strings from being counted as
    # optimizer IDs.
    "optimizer_id": re.compile(r"(?<![\w.])\d+\.\d+\.\d+(?![\w.])", re.IGNORECASE),
}

# Some PDF producers split dense legends/cable tables across many text objects,
# so block extraction undercounts these labels even though the searchable text
# layer contains them. For these asset types we add text-only medium-confidence
# records to preserve package-level counts; map-data still uses positioned
# high-confidence assets when coordinates exist.
RAW_COUNT_SUPPLEMENT_TYPES = {"trench_cable", "string_zone", "s_string", "pcs"}


ASSET_FEATURE: dict[str, str] = {
    "s_string": "strings",
    "string_zone": "string_zones",
    "split_ab_id": "strings",
    "dccb": "dccb",
    "icb": "icb",
    "sungrow_mvs": "inverters",
    "solaredge_inverter": "inverters",
    "bess": "bess",
    "pcs": "pcs",
    "camera_security": "security_devices",
    "weather_sensor": "weather_sensors",
    "trench_cable": "cable_trenches",
    "grounding": "grounding",
    "tracker_structure": "trackers",
    "floating_fpv": "floating_assets",
    "optimizer_id": "optimizers",
    "gate_boundary": "gps_capture",
}


LAYER_FEATURES: dict[str, list[str]] = {
    "physical_rows": ["physical_rows"],
    "string_zones": ["string_zones"],
    "strings": ["strings"],
    "optimizers": ["optimizers"],
    "modules": ["modules"],
    "inverters": ["inverters"],
    "icb": ["icb"],
    "dccb": ["dccb"],
    "bess": ["bess"],
    "pcs": ["pcs"],
    "cable_trenches": ["cable_trenches"],
    "communication_assets": ["communication"],
    "grounding_assets": ["grounding"],
    "tracker_assets": ["trackers", "piers"],
    "floating_assets": ["floating_assets"],
    "security_devices": ["security_devices", "cameras"],
    "weather_assets": ["weather_station", "weather_sensors"],
}

LAYER_ASSET_TYPES: dict[str, set[str]] = {
    "string_zones": {"string_zone"},
    "strings": {"s_string", "split_ab_id"},
    "optimizers": {"optimizer_id"},
    "inverters": {"sungrow_mvs", "solaredge_inverter"},
    "icb": {"icb"},
    "dccb": {"dccb"},
    "bess": {"bess"},
    "pcs": {"pcs", "sungrow_mvs"},
    "cable_trenches": {"trench_cable"},
    "communication_assets": {"camera_security", "weather_sensor"},
    "grounding_assets": {"grounding"},
    "tracker_assets": {"tracker_structure"},
    "floating_assets": {"floating_fpv"},
    "security_devices": {"camera_security"},
    "weather_assets": {"weather_sensor"},
}


def collect_pdf_jobs(input_paths: Iterable[str | Path], work_dir: str | Path | None = None, default_project_folder: str = "root") -> list[PdfJob]:
    jobs: list[PdfJob] = []
    work = Path(work_dir) if work_dir else None
    if work:
        work.mkdir(parents=True, exist_ok=True)

    for item in input_paths:
        path = Path(item)
        if path.is_dir():
            root = path
            for pdf in sorted(root.rglob("*.pdf")):
                rel = pdf.relative_to(root).as_posix()
                folder = _folder_from_relative(rel, default_project_folder=path.name or default_project_folder)
                jobs.append(PdfJob(pdf, rel, folder))
        elif path.suffix.lower() == ".zip" and path.exists():
            if not work:
                continue
            extract_root = work / _safe_stem(path.stem)
            if extract_root.exists():
                shutil.rmtree(extract_root, ignore_errors=True)
            extract_root.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(path, "r") as zf:
                for info in zf.infolist():
                    if info.is_dir() or not info.filename.lower().endswith(".pdf"):
                        continue
                    rel = PurePosixPath(info.filename)
                    if any(part.startswith("..") for part in rel.parts):
                        continue
                    dest = extract_root.joinpath(*rel.parts)
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(info) as src, dest.open("wb") as out:
                        shutil.copyfileobj(src, out)
                    source_file = rel.as_posix()
                    folder = _folder_from_relative(source_file, default_project_folder=default_project_folder)
                    jobs.append(PdfJob(dest, source_file, folder))
        elif path.suffix.lower() == ".pdf" and path.exists():
            jobs.append(PdfJob(path, path.name, default_project_folder))
    return sorted(jobs, key=lambda job: (job.project_folder.lower(), job.source_file.lower()))


def build_deepsearch_model(
    input_paths: Iterable[str | Path],
    work_dir: str | Path | None = None,
    default_project_folder: str = "root",
    enabled_features: dict[str, str] | None = None,
) -> dict[str, Any]:
    jobs = collect_pdf_jobs(input_paths, work_dir=work_dir, default_project_folder=default_project_folder)
    documents: list[dict[str, Any]] = []
    assets: list[dict[str, Any]] = []
    raw_text_by_doc: dict[str, str] = {}
    blocks_scanned = 0
    notes = [
        "OCR/vision hook TODO: scan unlabeled symbols and raster-only plans in a later EPL pass.",
    ]

    for job in jobs:
        raw_text, blocks = _read_pdf_blocks(job)
        raw_text_by_doc[job.source_file] = raw_text
        blocks_scanned += len(blocks)
        doc_assets = _assets_from_blocks(job, blocks)
        if raw_text:
            if not doc_assets:
                doc_assets = _assets_from_raw_text(job, raw_text)
            else:
                doc_assets.extend(_supplement_raw_count_assets(job, raw_text, doc_assets))
        project_type_guess = detect_project_type(job.project_folder, job.source_file, raw_text)
        document_type_guess = detect_document_type(job.source_file, raw_text)
        counts = dict(Counter(asset["asset_type"] for asset in doc_assets))
        documents.append({
            "source_file": job.source_file,
            "project_folder": job.project_folder,
            "project_type_guess": project_type_guess["project_type"],
            "project_type_confidence": project_type_guess["confidence"],
            "document_type_guess": document_type_guess,
            "metadata": extract_document_metadata(raw_text),
            "counts": counts,
        })
        assets.extend(doc_assets)

    component_metadata = _component_metadata_by_folder(documents)
    folder_guesses = _project_folder_guesses(documents, assets)
    for folder, metadata in component_metadata.items():
        folder_guesses.setdefault(folder, {
            "project_type_guess": "unknown",
            "confidence": "low",
            "document_count": 0,
        })
        folder_guesses[folder]["component_metadata"] = metadata
    folder_features = {}
    for folder, guess in folder_guesses.items():
        guessed_type = guess.get("project_type_guess")
        if (
            guess.get("confidence") == "low"
            or (guess.get("project_type_guess") == "fixed_ground" and guess.get("confidence") != "high")
        ) and folder != default_project_folder:
            guessed_type = "unknown"
        folder_features[folder] = merge_enabled_features(
            guessed_type,
            enabled_features if folder == default_project_folder else None,
        )
    _apply_feature_flags(assets, folder_features)

    global_counts = dict(Counter(asset["asset_type"] for asset in assets))
    counts_by_project_folder: dict[str, dict[str, int]] = {}
    for folder, folder_assets in _group_assets(assets).items():
        counts_by_project_folder[folder] = dict(Counter(asset["asset_type"] for asset in folder_assets))

    unique_labels_by_type: dict[str, list[str]] = {}
    for asset_type in DETECTORS:
        labels = sorted({asset["raw_label"] for asset in assets if asset["asset_type"] == asset_type})
        if labels:
            unique_labels_by_type[asset_type] = labels

    validations = validate_deepsearch_assets(assets, documents, folder_features, folder_guesses, component_metadata)
    blocking_errors = [issue for issue in validations if issue.get("severity") == "error"]
    type_conflicts = [issue for issue in blocking_errors if issue.get("type") == "project_type_metadata_conflict"]
    optional_assets = _group_optional_assets(assets)

    return {
        "scope": "EPL deepsearch",
        "documents_processed": len(documents),
        "blocks_scanned": blocks_scanned,
        "global_counts": global_counts,
        "counts_by_project_folder": counts_by_project_folder,
        "project_folders": folder_guesses,
        "component_metadata_by_project_folder": component_metadata,
        "enabled_features_by_project_folder": folder_features,
        "documents": documents,
        "unique_labels_by_type": unique_labels_by_type,
        "assets": assets,
        "optional_assets": optional_assets,
        "validations": validations,
        "epl_blocked": bool(blocking_errors),
        "parse_stopped": bool(type_conflicts),
        "blocking_errors": blocking_errors,
        "stop_message": type_conflicts[0]["message"] if type_conflicts else None,
        "notes": notes,
        "raw_text": raw_text_by_doc,
    }


def prepare_map_data(model: dict[str, Any], project_folder: str | None = None) -> dict[str, Any]:
    if model.get("parse_stopped"):
        return {
            "scope": "EPL map-data",
            "project_folder": project_folder,
            "layers": {},
            "enabled_features_by_project_folder": model.get("enabled_features_by_project_folder") or {},
            "epl_blocked": True,
            "parse_stopped": True,
            "stop_message": model.get("stop_message"),
            "blocking_errors": model.get("blocking_errors") or [],
        }
    all_assets = model.get("assets") or []
    folder_features = model.get("enabled_features_by_project_folder") or {}
    folders = [project_folder] if project_folder else sorted(folder_features.keys())
    layers: dict[str, list[dict[str, Any]]] = {layer: [] for layer in LAYER_FEATURES}

    for asset in all_assets:
        folder = asset.get("project_folder") or "root"
        if folder not in folders:
            continue
        features = folder_features.get(folder) or feature_preset("unknown")
        for layer, feature_names in LAYER_FEATURES.items():
            if not any(enabled(features, feature) for feature in feature_names):
                continue
            if asset.get("asset_type") not in LAYER_ASSET_TYPES.get(layer, set()):
                continue
            if asset.get("x") is None or asset.get("y") is None:
                continue
            layers[layer].append(asset)

    return {
        "scope": "EPL map-data",
        "project_folder": project_folder,
        "layers": {layer: items for layer, items in layers.items() if items},
        "enabled_features_by_project_folder": folder_features,
    }


def write_deepsearch_exports(model: dict[str, Any], output_dir: str | Path) -> dict[str, str]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths: dict[str, str] = {}

    def remember(name: str, path: Path) -> None:
        paths[name] = str(path)

    model_path = out / "epl_model.json"
    model_path.write_text(json.dumps(model, indent=2, ensure_ascii=False), encoding="utf-8")
    remember("epl_model_json", model_path)

    doc_csv = out / "document_summary.csv"
    with doc_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["source_file", "project_folder", "project_type_guess", "document_type_guess", "counts_json", "metadata_json"])
        for doc in model.get("documents", []):
            w.writerow([
                doc.get("source_file"),
                doc.get("project_folder"),
                doc.get("project_type_guess"),
                doc.get("document_type_guess"),
                json.dumps(doc.get("counts") or {}, ensure_ascii=False),
                json.dumps(doc.get("metadata") or {}, ensure_ascii=False),
            ])
    remember("document_summary_csv", doc_csv)

    assets_csv = out / "assets_all.csv"
    _write_assets_csv(assets_csv, model.get("assets", []))
    remember("assets_all_csv", assets_csv)

    labels_csv = out / "unique_labels_by_type.csv"
    with labels_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["asset_type", "raw_label"])
        for asset_type, labels in sorted((model.get("unique_labels_by_type") or {}).items()):
            for label in labels:
                w.writerow([asset_type, label])
    remember("unique_labels_by_type_csv", labels_csv)

    counts_csv = out / "counts_by_project.csv"
    with counts_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["project_folder", "asset_type", "count"])
        for folder, counts in sorted((model.get("counts_by_project_folder") or {}).items()):
            for asset_type, count in sorted(counts.items()):
                w.writerow([folder, asset_type, count])
    remember("counts_by_project_csv", counts_csv)

    export_specs = {
        "physical_rows.csv": {"tracker_structure"},
        "string_zones.csv": {"string_zone"},
        "strings.csv": {"s_string", "split_ab_id"},
        "optimizers.csv": {"optimizer_id"},
        "modules.csv": set(),
        "optional_security_devices.csv": {"camera_security"},
        "optional_weather_assets.csv": {"weather_sensor"},
    }
    for filename, asset_types in export_specs.items():
        path = out / filename
        rows = [a for a in model.get("assets", []) if a.get("asset_type") in asset_types] if asset_types else []
        _write_assets_csv(path, rows)
        remember(filename.replace(".", "_"), path)

    issues_csv = out / "validation_issues.csv"
    with issues_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["severity", "type", "feature", "project_folder", "source_file", "message", "data_json"])
        for issue in model.get("validations", []):
            w.writerow([
                issue.get("severity"),
                issue.get("type"),
                issue.get("feature"),
                issue.get("project_folder"),
                issue.get("source_file"),
                issue.get("message"),
                json.dumps(issue.get("data") or {}, ensure_ascii=False),
            ])
    remember("validation_issues_csv", issues_csv)

    raw_dir = out / "raw_text"
    raw_dir.mkdir(exist_ok=True)
    for source_file, text in (model.get("raw_text") or {}).items():
        safe = _safe_stem(source_file).strip("_") or "document"
        raw_path = raw_dir / f"{safe}.txt"
        raw_path.write_text(text or "", encoding="utf-8")
        remember(f"raw_text_{safe}", raw_path)

    return paths


def validate_deepsearch_assets(
    assets: list[dict[str, Any]],
    documents: list[dict[str, Any]],
    folder_features: dict[str, dict[str, str]],
    folder_guesses: dict[str, dict[str, Any]],
    component_metadata: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    assets_by_folder = _group_assets(assets)

    feature_asset_types: dict[str, set[str]] = defaultdict(set)
    for asset_type, feature in ASSET_FEATURE.items():
        feature_asset_types[feature].add(asset_type)
    feature_asset_types["piers"].add("tracker_structure")
    feature_asset_types["weather_station"].add("weather_sensor")
    feature_asset_types["cameras"].add("camera_security")
    feature_asset_types["strings"].add("string_zone")
    feature_asset_types["physical_rows"].update({"physical_row", "string_zone", "tracker_structure"})
    feature_asset_types["modules"].update({"module", "optimizer_id", "string_zone", "s_string", "split_ab_id"})

    for folder, features in folder_features.items():
        folder_assets = assets_by_folder.get(folder, [])
        asset_types_present = {asset.get("asset_type") for asset in folder_assets}
        guess = folder_guesses.get(folder, {})
        type_conflict = _project_type_metadata_conflict(folder, folder_assets, guess)
        if type_conflict:
            issues.append(type_conflict)
        for feature, state in features.items():
            if state == "required" and not (asset_types_present & feature_asset_types.get(feature, set())):
                issues.append(_issue(
                    "required_asset_missing",
                    "error",
                    feature,
                    folder,
                    f"Required EPL feature '{feature}' has no detected assets.",
                ))

        if enabled(features, "cameras") and not any(a.get("asset_type") == "camera_security" for a in folder_assets):
            issues.append(_issue("missing_optional_cameras", "warning", "cameras", folder, "No optional camera/security labels detected."))
        if enabled(features, "weather_station") and not any(_looks_weather_station(a) for a in folder_assets):
            issues.append(_issue("missing_optional_weather_station", "warning", "weather_station", folder, "No optional weather station labels detected."))
        if enabled(features, "weather_sensors") and not any(a.get("asset_type") == "weather_sensor" for a in folder_assets):
            issues.append(_issue("missing_optional_weather_sensors", "warning", "weather_sensors", folder, "No optional weather/sensor labels detected."))

        for optional_type, issue_type, feature in (
            ("camera_security", "duplicate_camera_label", "cameras"),
            ("weather_sensor", "duplicate_weather_label", "weather_sensors"),
        ):
            labels = Counter(_norm_label(a.get("raw_label")) for a in folder_assets if a.get("asset_type") == optional_type)
            for label, count in labels.items():
                if label and count > 1:
                    issues.append(_issue(issue_type, "warning", feature, folder, f"Repeated optional label '{label}' appears {count} times.", data={"label": label, "count": count}))

        project_type = guess.get("project_type_guess")
        issues.extend(_validate_metadata_components(folder, folder_assets, features, component_metadata or {}))
        issues.extend(get_site_parser(project_type).validate(folder, folder_assets, documents, features))

    return issues


def detect_project_type(project_folder: str, source_file: str = "", text: str = "") -> dict[str, Any]:
    hay = f"{project_folder} {source_file} {text[:20000]}".lower()
    if "sadii" in hay:
        return {"project_type": "fixed_ground", "confidence": "medium"}
    scores = {
        "floating": _score(hay, ["qunaitra", "fpv", "floating", "floater", "mooring", "shore"]),
        "agro_pv": _score(hay, ["bhk", "bet hae", "bet_hae", "agro-pv", "agro pv", "solaredge", "optimizer"]),
        "tracker": _score(hay, ["taliia", "ashalim", "nextracker", "ramming", "tracker", "pier"]),
        "fixed_ground": _score(hay, ["fixed ground", "sadii"]),
    }
    project_type, score = max(scores.items(), key=lambda item: item[1])
    if score <= 0:
        return {"project_type": "unknown", "confidence": "low"}
    confidence = "high" if score >= 2 or project_type in hay else "medium"
    if project_type == "fixed_ground" and "sadii" in hay:
        confidence = "high"
    return {"project_type": project_type, "confidence": confidence}


def detect_document_type(source_file: str, text: str = "") -> str:
    name = source_file.lower()
    if "communication" in name or "_e_30" in name:
        return "communication_plan"
    if "electrical cable" in name or "_e_20" in name:
        return "electrical_cable_plan"
    if "grounding" in name or "_e_50" in name:
        return "grounding_plan"
    if "trench" in name or "_e_40" in name:
        return "cable_trench_plan"
    if "color map" in name or "colour map" in name or "_e_10" in name:
        return "color_map"
    if "panel" in name or "_e_41" in name:
        return "panels_plan"
    if "agro" in name or "_e_11" in name:
        return "agro_pv_plan"
    if "ramming" in name:
        return "ramming_plan"
    if "construction" in name:
        return "construction_plan"
    if "site" in name:
        return "site_plan"
    if "weather" in (text or "").lower():
        return "site_plan"
    return "unknown"


def extract_document_metadata(text: str) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    patterns = {
        "total_modules": r"(?:Number\s+of\s+Modules|Modules)\s*[-:]\s*(\d[\d,\.]*)",
        "total_optimizers": r"(?:No[°º]?\s*of\s+optimizers\s+H1300|optimizers?)\s*[-:]\s*(\d[\d,\.]*)",
        "total_strings": r"(?:Number\s+of\s+STRINGS|strings?)\s*[-:]\s*(\d[\d,\.]*)",
        "storage_capacity_mwh": r"(\d+(?:\.\d+)?)\s*MWh",
    }
    for key, pattern in patterns.items():
        m = re.search(pattern, text or "", re.IGNORECASE)
        if not m:
            continue
        value = m.group(1).replace(",", "")
        try:
            metadata[key] = float(value) if "." in value else int(value)
        except ValueError:
            metadata[key] = value
    if re.search(r"\bSOLAREDGE\s*330\s*kW\b|\bSE330\b", text or "", re.IGNORECASE):
        metadata["inverter_family"] = "SolarEdge SE330"
    if re.search(r"\bSG350HX\b|\bSUNGROW\b", text or "", re.IGNORECASE):
        metadata["inverter_family"] = "Sungrow"
    component_expectations = _component_expectations_from_text(text or "")
    if component_expectations:
        metadata["component_expectations"] = component_expectations
    return metadata


def _component_expectations_from_text(text: str) -> list[dict[str, Any]]:
    expectations: list[dict[str, Any]] = []
    seen: set[tuple[str, str, int | None]] = set()
    product_patterns = [
        ("sungrow_mvs", "inverters", "SG350HX", r"\bSG350HX\b"),
        ("sungrow_mvs", "pcs", "MVS5140", r"\bMVS5140\b"),
        ("sungrow_mvs", "pcs", "MVS6400", r"\bMVS6400\b"),
        ("bess", "bess", "ST5015", r"\bST5015(?:\s*kWh)?\b"),
        ("solaredge_inverter", "inverters", "SolarEdge SE330", r"\b(?:SE330|SOLAREDGE\s*330\s*kW)\b"),
        ("bess", "bess", "BESS", r"\bBESS\b"),
        ("pcs", "pcs", "PCS", r"\b(?:PCSK|PCS)\b"),
        ("weather_sensor", "weather_sensors", "weather_station", r"\b(?:SITE\s+WEATHER\s+STATION|W\.S|WS|POA|GMX|PYRANOMETER|PT1000)\b"),
        ("camera_security", "security_devices", "security_camera", r"\b(?:PTZ|CAM|RADAR|CAB)\b"),
    ]
    for asset_type, feature, label, pattern in product_patterns:
        count = _count_near_label(text, pattern)
        if label in {"BESS", "SolarEdge SE330"} and count is None and re.search(pattern, text, re.IGNORECASE):
            count = 1
        if count is None and re.search(pattern, text, re.IGNORECASE):
            count = 1
        if count is None:
            continue
        key = (asset_type, label, count)
        if key in seen:
            continue
        seen.add(key)
        expectations.append({
            "asset_type": asset_type,
            "feature": feature,
            "label": label,
            "expected_count": count,
            "source": "map_metadata",
        })
    return expectations


def _count_near_label(text: str, label_pattern: str) -> int | None:
    # Match common BOM/map metadata phrases such as "34 x SG350HX",
    # "4 MVS5140 PCS", or "13 Sungrow ST5015kWh batteries". Keep this
    # line-scoped so model numbers/efficiency percentages in nearby text
    # don't become fake asset counts.
    for line in (text or "").splitlines():
        before = re.search(rf"\b(\d{{1,5}})\s*(?:x|X|×|-)?\s*(?:[A-Za-z]+\s+){{0,3}}{label_pattern}", line, re.IGNORECASE)
        if before:
            return int(before.group(1))
    return None


def _read_pdf_blocks(job: PdfJob) -> tuple[str, list[dict[str, Any]]]:
    if fitz is None:
        return "", []
    text_parts: list[str] = []
    blocks: list[dict[str, Any]] = []
    try:
        with fitz.open(str(job.path)) as doc:
            for page_no, page in enumerate(doc, start=1):
                page_text = page.get_text("text") or ""
                text_parts.append(page_text)
                for b in page.get_text("blocks") or []:
                    if len(b) < 5:
                        continue
                    x0, y0, x1, y1, txt = b[:5]
                    if not isinstance(txt, str) or not txt.strip():
                        continue
                    blocks.append({
                        "source_file": job.source_file,
                        "project_folder": job.project_folder,
                        "page": page_no,
                        "x": round(float(x0), 2),
                        "y": round(float(y0), 2),
                        "x1": round(float(x1), 2),
                        "y1": round(float(y1), 2),
                        "text_block": txt.strip().replace("\n", " "),
                    })
    except Exception:
        return "", []
    return "\n".join(text_parts), blocks


def _assets_from_blocks(job: PdfJob, blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    assets: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for block in blocks:
        text = block.get("text_block") or ""
        for asset_type, pattern in DETECTORS.items():
            for match in pattern.finditer(text):
                raw_label = _clean_label(match.group(0))
                if not raw_label:
                    continue
                key = (asset_type, raw_label.upper(), block.get("source_file"), block.get("page"), block.get("x"), block.get("y"))
                if key in seen:
                    continue
                seen.add(key)
                asset = {
                    "project_folder": job.project_folder,
                    "asset_type": asset_type,
                    "raw_label": raw_label,
                    "source_file": job.source_file,
                    "page": block.get("page"),
                    "x": block.get("x"),
                    "y": block.get("y"),
                    "x1": block.get("x1"),
                    "y1": block.get("y1"),
                    "confidence": CONFIDENCE_HIGH,
                    "required": False,
                    "requires_field_validation": asset_type in {"camera_security", "weather_sensor"},
                    "text_block": text[:300],
                }
                asset.update(_asset_extras(asset_type, raw_label, text))
                assets.append(asset)
    return assets


def _assets_from_raw_text(job: PdfJob, raw_text: str) -> list[dict[str, Any]]:
    assets: list[dict[str, Any]] = []
    for asset_type, pattern in DETECTORS.items():
        for match in pattern.finditer(raw_text or ""):
            asset = {
                "project_folder": job.project_folder,
                "asset_type": asset_type,
                "raw_label": _clean_label(match.group(0)),
                "source_file": job.source_file,
                "page": None,
                "x": None,
                "y": None,
                "x1": None,
                "y1": None,
                "confidence": CONFIDENCE_MEDIUM,
                "required": False,
                "requires_field_validation": asset_type in {"camera_security", "weather_sensor"},
                "text_block": _clean_label(match.group(0)),
            }
            asset.update(_asset_extras(asset_type, asset["raw_label"], asset["text_block"]))
            assets.append(asset)
    return assets


def _supplement_raw_count_assets(job: PdfJob, raw_text: str, positioned_assets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    supplements: list[dict[str, Any]] = []
    positioned_counts = Counter(asset.get("asset_type") for asset in positioned_assets)
    for asset_type in RAW_COUNT_SUPPLEMENT_TYPES:
        matches = list(DETECTORS[asset_type].finditer(raw_text or ""))
        missing = len(matches) - int(positioned_counts.get(asset_type, 0))
        if missing <= 0:
            continue
        for match in matches[-missing:]:
            asset = {
                "project_folder": job.project_folder,
                "asset_type": asset_type,
                "raw_label": _clean_label(match.group(0)),
                "source_file": job.source_file,
                "page": None,
                "x": None,
                "y": None,
                "x1": None,
                "y1": None,
                "confidence": CONFIDENCE_MEDIUM,
                "required": False,
                "requires_field_validation": False,
                "text_block": _clean_label(match.group(0)),
            }
            asset.update(_asset_extras(asset_type, asset["raw_label"], asset["text_block"]))
            supplements.append(asset)
    return supplements


def _apply_feature_flags(assets: list[dict[str, Any]], folder_features: dict[str, dict[str, str]]) -> None:
    for asset in assets:
        features = folder_features.get(asset.get("project_folder")) or feature_preset("unknown")
        feature = ASSET_FEATURE.get(asset.get("asset_type"))
        asset["required"] = bool(feature and required(features, feature))
        if asset.get("asset_type") in {"camera_security", "weather_sensor"}:
            asset["required"] = False
            asset["requires_field_validation"] = True


def _component_metadata_by_folder(documents: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    aggregate: dict[str, dict[tuple[str, str, str], dict[str, Any]]] = defaultdict(dict)
    numeric_meta: dict[str, dict[str, int | float]] = defaultdict(dict)

    for doc in documents:
        folder = str(doc.get("project_folder") or "root")
        metadata = doc.get("metadata") or {}
        for key in ("total_modules", "total_optimizers", "total_strings", "storage_capacity_mwh"):
            if isinstance(metadata.get(key), (int, float)):
                numeric_meta[folder][key] = max(float(numeric_meta[folder].get(key, 0)), float(metadata[key]))
        for expectation in metadata.get("component_expectations") or []:
            asset_type = str(expectation.get("asset_type") or "")
            label = str(expectation.get("label") or asset_type)
            feature = str(expectation.get("feature") or ASSET_FEATURE.get(asset_type) or "")
            if not asset_type or not feature:
                continue
            key = (asset_type, feature, _norm_label(label))
            previous = aggregate[folder].get(key)
            expected_count = expectation.get("expected_count")
            if previous is None:
                aggregate[folder][key] = dict(expectation)
                aggregate[folder][key]["source_files"] = [doc.get("source_file")]
            else:
                if isinstance(expected_count, int) and expected_count > int(previous.get("expected_count") or 0):
                    previous["expected_count"] = expected_count
                previous.setdefault("source_files", []).append(doc.get("source_file"))

    for folder, values in numeric_meta.items():
        if values.get("total_strings"):
            aggregate[folder][("string_zone", "strings", "STRINGS")] = {
                "asset_type": "string_zone",
                "feature": "strings",
                "label": "strings",
                "expected_count": int(values["total_strings"]),
                "source": "map_metadata",
            }
        if values.get("total_optimizers"):
            aggregate[folder][("optimizer_id", "optimizers", "OPTIMIZERS")] = {
                "asset_type": "optimizer_id",
                "feature": "optimizers",
                "label": "optimizers",
                "expected_count": int(values["total_optimizers"]),
                "source": "map_metadata",
            }
        if values.get("total_modules"):
            aggregate[folder][("module", "modules", "MODULES")] = {
                "asset_type": "module",
                "feature": "modules",
                "label": "modules",
                "expected_count": int(values["total_modules"]),
                "source": "map_metadata",
            }

    for folder, items in aggregate.items():
        expectations = sorted(items.values(), key=lambda item: (str(item.get("feature")), str(item.get("label"))))
        out[folder] = {
            "source": "map_metadata",
            "expectations": expectations,
            "counts_by_feature": dict(Counter(item.get("feature") for item in expectations if item.get("feature"))),
            "counts_by_asset_type": dict(Counter(item.get("asset_type") for item in expectations if item.get("asset_type"))),
        }
        if "sadii" in folder.lower():
            out[folder]["site_geometry"] = {
                "mounting": "fixed_panels",
                "panels_per_row_depth": 3,
            }
    return out


def _validate_metadata_components(
    folder: str,
    folder_assets: list[dict[str, Any]],
    features: dict[str, str],
    component_metadata: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    metadata = component_metadata.get(folder) or {}
    expectations = metadata.get("expectations") or []
    if not expectations:
        return []

    positioned_types = Counter(
        asset.get("asset_type")
        for asset in folder_assets
        if asset.get("x") is not None and asset.get("y") is not None
    )
    issues: list[dict[str, Any]] = []
    for expectation in expectations:
        feature = str(expectation.get("feature") or "")
        if feature and not enabled(features, feature):
            continue
        asset_types = _metadata_map_asset_types(expectation)
        if not asset_types:
            continue
        actual = sum(positioned_types.get(asset_type, 0) for asset_type in asset_types)
        if actual > 0:
            continue
        severity = "error" if feature and required(features, feature) else "warning"
        issues.append(_issue(
            "metadata_component_missing_on_map",
            severity,
            feature or "metadata",
            folder,
            f"Map metadata lists {expectation.get('label') or expectation.get('asset_type')}, but no positioned map label was detected for it.",
            data={
                "expected_count": expectation.get("expected_count"),
                "asset_types": sorted(asset_types),
                "source": expectation.get("source"),
            },
        ))
    return issues


def _metadata_map_asset_types(expectation: dict[str, Any]) -> set[str]:
    asset_type = str(expectation.get("asset_type") or "")
    feature = str(expectation.get("feature") or "")
    if asset_type == "module" or feature == "modules":
        return {"optimizer_id", "string_zone", "s_string", "split_ab_id"}
    if feature == "strings":
        return {"s_string", "split_ab_id", "string_zone"}
    if feature == "inverters":
        return {"sungrow_mvs", "solaredge_inverter"}
    if feature == "pcs":
        return {"pcs", "sungrow_mvs"}
    if feature == "weather_station":
        return {"weather_sensor"}
    if feature in {"security_devices", "cameras"}:
        return {"camera_security"}
    return {asset_type} if asset_type else set()


def _project_type_metadata_conflict(folder: str, assets: list[dict[str, Any]], guess: dict[str, Any]) -> dict[str, Any] | None:
    metadata_type = (guess.get("site_metadata") or {}).get("project_type") or (guess.get("site_metadata") or {}).get("mounting")
    if not metadata_type:
        return None
    metadata_type = _normalize_metadata_project_type(str(metadata_type))
    if not metadata_type or metadata_type == "unknown":
        return None

    evidence = _project_type_from_map_evidence(folder, assets)
    if not evidence or evidence["project_type"] in {metadata_type, "unknown"}:
        return None
    if evidence["confidence"] == "low":
        return None
    return _issue(
        "project_type_metadata_conflict",
        "error",
        "project_type",
        folder,
        f"Project metadata says '{metadata_type}', but map evidence looks like '{evidence['project_type']}'. Stop EPL parsing and confirm the site type or uploaded folder.",
        data={
            "metadata_project_type": metadata_type,
            "map_project_type": evidence["project_type"],
            "map_confidence": evidence["confidence"],
            "signals": evidence["signals"],
        },
    )


def _project_type_from_map_evidence(folder: str, assets: list[dict[str, Any]]) -> dict[str, Any] | None:
    counts = Counter(asset.get("asset_type") for asset in assets)
    labels = " ".join(str(asset.get("raw_label") or "") for asset in assets[:5000]).lower()
    scores = {
        "floating": int(counts.get("floating_fpv", 0) > 0) * 3 + int("fpv" in labels or "floating" in labels) * 2 + int(counts.get("sungrow_mvs", 0) > 0),
        "agro_pv": int(counts.get("solaredge_inverter", 0) > 0) * 3 + int(counts.get("optimizer_id", 0) > 25) + int("agro" in labels or "solaredge" in labels) * 2,
        "tracker": int(counts.get("tracker_structure", 0) > 100) * 3 + int(counts.get("dccb", 0) > 0) + int("nextracker" in labels or "tracker" in labels) * 2,
        "fixed_ground": int("fixed" in labels or "sadii" in folder.lower()) * 2,
    }
    project_type, score = max(scores.items(), key=lambda item: item[1])
    if score <= 0:
        return None
    return {
        "project_type": project_type,
        "confidence": "high" if score >= 4 else "medium",
        "signals": {key: value for key, value in counts.items() if value},
    }


def _normalize_metadata_project_type(value: str) -> str:
    normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
    if normalized in {"fixed", "fixed_panels", "fixed_panel", "ground_fixed"}:
        return "fixed_ground"
    if normalized in {"fpv", "floating_pv"}:
        return "floating"
    if normalized in PROJECT_TYPES:
        return normalized
    return "unknown"


def _group_optional_assets(assets: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped = {"security_devices": [], "weather_assets": []}
    counters = {"security_devices": 0, "weather_assets": 0}
    prefixes = {"security_devices": "CAM", "weather_assets": "WS"}
    for asset in assets:
        if asset.get("asset_type") == "camera_security":
            group = "security_devices"
        elif asset.get("asset_type") == "weather_sensor":
            group = "weather_assets"
        else:
            continue
        counters[group] += 1
        item = {
            "id": f"{prefixes[group]}_{counters[group]:03d}",
            "type": asset.get("optional_asset_type") or asset.get("asset_type"),
            "raw_label": asset.get("raw_label"),
            "source_file": asset.get("source_file"),
            "project_folder": asset.get("project_folder"),
            "page": asset.get("page"),
            "x": asset.get("x"),
            "y": asset.get("y"),
            "confidence": asset.get("confidence"),
            "required": False,
            "requires_field_validation": True,
        }
        if group == "weather_assets":
            item["sensors"] = asset.get("sensors") or []
        grouped[group].append(item)
    return grouped


def _project_folder_guesses(documents: list[dict[str, Any]], assets: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    folders = sorted({doc.get("project_folder") for doc in documents if doc.get("project_folder")} | {asset.get("project_folder") for asset in assets if asset.get("project_folder")})
    out: dict[str, dict[str, Any]] = {}
    for folder in folders:
        votes = Counter(doc.get("project_type_guess") for doc in documents if doc.get("project_folder") == folder)
        if votes:
            project_type, count = votes.most_common(1)[0]
        else:
            project_type, count = "unknown", 0
        if project_type not in PROJECT_TYPES:
            project_type = "unknown"
        out[folder] = {
            "project_type_guess": project_type,
            "confidence": "high" if count >= 2 and project_type != "unknown" else "medium" if project_type != "unknown" else "low",
            "document_count": sum(1 for doc in documents if doc.get("project_folder") == folder),
        }
        if "sadii" in folder.lower():
            out[folder]["project_type_guess"] = "fixed_ground"
            out[folder]["confidence"] = "medium"
            out[folder]["classification_note"] = "Fixed-ground candidate from user/site metadata; map evidence currently shows BESS, optimizer IDs, cameras, and boundaries but limited structural certainty."
            out[folder]["site_metadata"] = {
                "project_type": "fixed_ground",
                "mounting": "fixed_panels",
                "panel_rows": "fixed_ground",
                "panels_per_row_depth": 3,
                "notes": "Sadii rows use three panels across the row depth; do not classify as tracker or agro-PV optimizer rows.",
            }
        if "qunaitra" in folder.lower() and out[folder]["project_type_guess"] == "floating":
            out[folder]["confidence"] = "high"
    return out


def _validate_agro_pv(folder: str, assets: list[dict[str, Any]], documents: list[dict[str, Any]], features: dict[str, str]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    expected_strings = 288
    expected_optimizers = 6336
    expected_modules = 12672
    modules_per_string = 44
    optimizers_per_string = 22
    modules_per_optimizer = 2

    zones = [a for a in assets if a.get("asset_type") == "string_zone"]
    authoritative_zones = [
        a for a in zones
        if detect_document_type(str(a.get("source_file") or "")) == "electrical_cable_plan"
    ] or zones
    zone_sum = sum(_string_zone_count(a.get("raw_label")) for a in authoritative_zones)
    if required(features, "string_zones") and authoritative_zones and zone_sum != expected_strings:
        issues.append(_issue(
            "string_zone_total_mismatch",
            "error",
            "string_zones",
            folder,
            f"Authoritative string-zone total is {zone_sum}, expected {expected_strings}.",
            source_file=authoritative_zones[0].get("source_file"),
            data={"actual": zone_sum, "expected": expected_strings},
        ))
    if required(features, "optimizers") and expected_strings * optimizers_per_string != expected_optimizers:
        issues.append(_issue("optimizer_math_mismatch", "error", "optimizers", folder, "BHK optimizer math mismatch.", data={"strings": expected_strings}))
    if required(features, "modules") and expected_strings * modules_per_string != expected_modules:
        issues.append(_issue("module_math_mismatch", "error", "modules", folder, "BHK module math mismatch.", data={"strings": expected_strings}))
    if required(features, "modules") and expected_optimizers * modules_per_optimizer != expected_modules:
        issues.append(_issue("optimizer_module_math_mismatch", "error", "modules", folder, "BHK optimizer/module math mismatch."))

    optimizer_labels = [a.get("raw_label") for a in assets if a.get("asset_type") == "optimizer_id"]
    for label, count in Counter(optimizer_labels).items():
        if label and count > 1:
            issues.append(_issue(
                "duplicate_optimizer_id",
                "warning",
                "optimizers",
                folder,
                f"Optimizer ID '{label}' appears {count} times across EPL drawings.",
                data={"label": label, "count": count},
            ))
    return issues


def _validate_floating(folder: str, assets: list[dict[str, Any]], features: dict[str, str]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    split_ids = [str(a.get("raw_label") or "") for a in assets if a.get("asset_type") == "split_ab_id"]
    groups: dict[str, set[str]] = defaultdict(set)
    for label in split_ids:
        m = re.match(r"(.+)([AB])$", label, re.IGNORECASE)
        if m:
            groups[m.group(1)].add(m.group(2).upper())
    incomplete = sorted(group for group, parts in groups.items() if parts != {"A", "B"})
    if incomplete and required(features, "strings"):
        issues.append(_issue(
            "incomplete_split_ab_pairs",
            "warning",
            "strings",
            folder,
            f"{len(incomplete)} floating A/B split labels are missing a pair.",
            data={"examples": incomplete[:10]},
        ))
    return issues


def _group_assets(assets: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for asset in assets:
        out[str(asset.get("project_folder") or "root")].append(asset)
    return out


def _issue(
    issue_type: str,
    severity: str,
    feature: str,
    project_folder: str,
    message: str,
    source_file: str | None = None,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "type": issue_type,
        "severity": severity,
        "feature": feature,
        "project_folder": project_folder,
        "message": message,
        "source_file": source_file,
        "data": data or {},
        "blocking": severity == "error",
    }


def _looks_weather_station(asset: dict[str, Any]) -> bool:
    if asset.get("asset_type") != "weather_sensor":
        return False
    label = str(asset.get("raw_label") or "").upper()
    return any(token in label for token in ("WEATHER", "W.S", "WS", "GMX"))


def _score(haystack: str, needles: list[str]) -> int:
    return sum(1 for needle in needles if needle.lower() in haystack)


def _folder_from_relative(source_file: str, default_project_folder: str) -> str:
    parts = PurePosixPath(source_file).parts
    if len(parts) > 1:
        return parts[0]
    return default_project_folder or "root"


def _safe_stem(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value)


def _clean_label(value: str | None) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip(" :-_,")).strip()


def _norm_label(value: str | None) -> str:
    return re.sub(r"[^A-Z0-9]+", "", str(value or "").upper())


def _asset_extras(asset_type: str, raw_label: str, context: str = "") -> dict[str, Any]:
    label = str(raw_label or "")
    if asset_type == "camera_security":
        return CAMERA_PARSER.classify(label, context)
    if asset_type == "weather_sensor":
        return WEATHER_STATION_PARSER.classify(label, context)
    return {}


def _string_zone_count(value: Any) -> int:
    m = re.search(r"\b(\d+)\s+STRINGS\b", str(value or ""), re.IGNORECASE)
    return int(m.group(1)) if m else 0


def _write_assets_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = [
        "project_folder",
        "asset_type",
        "raw_label",
        "source_file",
        "page",
        "x",
        "y",
        "x1",
        "y1",
        "confidence",
        "required",
        "requires_field_validation",
        "text_block",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow(row)
