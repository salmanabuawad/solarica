from __future__ import annotations

from pathlib import Path

from app.utils import read_json


class SystemCache:
    """
    In-memory cache for per-project system_cache JSON files.

    These JSON files are created by `ensure_system_json_cache(...)` and then used for fast queries
    without reparsing the PDFs.
    """

    def __init__(self, projects_root: Path):
        self.root = Path(projects_root)
        self.projects: dict[str, dict] = {}

    def _system_files(self, project_id: str) -> dict[str, Path]:
        d = self.root / project_id / "system_cache"
        return {
            "sources": d / "system_sources.json",
            "meta": d / "system_meta.json",
            "blocks": d / "system_blocks.json",
            "trackers": d / "system_trackers.json",
            "piers": d / "system_piers.json",
            "pier_type_legend": d / "system_pier_type_legend.json",
            "pier_type_counts": d / "system_pier_type_counts.json",
        }

    def _signature(self, files: dict[str, Path]) -> dict[str, int]:
        return {name: path.stat().st_mtime_ns for name, path in files.items()}

    def load_system(self, project_id: str) -> dict:
        files = self._system_files(project_id)
        obj = {
            "sources": read_json(files["sources"]),
            "meta": read_json(files["meta"]),
            "blocks": read_json(files["blocks"]),
            "trackers": read_json(files["trackers"]),
            "piers": read_json(files["piers"]),
            "pier_type_legend": read_json(files["pier_type_legend"]),
            "pier_type_counts": read_json(files["pier_type_counts"]),
            "_signature": self._signature(files),
        }
        self.projects[project_id] = obj
        return obj

    def get_system(self, project_id: str) -> dict:
        files = self._system_files(project_id)
        cached = self.projects.get(project_id)
        if cached:
            try:
                if cached.get("_signature") == self._signature(files):
                    return cached
            except FileNotFoundError:
                self.projects.pop(project_id, None)
                raise
        return self.load_system(project_id)

