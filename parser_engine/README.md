# parser_engine (map_parser_v7)

Deploy uploads everything under `src/` plus `pyproject.toml`, `requirements.txt`, and other package root files to `/opt/solarica/parser_engine` on the server.

Place the **`map_parser_v7`** package at:

`src/map_parser_v7/` (with `__init__.py`, `core/engine.py`, etc.)

The repo root folder `backend/` here is **not** deployed — it is a local stub only.
