"""Watch import folder and auto-import PVPM export files."""

import logging
import threading
from pathlib import Path

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from config import settings
from database import get_connection
from parsers import parse_file

logger = logging.getLogger("ivcurve.file_watcher")
_observer: Observer | None = None


def _import_file(path: Path) -> bool:
    """Try to import a single file. Returns True if imported successfully."""
    try:
        m = parse_file(path)
        if not m:
            return False
        # Convert to dict for insert (reuse parse_import_file logic)
        from parsers import parse_import_file
        content = path.read_bytes()
        result = parse_import_file(content, path.name, path.suffix)
        if not result:
            return False
        with get_connection() as conn:
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO measurements (
                            measured_at, device_serial, irradiance_sensor_serial, customer, module_type, remarks,
                            ppk, rs, rp, voc, isc, vpmax, ipmax, pmax, ff, eeff, tmod, tcell, source_file
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                        """,
                        (
                            result.get("measured_at"),
                            result.get("device_serial"),
                            result.get("sensor_serial") or result.get("irradiance_sensor_serial"),
                            result.get("customer"),
                            result.get("module_type"),
                            result.get("remarks"),
                            result.get("ppk"),
                            result.get("rs"),
                            result.get("rp"),
                            result.get("voc"),
                            result.get("isc"),
                            result.get("vpmax"),
                            result.get("ipmax"),
                            result.get("pmax"),
                            result.get("fill_factor") or result.get("ff"),
                            result.get("eeff"),
                            result.get("tmod"),
                            result.get("tcell"),
                            path.name,
                        ),
                    )
                    mid = cur.fetchone()[0]
                    iv_curve = result.get("iv_curve") or []
                    for i, pt in enumerate(iv_curve):
                        p = pt if isinstance(pt, dict) else {"voltage": pt.voltage, "current": pt.current}
                        cur.execute(
                            "INSERT INTO iv_curve_points (measurement_id, point_index, voltage, current) VALUES (%s, %s, %s, %s)",
                            (mid, i, p.get("voltage", 0), p.get("current", 0)),
                        )
                conn.commit()
                logger.info("Auto-imported %s -> measurement #%s", path.name, mid)
                return True
            except Exception as e:
                conn.rollback()
                logger.warning("Failed to import %s: %s", path.name, e)
                return False
    except Exception as e:
        logger.warning("Parse/import failed for %s: %s", path, e)
        return False


class _PVPMImportHandler(FileSystemEventHandler):
    SUFFIXES = {".xls", ".xlsx", ".csv", ".txt", ".asc", ".dat"}

    def on_created(self, event):
        if event.is_directory:
            return
        path = Path(event.src_path)
        if path.suffix.lower() in self.SUFFIXES:
            # Small delay so file is fully written
            threading.Timer(1.0, lambda: _import_file(path)).start()


def start_file_watcher():
    """Start watching the import folder for new files."""
    global _observer
    folder = Path(settings.import_folder).resolve()
    if not folder.exists():
        folder.mkdir(parents=True, exist_ok=True)
    _observer = Observer()
    _observer.schedule(_PVPMImportHandler(), str(folder), recursive=False)
    _observer.start()
    logger.info("File watcher started on %s", folder)


def stop_file_watcher():
    """Stop the file watcher."""
    global _observer
    if _observer:
        _observer.stop()
        _observer.join()
        _observer = None
        logger.info("File watcher stopped")
