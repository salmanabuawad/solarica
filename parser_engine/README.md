# parser_engine (map_parser_v7)

The **`map_parser_v7`** package lives under **`src/map_parser_v7/`**. It implements the `ParserEngine` step flow used by Solarica **scan-stream** for **DXF-only** jobs (no explicit regex): steps run on the backend, and **`step_extract_strings`** calls `app.parsers.design.dxf_parser.parse_dxf_path`.

Deploy uploads everything under `src/` plus `pyproject.toml`, `requirements.txt`, etc., to `/opt/solarica/parser_engine`, then runs `pip install -e`.

The folder **`parser_engine/backend/`** is **not** deployed (legacy stub only).
