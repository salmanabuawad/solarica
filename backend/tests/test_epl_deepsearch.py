from __future__ import annotations

import unittest
from pathlib import Path

from app.epl_engine.features import CREATABLE_PROJECT_TYPES, feature_preset
from app.epl_engine.parsers.deepsearch_parser import (
    PdfJob,
    _assets_from_blocks,
    _component_metadata_by_folder,
    _apply_feature_flags,
    detect_project_type,
    prepare_map_data,
    validate_deepsearch_assets,
)


class EplDeepsearchTests(unittest.TestCase):
    def test_feature_presets_keep_optional_assets_non_blocking(self) -> None:
        self.assertEqual(CREATABLE_PROJECT_TYPES, {"fixed_ground", "tracker", "floating", "hybrid"})
        agro = feature_preset("agro_pv")
        self.assertEqual(agro["physical_rows"], "required")
        self.assertEqual(agro["string_zones"], "required")
        self.assertEqual(agro["optimizers"], "required")
        self.assertEqual(agro["cameras"], "optional")
        self.assertEqual(agro["weather_station"], "optional")
        self.assertEqual(agro["weather_sensors"], "optional")

    def test_project_type_detection(self) -> None:
        self.assertEqual(detect_project_type("Qunaitra", "fpv.pdf", "floating FPV SG350HX")["project_type"], "floating")
        self.assertEqual(detect_project_type("bet_haeemeq", "BHK.pdf", "SolarEdge 330kW optimizers")["project_type"], "agro_pv")
        self.assertEqual(detect_project_type("taliia", "ramming.pdf", "Nextracker pier DCCB")["project_type"], "tracker")
        sadii = detect_project_type("sadii", "layout.pdf", "BESS optimizer cameras boundary")
        self.assertEqual(sadii["project_type"], "fixed_ground")

    def test_regex_extraction_and_optional_asset_types(self) -> None:
        job = PdfJob(Path("dummy.pdf"), "bet_haeemeq/BHK_E_30_Communication Plan_rev01.pdf", "bet_haeemeq")
        blocks = [{
            "source_file": job.source_file,
            "project_folder": job.project_folder,
            "page": 1,
            "x": 10.0,
            "y": 20.0,
            "x1": 100.0,
            "y1": 40.0,
            "text_block": "PTZ1 fix CAM CAB3-Radar Site Weather Station POA GMX MT PT1000 DCCB_1.2.3 S.1.2.3 11 STRINGS",
        }]
        assets = _assets_from_blocks(job, blocks)
        types = {asset["asset_type"] for asset in assets}
        self.assertIn("camera_security", types)
        self.assertIn("weather_sensor", types)
        self.assertIn("dccb", types)
        self.assertIn("s_string", types)
        self.assertIn("string_zone", types)
        optional_types = {asset.get("optional_asset_type") for asset in assets}
        self.assertIn("ptz_camera", optional_types)
        self.assertIn("weather_station", optional_types)
        for asset in assets:
            if asset["asset_type"] in {"camera_security", "weather_sensor"}:
                self.assertFalse(asset["required"])
                self.assertTrue(asset["requires_field_validation"])

    def test_bhk_string_zones_are_not_physical_rows(self) -> None:
        job = PdfJob(Path("dummy.pdf"), "bet_haeemeq/BHK_E_20_Electrical Cable Plan_rev01.pdf", "bet_haeemeq")
        assets = _assets_from_blocks(job, [{
            "source_file": job.source_file,
            "project_folder": job.project_folder,
            "page": 1,
            "x": 1.0,
            "y": 1.0,
            "x1": 2.0,
            "y1": 2.0,
            "text_block": "10 STRINGS 11 STRINGS SolarEdge 330kW 1.2.3",
        }])
        self.assertEqual({asset["asset_type"] for asset in assets if "STRINGS" in asset["raw_label"]}, {"string_zone"})
        self.assertNotIn("physical_row", {asset["asset_type"] for asset in assets})

    def test_bhk_metadata_math_and_optional_warnings_do_not_block(self) -> None:
        features = feature_preset("agro_pv")
        assets = []
        for i in range(24):
            assets.append({
                "project_folder": "bet_haeemeq",
                "asset_type": "string_zone",
                "raw_label": "11 STRINGS" if i < 24 else "10 STRINGS",
                "source_file": "bet_haeemeq/BHK_E_20_Electrical Cable Plan_rev01.pdf",
                "x": i,
                "y": i,
            })
        for i in range(24, 26):
            assets.append({
                "project_folder": "bet_haeemeq",
                "asset_type": "string_zone",
                "raw_label": "12 STRINGS",
                "source_file": "bet_haeemeq/BHK_E_20_Electrical Cable Plan_rev01.pdf",
                "x": i,
                "y": i,
            })
        assets.append({"project_folder": "bet_haeemeq", "asset_type": "optimizer_id", "raw_label": "1.2.3", "x": 1, "y": 1})
        assets.append({"project_folder": "bet_haeemeq", "asset_type": "solaredge_inverter", "raw_label": "SE330", "x": 2, "y": 2})
        _apply_feature_flags(assets, {"bet_haeemeq": features})
        issues = validate_deepsearch_assets(
            assets,
            [],
            {"bet_haeemeq": features},
            {"bet_haeemeq": {"project_type_guess": "agro_pv", "confidence": "high"}},
        )
        issue_types = {issue["type"] for issue in issues}
        self.assertIn("missing_optional_cameras", issue_types)
        self.assertIn("missing_optional_weather_station", issue_types)
        self.assertFalse(any(issue["blocking"] for issue in issues if issue["feature"] in {"cameras", "weather_station", "weather_sensors"}))
        self.assertFalse(any(issue["type"] == "string_zone_total_mismatch" for issue in issues))

    def test_tracker_dccb_detection_and_no_bhk_logic(self) -> None:
        job = PdfJob(Path("dummy.pdf"), "taliia/ramming.pdf", "taliia")
        assets = _assets_from_blocks(job, [{
            "source_file": job.source_file,
            "project_folder": job.project_folder,
            "page": 1,
            "x": 5.0,
            "y": 6.0,
            "x1": 10.0,
            "y1": 12.0,
            "text_block": "Nextracker Pier P1 P2 DCCB_1.2.3",
        }])
        self.assertIn("dccb", {asset["asset_type"] for asset in assets})
        issues = validate_deepsearch_assets(
            assets,
            [],
            {"taliia": feature_preset("tracker")},
            {"taliia": {"project_type_guess": "tracker", "confidence": "high"}},
        )
        self.assertFalse(any(issue["type"] == "string_zone_total_mismatch" for issue in issues))

    def test_component_metadata_validates_against_positioned_map_assets(self) -> None:
        documents = [{
            "source_file": "Qunaitra/meta.pdf",
            "project_folder": "Qunaitra",
            "metadata": {
                "component_expectations": [
                    {"asset_type": "sungrow_mvs", "feature": "inverters", "label": "SG350HX", "expected_count": 34, "source": "map_metadata"}
                ]
            },
        }]
        metadata = _component_metadata_by_folder(documents)
        issues = validate_deepsearch_assets(
            [],
            documents,
            {"Qunaitra": feature_preset("floating")},
            {"Qunaitra": {"project_type_guess": "floating", "confidence": "high"}},
            metadata,
        )
        self.assertTrue(any(issue["type"] == "metadata_component_missing_on_map" and issue["severity"] == "error" for issue in issues))

    def test_project_type_metadata_conflict_blocks_epl(self) -> None:
        assets = [
            {"project_folder": "site_a", "asset_type": "floating_fpv", "raw_label": "FPV", "x": 1, "y": 1},
            {"project_folder": "site_a", "asset_type": "sungrow_mvs", "raw_label": "SG350HX", "x": 2, "y": 2},
        ]
        issues = validate_deepsearch_assets(
            assets,
            [],
            {"site_a": feature_preset("fixed_ground")},
            {"site_a": {"project_type_guess": "fixed_ground", "confidence": "high", "site_metadata": {"project_type": "fixed_ground"}}},
        )
        conflict = [issue for issue in issues if issue["type"] == "project_type_metadata_conflict"]
        self.assertEqual(len(conflict), 1)
        self.assertTrue(conflict[0]["blocking"])
        map_data = prepare_map_data({
            "parse_stopped": True,
            "stop_message": conflict[0]["message"],
            "blocking_errors": conflict,
            "enabled_features_by_project_folder": {"site_a": feature_preset("fixed_ground")},
            "assets": assets,
        })
        self.assertTrue(map_data["parse_stopped"])
        self.assertEqual(map_data["layers"], {})


if __name__ == "__main__":
    unittest.main()
