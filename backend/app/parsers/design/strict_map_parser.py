"""
Backward-compatible entry point for the strict PDF/DXF parser.

Implementation: :mod:`app.parsers.design.unified_layout_parser`.

CLI::

  python -m app.parsers.design.strict_map_parser file1.pdf --json-out report.json
"""
from __future__ import annotations

from app.parsers.design.unified_layout_parser import main, parse_files, run_full, to_frontend_parse_report

__all__ = ["main", "parse_files", "run_full", "to_frontend_parse_report"]

if __name__ == "__main__":
    raise SystemExit(main())
