import argparse
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.system_artifacts import ensure_system_json_cache  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache-dir", required=True, help="Directory to write system_*.json files into")
    parser.add_argument("--vector-json", required=True, help="piers_vector_labeled.json (vector-based pier list)")
    parser.add_argument("--ramming-pdf", required=True, help="Ramming plan PDF (ROW/TRK + BLOCK labels)")
    parser.add_argument("--pier-legend-image", default="", help="Optional legend image (png/jpg) to OCR pier type descriptions")
    parser.add_argument("--tesseract-exe", default="", help="Optional tesseract.exe path (if not on PATH)")
    parser.add_argument("--force", action="store_true", help="Rebuild even if cache exists")
    args = parser.parse_args()

    rebuilt = ensure_system_json_cache(
        cache_dir=args.cache_dir,
        vector_json_path=args.vector_json,
        ramming_pdf_path=args.ramming_pdf,
        legend_image_path=(args.pier_legend_image or None),
        tesseract_exe=(args.tesseract_exe or None),
        force=bool(args.force),
    )
    print(args.cache_dir)
    if rebuilt:
        print("rebuilt")
    else:
        print("cache_ok")


if __name__ == "__main__":
    main()

