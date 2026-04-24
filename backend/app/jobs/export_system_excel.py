import argparse
import sys
from pathlib import Path

import pandas as pd

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.system_artifacts import SYSTEM_CACHE_FILES, build_pier_type_legend_df, build_system_tables, cache_paths, ensure_system_json_cache
from app.utils import read_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--vector-json", required=True, help="Output from extract_vector_piers (piers_vector_labeled.json)")
    parser.add_argument("--ramming-pdf", required=True, help="Ramming plan PDF used for ROW/TRK and BLOCK labels")
    parser.add_argument("--out", required=True, help="Output .xlsx path")
    parser.add_argument("--pier-legend-image", default="", help="Optional legend image (png/jpg) to OCR pier type descriptions")
    parser.add_argument("--tesseract-exe", default="", help="Optional tesseract.exe path (if not on PATH)")
    parser.add_argument("--cache-dir", default="", help="Optional directory for system_*.json cache. If present, export uses cache and only parses PDFs when cache is missing/outdated.")
    args = parser.parse_args()

    if args.cache_dir:
        ensure_system_json_cache(
            cache_dir=args.cache_dir,
            vector_json_path=args.vector_json,
            ramming_pdf_path=args.ramming_pdf,
            legend_image_path=(args.pier_legend_image or None),
            tesseract_exe=(args.tesseract_exe or None),
        )
        paths = cache_paths(args.cache_dir)
        meta_df = pd.DataFrame([read_json(paths["meta"])])
        block_df = pd.DataFrame(read_json(paths["blocks"]))
        tracker_df = pd.DataFrame(read_json(paths["trackers"]))
        piers_df = pd.DataFrame(read_json(paths["piers"]))
        legend_df = pd.DataFrame(read_json(paths["pier_type_legend"]))
        pier_type_counts_df = pd.DataFrame(read_json(paths["pier_type_counts"]))
    else:
        meta_df, block_df, tracker_df, piers_df = build_system_tables(args.vector_json, args.ramming_pdf)
        legend_df = build_pier_type_legend_df(
            pier_types=piers_df.get("pier_type", []),
            legend_image=args.pier_legend_image or None,
            tesseract_exe=args.tesseract_exe or None,
        )
        pier_type_counts_df = (
            piers_df["pier_type"]
            .astype(str)
            .str.upper()
            .value_counts()
            .rename_axis("pier_type")
            .reset_index(name="count")
            .sort_values("pier_type", kind="stable")
            .reset_index(drop=True)
        )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        meta_df.to_excel(writer, sheet_name="Meta", index=False)
        block_df.to_excel(writer, sheet_name="Blocks", index=False)
        tracker_df.to_excel(writer, sheet_name="Trackers", index=False)
        piers_df.to_excel(writer, sheet_name="Piers", index=False)
        legend_df.to_excel(writer, sheet_name="PierTypeLegend", index=False)
        pier_type_counts_df.to_excel(writer, sheet_name="PierTypeCounts", index=False)

    print(out_path)


if __name__ == "__main__":
    main()
