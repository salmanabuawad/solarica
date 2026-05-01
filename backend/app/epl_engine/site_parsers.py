from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Any

from app.epl_engine.features import required


class SiteTypeParser:
    project_type = "unknown"

    def validate(
        self,
        project_folder: str,
        assets: list[dict[str, Any]],
        documents: list[dict[str, Any]],
        features: dict[str, str],
    ) -> list[dict[str, Any]]:
        return []


class AgroPVParser(SiteTypeParser):
    project_type = "agro_pv"

    def validate(self, project_folder: str, assets: list[dict[str, Any]], documents: list[dict[str, Any]], features: dict[str, str]) -> list[dict[str, Any]]:
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
            if _document_type(str(a.get("source_file") or "")) == "electrical_cable_plan"
        ] or zones
        zone_sum = sum(_string_zone_count(a.get("raw_label")) for a in authoritative_zones)
        if required(features, "string_zones") and authoritative_zones and zone_sum != expected_strings:
            issues.append(_issue(
                "string_zone_total_mismatch",
                "error",
                "string_zones",
                project_folder,
                f"Authoritative string-zone total is {zone_sum}, expected {expected_strings}.",
                source_file=authoritative_zones[0].get("source_file"),
                data={"actual": zone_sum, "expected": expected_strings},
            ))
        if required(features, "optimizers") and expected_strings * optimizers_per_string != expected_optimizers:
            issues.append(_issue("optimizer_math_mismatch", "error", "optimizers", project_folder, "BHK optimizer math mismatch."))
        if required(features, "modules") and expected_strings * modules_per_string != expected_modules:
            issues.append(_issue("module_math_mismatch", "error", "modules", project_folder, "BHK module math mismatch."))
        if required(features, "modules") and expected_optimizers * modules_per_optimizer != expected_modules:
            issues.append(_issue("optimizer_module_math_mismatch", "error", "modules", project_folder, "BHK optimizer/module math mismatch."))

        optimizer_labels = [a.get("raw_label") for a in assets if a.get("asset_type") == "optimizer_id"]
        for label, count in Counter(optimizer_labels).items():
            if label and count > 1:
                issues.append(_issue(
                    "duplicate_optimizer_id",
                    "warning",
                    "optimizers",
                    project_folder,
                    f"Optimizer ID '{label}' appears {count} times across EPL drawings.",
                    data={"label": label, "count": count},
                ))
        return issues


class FloatingParser(SiteTypeParser):
    project_type = "floating"

    def validate(self, project_folder: str, assets: list[dict[str, Any]], documents: list[dict[str, Any]], features: dict[str, str]) -> list[dict[str, Any]]:
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
                project_folder,
                f"{len(incomplete)} floating A/B split labels are missing a pair.",
                data={"examples": incomplete[:10]},
            ))
        return issues


class TrackerParser(SiteTypeParser):
    project_type = "tracker"

    def validate(self, project_folder: str, assets: list[dict[str, Any]], documents: list[dict[str, Any]], features: dict[str, str]) -> list[dict[str, Any]]:
        issues: list[dict[str, Any]] = []
        has_dccb = any(asset.get("asset_type") == "dccb" for asset in assets)
        if has_dccb and not any(asset.get("asset_type") == "s_string" for asset in assets):
            issues.append(_issue(
                "tracker_strings_not_derived",
                "warning",
                "strings",
                project_folder,
                "DCCB labels were detected; string derivation from DCCB pattern is not yet available for this tracker package.",
            ))
        return issues


class FixedGroundParser(SiteTypeParser):
    project_type = "fixed_ground"


class UnknownParser(SiteTypeParser):
    project_type = "unknown"


def get_site_parser(project_type: str | None) -> SiteTypeParser:
    return {
        "agro_pv": AgroPVParser,
        "floating": FloatingParser,
        "tracker": TrackerParser,
        "fixed_ground": FixedGroundParser,
    }.get(str(project_type or "unknown"), UnknownParser)()


def _issue(issue_type: str, severity: str, feature: str, project_folder: str, message: str, source_file: str | None = None, data: dict[str, Any] | None = None) -> dict[str, Any]:
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


def _document_type(source_file: str) -> str:
    name = source_file.lower()
    if "electrical cable" in name or "_e_20" in name:
        return "electrical_cable_plan"
    return "unknown"


def _string_zone_count(value: Any) -> int:
    m = re.search(r"\b(\d+)\s+STRINGS\b", str(value or ""), re.IGNORECASE)
    return int(m.group(1)) if m else 0

