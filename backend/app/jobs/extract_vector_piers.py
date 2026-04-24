import argparse
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.pier_scan import (
    export_labeled_pier_csv,
    export_labeled_pier_json,
    export_labeled_pier_type_map_svg,
    extract_vector_labeled_piers,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ramming-pdf", required=True)
    parser.add_argument("--page-index", type=int, default=0)
    parser.add_argument("--json-out", required=True)
    parser.add_argument("--csv-out")
    parser.add_argument("--type-map-svg-out")
    args = parser.parse_args()

    result = extract_vector_labeled_piers(args.ramming_pdf, page_index=args.page_index)
    export_labeled_pier_json(args.json_out, result)
    if args.csv_out:
        export_labeled_pier_csv(args.csv_out, result)
    if args.type_map_svg_out:
        export_labeled_pier_type_map_svg(args.type_map_svg_out, result)
    print(args.json_out)


if __name__ == "__main__":
    main()
