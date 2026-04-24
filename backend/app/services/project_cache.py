from pathlib import Path
from app.utils import read_json
from app.services.project_artifacts import ensure_project_artifacts

class ProjectCache:
    def __init__(self, root):
        self.root = Path(root)
        self.projects = {}

    def _project_files(self, project_id):
        p = self.root / project_id
        return {
            "summary": p / "summary.json",
            "blocks": p / "blocks.json",
            "trackers": p / "trackers.json",
            "piers": p / "piers.json",
            "zoom_targets": p / "zoom_targets.json",
            "drawing_bundles": p / "drawing_bundles.json",
        }

    def _signature(self, files):
        return {name: path.stat().st_mtime_ns for name, path in files.items()}

    def load_project(self, project_id):
        files = self._project_files(project_id)
        project = {
            "summary": read_json(files["summary"]),
            "blocks": read_json(files["blocks"]),
            "trackers": read_json(files["trackers"]),
            "piers": read_json(files["piers"]),
            "zoom_targets": read_json(files["zoom_targets"]),
            "drawing_bundles": read_json(files["drawing_bundles"]),
            "_signature": self._signature(files),
        }
        self.projects[project_id] = project
        return project

    def get_project(self, project_id):
        files = self._project_files(project_id)
        cached = self.projects.get(project_id)
        if cached:
            try:
                if cached.get("_signature") == self._signature(files):
                    return cached
            except FileNotFoundError:
                self.projects.pop(project_id, None)
                raise
        try:
            return self.load_project(project_id)
        except FileNotFoundError:
            # If artifacts are missing, attempt a rebuild from manifest.json (if present),
            # then try once more.
            project_dir = self.root / project_id
            ensure_project_artifacts(project_dir)
            return self.load_project(project_id)

    def list_projects(self):
        projects = []
        if not self.root.exists():
            return projects
        for project_dir in sorted(self.root.iterdir()):
            if not project_dir.is_dir():
                continue
            summary_path = project_dir / "summary.json"
            if not summary_path.exists():
                continue
            try:
                summary = self.get_project(project_dir.name)["summary"]
            except Exception:
                continue
            projects.append({
                "project_id": project_dir.name,
                "summary": summary,
            })
        return projects
