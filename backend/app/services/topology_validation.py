"""
TopologyValidationService — validates inverter/MPPT/string topology.
Works entirely on the scan_result dict; no DB access required.
"""
from __future__ import annotations
from collections import Counter, defaultdict
from typing import Any

from app.services.event_bus import EventBus


class TopologyValidationService:
    """
    Runs topology validation and returns findings + events.
    All 8 issue types from the specification are implemented.
    """

    def validate(
        self,
        scan_result: dict[str, Any],
        project_id: int | None = None,
        bus: EventBus | None = None,
    ) -> list[dict[str, Any]]:
        bus = bus or EventBus()
        findings: list[dict[str, Any]] = []

        inverters: list[dict] = scan_result.get("inverters", [])
        string_rows: list[dict] = scan_result.get("string_rows", [])
        mppt_channels: list[dict] = scan_result.get("mppt_channels", [])
        icb_zones: list[dict] = scan_result.get("icb_zones", [])
        map_zones: list[dict] = scan_result.get("map_zones", [])

        # ── helpers ────────────────────────────────────────────────────────
        def finding(code: str, severity: str, title: str, description: str,
                    related: list[str] | None = None) -> dict:
            f = {
                "risk_code": code,
                "severity": severity,
                "title": title,
                "description": description,
                "recommendations": [],
                "related_assets": related or [],
            }
            return f

        # ── 1. duplicate_inverter ──────────────────────────────────────────
        label_counts = Counter(inv["raw_name"] for inv in inverters)
        for label, count in label_counts.items():
            if count > 1:
                f = finding(
                    "duplicate_inverter", "high",
                    "Duplicate inverter label",
                    f"Inverter label '{label}' appears {count} times in the topology.",
                    [label],
                )
                findings.append(f)
                bus.emit("inverter.mismatch", {"type": "duplicate", "label": label})

        # ── 2. missing_inverter ───────────────────────────────────────────
        for inv in inverters:
            pattern = inv.get("pattern", "")
            if pattern in ("inferred", "gap_fill"):
                desc = (
                    f"Inverter '{inv['raw_name']}' was not detected in the drawing "
                    f"(pattern: {pattern}). It has {inv.get('strings_count', 0)} strings assigned."
                )
                f = finding(
                    "missing_inverter", "medium",
                    "Inverter missing from color map",
                    desc,
                    [inv["raw_name"]],
                )
                findings.append(f)
                bus.emit("inverter.mismatch", {"type": "missing", "label": inv["raw_name"], "pattern": pattern})

        # ── 3. invalid_mppt ───────────────────────────────────────────────
        if mppt_channels:
            for ch in mppt_channels:
                mppt_no = ch.get("mppt_no")
                dc_no = ch.get("dc_terminal_no")
                if mppt_no is not None and mppt_no > 12:
                    f = finding(
                        "invalid_mppt", "medium",
                        "MPPT number out of expected range",
                        f"MPPT {mppt_no} in zone {ch.get('icb_zone')} DC{dc_no} exceeds expected max of 12.",
                    )
                    findings.append(f)
                    bus.emit("mppt.mismatch", {"type": "invalid_number", "mppt_no": mppt_no, "zone": ch.get("icb_zone")})
                if dc_no is not None and dc_no > 3:
                    f = finding(
                        "invalid_mppt", "low",
                        "DC terminal number out of expected range",
                        f"DC terminal {dc_no} in zone {ch.get('icb_zone')} exceeds expected max of 3.",
                    )
                    findings.append(f)

        # ── 4. mppt_string_count_mismatch ────────────────────────────────
        if mppt_channels:
            for ch in mppt_channels:
                detected = ch.get("string_count", 0)
                expected = ch.get("expected_string_count")
                if expected and detected != expected:
                    key = f"{ch.get('icb_zone')} DC{ch.get('dc_terminal_no')} MPPT{ch.get('mppt_no')}"
                    f = finding(
                        "mppt_string_count_mismatch", "medium",
                        "MPPT string count mismatch",
                        f"{key}: expected {expected} strings, detected {detected}.",
                    )
                    findings.append(f)
                    bus.emit("mppt.mismatch", {"type": "string_count", "zone": key, "expected": expected, "detected": detected})

        # ── 5. inverter_string_count_mismatch ────────────────────────────
        # Group valid strings by inverter (section.block)
        actual_counts: dict[str, int] = defaultdict(int)
        for row in string_rows:
            if row.get("is_valid") and row.get("section_no") and row.get("block_no"):
                key = f"{row['section_no']}.{row['block_no']}"
                actual_counts[key] += 1

        for inv in inverters:
            label = inv["raw_name"]
            expected = inv.get("expected_string_count")
            detected = actual_counts.get(label, inv.get("strings_count", 0))
            if expected and detected != expected:
                f = finding(
                    "inverter_string_count_mismatch", "medium",
                    "Inverter string count mismatch",
                    f"Inverter {label}: expected {expected} strings, detected {detected}.",
                    [label],
                )
                findings.append(f)
                bus.emit("inverter.mismatch", {"type": "string_count", "label": label, "expected": expected, "detected": detected})

        # ── 6. color_group_mismatch ───────────────────────────────────────
        # Requires map_zones to be populated (via API)
        if map_zones:
            zone_by_inverter: dict[str, str] = {
                z["inverter_label"]: z["color_code"]
                for z in map_zones if z.get("inverter_label") and z.get("color_code")
            }
            for row in string_rows:
                if not row.get("is_valid"):
                    continue
                color = row.get("color_group")
                inv_label = f"{row.get('section_no')}.{row.get('block_no')}"
                expected_color = zone_by_inverter.get(inv_label)
                if color and expected_color and color != expected_color:
                    f = finding(
                        "color_group_mismatch", "high",
                        "String color group mismatch",
                        f"String {row.get('string_code')} has color '{color}' but inverter {inv_label} expects '{expected_color}'.",
                        [row.get("string_code", "")],
                    )
                    findings.append(f)
                    bus.emit("color.mismatch", {"string": row.get("string_code"), "found_color": color, "expected_color": expected_color})

        # ── 7. inverter_zone_mismatch ─────────────────────────────────────
        if map_zones:
            zone_labels = {z["zone_label"] for z in map_zones}
            inv_labels_in_map = {z["inverter_label"] for z in map_zones if z.get("inverter_label")}
            detected_labels = {inv["raw_name"] for inv in inverters}
            for label in detected_labels:
                if label not in inv_labels_in_map and inv_labels_in_map:
                    f = finding(
                        "inverter_zone_mismatch", "medium",
                        "Inverter not mapped to any zone",
                        f"Inverter {label} was detected in the design but is not assigned to any map zone.",
                        [label],
                    )
                    findings.append(f)
                    bus.emit("inverter.mismatch", {"type": "zone_missing", "label": label})

        # ── 8. table_map_mismatch ─────────────────────────────────────────
        inverter_count_doc = scan_result.get("inverter_count_doc")
        if inverter_count_doc:
            doc_count = int(float(inverter_count_doc))
            freq_detected = sum(1 for inv in inverters if inv.get("pattern") == "frequency_scan")
            if freq_detected < doc_count:
                missing = doc_count - freq_detected
                inferred_labels = [inv["raw_name"] for inv in inverters if inv.get("pattern") in ("inferred", "gap_fill")]
                f = finding(
                    "table_map_mismatch", "medium",
                    "Table vs map inverter count mismatch",
                    f"Electrical table lists {doc_count} inverters; color map shows {freq_detected} labeled. "
                    f"{missing} inverter(s) are missing from the map: {', '.join(inferred_labels)}.",
                    inferred_labels,
                )
                findings.append(f)
                bus.emit("topology.invalid", {
                    "type": "inverter_count",
                    "table_count": doc_count,
                    "map_count": freq_detected,
                    "missing": inferred_labels,
                })

        return findings
