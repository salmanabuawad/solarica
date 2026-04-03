from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from map_parser_v7.schemas.models import PipelineResponse, StepRecord
from map_parser_v7.utils.io import ensure_dir, read_json, write_json


class ProgressStore:
    def __init__(self, base_dir: str = ".map_parser_jobs") -> None:
        self.base_dir = Path(base_dir)
        ensure_dir(self.base_dir)

    def path(self, job_id: str) -> Path:
        return self.base_dir / f"{job_id}.json"

    def save(self, state: dict[str, Any]) -> None:
        write_json(self.path(state["job_id"]), state)

    def load(self, job_id: str) -> dict[str, Any]:
        return read_json(self.path(job_id))


class ProgressTracker:
    def __init__(self, job_id: str, steps: list[dict[str, str]], store: ProgressStore) -> None:
        self.store = store
        self.state: dict[str, Any] = {
            "job_id": job_id,
            "status": "running",
            "current_step": None,
            "progress_percent": 0,
            "steps": [StepRecord(id=s["id"], title=s["title"]).model_dump() for s in steps],
            "messages": [],
            "results": {},
        }
        self._started: dict[str, float] = {}
        self.store.save(self.state)

    def message(self, msg: str) -> None:
        self.state["messages"].append(msg)
        self.store.save(self.state)

    def start(self, step_id: str) -> None:
        self.state["current_step"] = step_id
        self._started[step_id] = time.time()
        for s in self.state["steps"]:
            if s["id"] == step_id:
                s["status"] = "running"
        self._update_progress()
        self.store.save(self.state)

    def finish(self, step_id: str, status: str, summary: str | None = None, checkpoint_output: dict[str, Any] | None = None, warnings: list[str] | None = None, errors: list[str] | None = None) -> None:
        dur = int((time.time() - self._started.get(step_id, time.time())) * 1000)
        for s in self.state["steps"]:
            if s["id"] == step_id:
                s["status"] = status
                s["duration_ms"] = dur
                s["summary"] = summary
                s["checkpoint_output"] = checkpoint_output
                s["warnings"] = warnings or []
                s["errors"] = errors or []
        self._update_progress()
        self.store.save(self.state)

    def set_results(self, results: dict[str, Any]) -> None:
        self.state["results"] = results
        self.store.save(self.state)

    def complete(self) -> None:
        self.state["status"] = "done"
        self.state["current_step"] = None
        self.state["progress_percent"] = 100
        self.store.save(self.state)

    def fail(self, message: str) -> None:
        self.state["status"] = "failed"
        self.message(message)
        self.store.save(self.state)

    def _update_progress(self) -> None:
        total = len(self.state["steps"])
        done = sum(1 for s in self.state["steps"] if s["status"] in {"done", "warning", "skipped"})
        self.state["progress_percent"] = int((done / total) * 100) if total else 100
