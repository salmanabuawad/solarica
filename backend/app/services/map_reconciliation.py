"""
MapReconciliationService — reconciles electrical table data vs color map layout.
"""
from __future__ import annotations
from typing import Any
from app.services.event_bus import EventBus


class MapReconciliationService:
    """
    Cross-checks the two data sources in a color-map design document:
    1. Electrical schedule table (inverter count, MPPT, string counts)
    2. Layout color map (inverter zones, string label positions)
    """

    def reconcile(
        self,
        scan_result: dict[str, Any],
        map_zones: list[dict] | None = None,
        bus: EventBus | None = None,
    ) -> dict[str, Any]:
        bus = bus or EventBus()
        issues: list[dict] = []
        summary: dict[str, Any] = {}

        inverters = scan_result.get("inverters", [])
        mppt_channels = scan_result.get("mppt_channels", [])
        icb_zones = scan_result.get("icb_zones", [])
        inverter_count_doc = scan_result.get("inverter_count_doc")
        total_strings_doc = scan_result.get("total_strings_doc")

        # ── Table data ───────────────────────────────────────────────────
        table_inverter_count = int(float(inverter_count_doc)) if inverter_count_doc else None
        table_string_count = int(float(total_strings_doc)) if total_strings_doc else None

        # ── Map data ─────────────────────────────────────────────────────
        map_inverter_count = sum(1 for inv in inverters if inv.get("pattern") == "frequency_scan")
        map_string_total = sum(inv.get("strings_count", 0) for inv in inverters)

        summary["table_inverter_count"] = table_inverter_count
        summary["map_inverter_count"] = map_inverter_count
        summary["map_string_total"] = map_string_total
        summary["table_string_count"] = table_string_count
        summary["icb_zones_detected"] = [z["label"] for z in icb_zones]
        summary["mppt_groups_detected"] = len(set(
            f"{c['icb_zone']}_{c['dc_terminal_no']}_{c['mppt_no']}"
            for c in mppt_channels
        )) if mppt_channels else 0

        # Check inverter count match
        if table_inverter_count and map_inverter_count != table_inverter_count:
            issues.append({
                "code": "table_map_inverter_count",
                "severity": "medium",
                "message": f"Table: {table_inverter_count} inverters, map labels: {map_inverter_count}",
            })
            bus.emit("topology.invalid", {"type": "inverter_count_reconcile",
                                           "table": table_inverter_count, "map": map_inverter_count})

        # Check string count match
        if table_string_count and abs(map_string_total - table_string_count) > 5:
            issues.append({
                "code": "table_map_string_count",
                "severity": "medium",
                "message": f"Table: {table_string_count} strings, map detected: {map_string_total}",
            })
            bus.emit("topology.invalid", {"type": "string_count_reconcile",
                                           "table": table_string_count, "map": map_string_total})

        # Check ICB zones have corresponding inverters
        icb_zone_labels = {z["zone_id"] for z in icb_zones}
        inv_sections = set(inv["raw_name"].split(".")[0] for inv in inverters)
        for zone_id in icb_zone_labels:
            section = zone_id.split(".")[0]
            if section not in inv_sections:
                issues.append({
                    "code": "icb_zone_no_inverters",
                    "severity": "low",
                    "message": f"ICB-area-{zone_id} has no inverters detected in that section",
                })

        summary["issues"] = issues
        summary["status"] = "ok" if not issues else "issues_found"
        return summary
