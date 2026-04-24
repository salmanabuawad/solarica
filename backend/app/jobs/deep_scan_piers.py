import argparse
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.pier_scan import (
    build_ns_set_rows,
    deep_scan_pier_types,
    export_labeled_pier_csv,
    export_labeled_pier_json,
    export_labeled_pier_type_map_svg,
    export_pier_group_csv,
    export_pier_group_svg,
    export_pier_symbol_csv,
    export_pier_symbol_svg,
    extract_vector_labeled_piers,
    scan_pier_symbols,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ramming-pdf", required=True)
    parser.add_argument("--page-index", type=int, default=0)
    parser.add_argument("--zoom", type=float, default=2.8)
    parser.add_argument("--out", required=True)
    parser.add_argument("--csv-out")
    parser.add_argument("--svg-out")
    parser.add_argument("--group-csv-out")
    parser.add_argument("--group-svg-out")
    parser.add_argument("--vector-json-out")
    parser.add_argument("--vector-csv-out")
    parser.add_argument("--vector-type-map-svg-out")
    args = parser.parse_args()

    result = deep_scan_pier_types(args.ramming_pdf, page_index=args.page_index, zoom=args.zoom)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    if args.csv_out or args.svg_out or args.group_csv_out or args.group_svg_out:
        scan = scan_pier_symbols(args.ramming_pdf, page_index=args.page_index, zoom=args.zoom)
        if args.csv_out:
            export_pier_symbol_csv(args.csv_out, scan["page_width"], scan["page_height"], scan["symbols"])
        if args.svg_out:
            export_pier_symbol_svg(args.svg_out, scan["page_width"], scan["page_height"], scan["symbols"])
        if args.group_csv_out or args.group_svg_out:
            groups, leftovers = build_ns_set_rows(scan["symbols"])
            if args.group_csv_out:
                export_pier_group_csv(args.group_csv_out, scan["page_width"], scan["page_height"], groups)
            if args.group_svg_out:
                export_pier_group_svg(args.group_svg_out, scan["page_width"], scan["page_height"], groups, leftovers)

    if args.vector_json_out or args.vector_csv_out or args.vector_type_map_svg_out:
        vector_result = extract_vector_labeled_piers(args.ramming_pdf, page_index=args.page_index)
        if args.vector_json_out:
            export_labeled_pier_json(args.vector_json_out, vector_result)
        if args.vector_csv_out:
            export_labeled_pier_csv(args.vector_csv_out, vector_result)
        if args.vector_type_map_svg_out:
            export_labeled_pier_type_map_svg(args.vector_type_map_svg_out, vector_result)
    print(out_path)


if __name__ == "__main__":
    main()
