import glob
import json
import sys

sys.path.insert(0, ".")
from app.modules.epl.bhk_base_map import analyze_layers_across_files

# All available BHK PDFs (FTP uploads + project E_20).
paths = sorted(glob.glob("/opt/wavelync-ftp/uploads/BHK_*.pdf"))
e20 = glob.glob("data/projects/BHK/uploads/*E_20*.pdf")
paths += e20
print("inputs:")
for p in paths:
    print("  ", p)

result = analyze_layers_across_files(paths)

print("\n=== WARNINGS ===")
for w in result["warnings"]:
    print(f"  [{w['severity']}] {w['code']}: {w['detail']}")

for f in result["files"]:
    print(f"\n=== {f['source_file']} | status={f['status']} | page={f.get('page_size')} | "
          f"layers={f.get('layer_count')} | declared_ocgs={len(f.get('declared_ocgs') or [])} ===")
    for L in f["layers"][:18]:
        g = L["geometry"]
        print(f"  [{L['semantic_layer']:14s}] {L['pdf_layer'][:48]:48s} paths={g['paths']:5d} l={g['line_segments']:6d} c={g['curve_segments']:6d} re={g['rect_fills']:5d}")

with open("/tmp/bhk_layer_analysis.json", "w") as fh:
    json.dump(result, fh, indent=2)
print("\nwrote /tmp/bhk_layer_analysis.json")
