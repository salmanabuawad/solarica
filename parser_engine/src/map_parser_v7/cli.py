from __future__ import annotations

import argparse
import json

import uvicorn

from map_parser_v7.core.engine import ParserEngine


def _print_or_save(data: dict, json_out: str | None) -> None:
    if json_out:
        with open(json_out, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    else:
        print(json.dumps(data, indent=2, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(prog="map-parser-v7")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run")
    p_run.add_argument("--files", nargs="+", required=True)
    p_run.add_argument("--force-ocr", action="store_true")
    p_run.add_argument("--json-out")

    p_step = sub.add_parser("step")
    p_step.add_argument("--step", required=True)
    p_step.add_argument("--files", nargs="+", required=True)
    p_step.add_argument("--resolve-dependencies", action="store_true")
    p_step.add_argument("--force-ocr", action="store_true")
    p_step.add_argument("--json-out")

    p_progress = sub.add_parser("progress")
    p_progress.add_argument("--job-id", required=True)
    p_progress.add_argument("--json-out")

    p_serve = sub.add_parser("serve")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8080)

    args = parser.parse_args()
    engine = ParserEngine()

    if args.cmd == "run":
        data = engine.run_full(args.files, force_ocr=args.force_ocr)
        _print_or_save(data, args.json_out)
    elif args.cmd == "step":
        data = engine.run_step(args.step, args.files, resolve_dependencies=args.resolve_dependencies, force_ocr=args.force_ocr)
        _print_or_save(data, args.json_out)
    elif args.cmd == "progress":
        data = engine.get_progress(args.job_id)
        _print_or_save(data, args.json_out)
    elif args.cmd == "serve":
        uvicorn.run("map_parser_v7.api.server:app", host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()
