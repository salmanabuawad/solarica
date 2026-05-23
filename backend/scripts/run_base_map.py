import csv
import glob
import json
import os
import sys

sys.path.insert(0, ".")
from app.modules.epl.bhk_base_map import build_base_map, analyze_layers_across_files

OUT = "/tmp/bhk_base_map"
os.makedirs(OUT, exist_ok=True)

paths = sorted(glob.glob("/opt/wavelync-ftp/uploads/BHK_*.pdf"))
paths += glob.glob("data/projects/BHK/uploads/*E_20*.pdf")[:1]

# Phase 1 warnings feed into the combined warnings file.
phase1 = analyze_layers_across_files(paths)
model = build_base_map(paths)
print("status:", model.get("status"))
print("summary:", model.get("summary"))


def write_csv(name, header, rows):
    with open(os.path.join(OUT, name), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


# base_map_model.json
with open(os.path.join(OUT, "base_map_model.json"), "w") as f:
    json.dump(model, f, indent=2)

rows = model.get("rows", [])

write_csv("physical_rows.csv",
          ["row_id", "row_number", "south_x", "south_y", "north_x", "north_y", "length", "panel_count", "pier_count", "tracker_count", "confidence"],
          [[r["row_id"], r["row_number"], *r["south_point"], *r["north_point"], r["length"], r["panel_count"], r["pier_count"], r["tracker_count"], r["confidence"]] for r in rows])

write_csv("panels.csv", ["panel_id", "row_id", "row_number", "panel_number", "cx", "cy"],
          [[p["panel_id"], r["row_id"], r["row_number"], p["panel_number"], p["cx"], p["cy"]] for r in rows for p in r["panels"]])

write_csv("piers.csv", ["pier_id", "row_id", "row_number", "pier_number", "x", "y"],
          [[p["pier_id"], r["row_id"], r["row_number"], p["pier_number"], p["x"], p["y"]] for r in rows for p in r["piers"]])

write_csv("trackers.csv", ["tracker_id", "tracker_number", "row_id", "row_number"],
          [[t["tracker_id"], t["tracker_number"], r["row_id"], r["row_number"]] for r in rows for t in r["trackers"]])

write_csv("row_panel_mapping.csv", ["row_id", "panel_id", "panel_number"],
          [[r["row_id"], p["panel_id"], p["panel_number"]] for r in rows for p in r["panels"]])
write_csv("row_pier_mapping.csv", ["row_id", "pier_id", "pier_number"],
          [[r["row_id"], p["pier_id"], p["pier_number"]] for r in rows for p in r["piers"]])
write_csv("row_tracker_mapping.csv", ["row_id", "tracker_id"],
          [[r["row_id"], t["tracker_id"]] for r in rows for t in r["trackers"]])

all_warn = phase1.get("warnings", []) + model.get("warnings", [])
write_csv("extraction_warnings.csv", ["code", "severity", "detail"],
          [[w["code"], w["severity"], w["detail"]] for w in all_warn])

print("\nfiles written to", OUT)
for fn in sorted(os.listdir(OUT)):
    print("  ", fn, os.path.getsize(os.path.join(OUT, fn)), "bytes")

print("\nfirst 3 rows:")
for r in rows[:3]:
    print(f"  {r['row_id']} #{r['row_number']} panels={r['panel_count']} piers={r['pier_count']} trackers={r['tracker_count']} len={r['length']}")
print("...")
for r in rows[-2:]:
    print(f"  {r['row_id']} #{r['row_number']} panels={r['panel_count']} piers={r['pier_count']} trackers={r['tracker_count']}")
print("\nwarnings:")
for w in all_warn:
    print(f"  [{w['severity']}] {w['code']}: {w['detail']}")
