"""
Solarica Production Deployment Script
Deploys backend files and frontend dist to 185.229.226.37 via SFTP/SSH using paramiko.
"""

import os
import sys
import posixpath
import paramiko

# Repository root (directory that contains backend/, frontend/, deploy/, parser_engine/)
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))

HOST = "185.229.226.37"
PORT = 22
USER = "root"
PASS = "KortexDigital1342#"

BACKEND_REMOTE_BASE = "/opt/solarica/backend/app"
FRONTEND_REMOTE_DIST = "/opt/solarica/frontend/dist"

BACKEND_FILES = [
    # (local_windows_path, remote_posix_path)
    (r"C:\Solarica_OM\backend\app\models\company.py",
     "/opt/solarica/backend/app/models/company.py"),
    (r"C:\Solarica_OM\backend\app\repositories\company_repo.py",
     "/opt/solarica/backend/app/repositories/company_repo.py"),
    (r"C:\Solarica_OM\backend\app\api\routes\companies.py",
     "/opt/solarica/backend/app/api/routes/companies.py"),
    (r"C:\Solarica_OM\backend\app\parsers\design\dxf_parser.py",
     "/opt/solarica/backend/app/parsers/design/dxf_parser.py"),
    (r"C:\Solarica_OM\backend\app\models\__init__.py",
     "/opt/solarica/backend/app/models/__init__.py"),
    (r"C:\Solarica_OM\backend\app\models\project.py",
     "/opt/solarica/backend/app/models/project.py"),
    (r"C:\Solarica_OM\backend\app\repositories\project_repo.py",
     "/opt/solarica/backend/app/repositories/project_repo.py"),
    (r"C:\Solarica_OM\backend\app\api\routes\projects.py",
     "/opt/solarica/backend/app/api/routes/projects.py"),
    (r"C:\Solarica_OM\backend\app\api\routes\project_files.py",
     "/opt/solarica/backend/app/api/routes/project_files.py"),
    (r"C:\Solarica_OM\backend\app\api\routes\string_scan.py",
     "/opt/solarica/backend/app/api/routes/string_scan.py"),
    (r"C:\Solarica_OM\backend\app\parsers\design\strict_map_parser.py",
     "/opt/solarica/backend/app/parsers/design/strict_map_parser.py"),
    (r"C:\Solarica_OM\backend\app\parsers\design\unified_layout_parser.py",
     "/opt/solarica/backend/app/parsers/design/unified_layout_parser.py"),
    (r"C:\Solarica_OM\backend\app\parsers\design\unified_scan_adapter.py",
     "/opt/solarica/backend/app/parsers/design/unified_scan_adapter.py"),
    (r"C:\Solarica_OM\backend\app\api\routes\parser_engine.py",
     "/opt/solarica/backend/app/api/routes/parser_engine.py"),
    (r"C:\Solarica_OM\backend\app\services\output_validation.py",
     "/opt/solarica/backend/app/services/output_validation.py"),
    (r"C:\Solarica_OM\backend\app\main.py",
     "/opt/solarica/backend/app/main.py"),
    (r"C:\Solarica_OM\backend\app\schemas\project.py",
     "/opt/solarica/backend/app/schemas/project.py"),
    (r"C:\Solarica_OM\backend\app\core\database.py",
     "/opt/solarica/backend/app/core/database.py"),
    # Device inventory repository
    (r"C:\Solarica_OM\backend\app\models\device_repo.py",
     "/opt/solarica/backend/app/models/device_repo.py"),
    (r"C:\Solarica_OM\backend\app\repositories\device_repo.py",
     "/opt/solarica/backend/app/repositories/device_repo.py"),
    (r"C:\Solarica_OM\backend\app\api\routes\device_inventory.py",
     "/opt/solarica/backend/app/api/routes/device_inventory.py"),
    (r"C:\Solarica_OM\backend\app\db\seed.py",
     "/opt/solarica/backend/app/db/seed.py"),
    # Solar catalog
    (r"C:\Solarica_OM\backend\app\models\solar_catalog.py",
     "/opt/solarica/backend/app/models/solar_catalog.py"),
    (r"C:\Solarica_OM\backend\app\repositories\solar_catalog_repo.py",
     "/opt/solarica/backend/app/repositories/solar_catalog_repo.py"),
    (r"C:\Solarica_OM\backend\app\api\routes\solar_catalog.py",
     "/opt/solarica/backend/app/api/routes/solar_catalog.py"),
    # Field config
    (r"C:\Solarica_OM\backend\app\models\field_config.py",
     "/opt/solarica/backend/app/models/field_config.py"),
    (r"C:\Solarica_OM\backend\app\repositories\field_config_repo.py",
     "/opt/solarica/backend/app/repositories/field_config_repo.py"),
    (r"C:\Solarica_OM\backend\app\api\routes\field_config.py",
     "/opt/solarica/backend/app/api/routes/field_config.py"),
]

# device_repo data files
DEVICE_REPO_FILES = [
    (r"C:\Solarica_OM\device_repo\device_repository\repository.json",
     "/opt/solarica/device_repo/device_repository/repository.json"),
    # solar_db_dump_real catalog CSVs
    (r"C:\Solarica_OM\device_repo\device_repository\solar_db_dump_real\sources.csv",
     "/opt/solarica/device_repo/device_repository/solar_db_dump_real/sources.csv"),
    (r"C:\Solarica_OM\device_repo\device_repository\solar_db_dump_real\asset_categories.csv",
     "/opt/solarica/device_repo/device_repository/solar_db_dump_real/asset_categories.csv"),
    (r"C:\Solarica_OM\device_repo\device_repository\solar_db_dump_real\manufacturers.csv",
     "/opt/solarica/device_repo/device_repository/solar_db_dump_real/manufacturers.csv"),
    (r"C:\Solarica_OM\device_repo\device_repository\solar_db_dump_real\device_models.csv",
     "/opt/solarica/device_repo/device_repository/solar_db_dump_real/device_models.csv"),
    (r"C:\Solarica_OM\device_repo\device_repository\solar_db_dump_real\device_specs.csv",
     "/opt/solarica/device_repo/device_repository/solar_db_dump_real/device_specs.csv"),
    (r"C:\Solarica_OM\device_repo\device_repository\solar_db_dump_real\vulnerabilities.csv",
     "/opt/solarica/device_repo/device_repository/solar_db_dump_real/vulnerabilities.csv"),
    (r"C:\Solarica_OM\device_repo\device_repository\solar_db_dump_real\vulnerability_matches.csv",
     "/opt/solarica/device_repo/device_repository/solar_db_dump_real/vulnerability_matches.csv"),
]

PARSER_ENGINE_REMOTE_BASE = "/opt/solarica/parser_engine"

# Directory names skipped while walking parser_engine/src (and pruned from os.walk)
_PARSER_ENGINE_SKIP_DIRS = frozenset({
    "__pycache__", ".git", ".venv", "venv", ".mypy_cache", ".pytest_cache", "node_modules",
})

# Optional package-root files under parser_engine/
_PARSER_ENGINE_ROOT_FILES = (
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "README.md",
    "requirements.txt",
)


def collect_parser_engine_uploads() -> tuple[list[tuple[str, str]], bool]:
    """
    Build (local_path, remote_posix_path) for parser_engine.

    - Uploads package metadata files at parser_engine/ root if present.
    - Recursively uploads parser_engine/src/** (exclusive source of map_parser_v7).
    - Does NOT upload parser_engine/backend/ (local stub tree).

    Returns (pairs, has_map_parser_v7) where has_map_parser_v7 is True iff
    src/map_parser_v7/__init__.py exists locally (so pip install -e is safe).
    """
    base = os.path.join(REPO_ROOT, "parser_engine")
    pairs: list[tuple[str, str]] = []
    if not os.path.isdir(base):
        return pairs, False

    for name in _PARSER_ENGINE_ROOT_FILES:
        local_path = os.path.join(base, name)
        if os.path.isfile(local_path):
            pairs.append(
                (local_path, posixpath.join(PARSER_ENGINE_REMOTE_BASE, name.replace("\\", "/")))
            )

    src_root = os.path.join(base, "src")
    if os.path.isdir(src_root):
        for dirpath, dirnames, filenames in os.walk(src_root):
            dirnames[:] = sorted(
                d for d in dirnames
                if d not in _PARSER_ENGINE_SKIP_DIRS and not d.startswith(".")
            )
            for filename in sorted(filenames):
                if filename.endswith((".pyc", ".pyo")):
                    continue
                local_file = os.path.join(dirpath, filename)
                rel_from_engine = os.path.relpath(local_file, base)
                rel_posix = rel_from_engine.replace("\\", "/")
                remote = posixpath.join(PARSER_ENGINE_REMOTE_BASE, rel_posix)
                pairs.append((local_file, remote))

    v7_init = os.path.join(base, "src", "map_parser_v7", "__init__.py")
    return pairs, os.path.isfile(v7_init)


FRONTEND_LOCAL_DIST = os.path.join(REPO_ROOT, "frontend", "dist")


def _print_remote_line(prefix: str, line: str) -> None:
    """Avoid UnicodeEncodeError on Windows consoles when printing SSH output."""
    text = f"{prefix}{line}"
    try:
        print(text)
    except UnicodeEncodeError:
        enc = getattr(sys.stdout, "encoding", None) or "utf-8"
        print(text.encode(enc, errors="replace").decode(enc))


def sftp_makedirs(sftp, remote_path):
    """Recursively create remote directories if they do not exist."""
    parts = remote_path.split("/")
    current = ""
    for part in parts:
        if not part:
            current = "/"
            continue
        current = posixpath.join(current, part)
        try:
            sftp.stat(current)
        except FileNotFoundError:
            try:
                sftp.mkdir(current)
                print(f"    mkdir {current}")
            except Exception as e:
                # May already exist due to race or symlink; ignore
                pass


def deploy():
    print("=" * 60)
    print("Solarica Production Deployment")
    print(f"Target: {USER}@{HOST}")
    print("=" * 60)

    # --- Connect ---
    print("\n[1/4] Connecting to server...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(HOST, port=PORT, username=USER, password=PASS,
                       timeout=30, banner_timeout=30, auth_timeout=30)
        print(f"      Connected to {HOST}")
    except Exception as e:
        print(f"      FAILED to connect: {e}")
        sys.exit(1)

    sftp = client.open_sftp()

    # --- Upload backend files ---
    print("\n[2/4] Uploading backend files...")
    parser_engine_upload, parser_engine_has_v7 = collect_parser_engine_uploads()
    if not parser_engine_upload:
        print(
            "  (Note: parser_engine/ missing or has no deployable files — "
            "nothing uploaded under /opt/solarica/parser_engine.)"
        )
    elif not parser_engine_has_v7:
        print(
            "  (Note: parser_engine/src/map_parser_v7/ not found (no __init__.py) — "
            "uploaded package root / src/* only; pip install -e will be skipped. "
            "Add the full package under parser_engine/src/map_parser_v7/ to sync it.)"
        )
    backend_ok = 0
    backend_fail = 0
    for local_path, remote_path in BACKEND_FILES + parser_engine_upload + DEVICE_REPO_FILES:
        remote_dir = posixpath.dirname(remote_path)
        sftp_makedirs(sftp, remote_dir)
        try:
            sftp.put(local_path, remote_path)
            size = os.path.getsize(local_path)
            print(f"  [OK]   {remote_path}  ({size:,} bytes)")
            backend_ok += 1
        except Exception as e:
            print(f"  [FAIL] {remote_path}  ERROR: {e}")
            backend_fail += 1

    print(f"\n  Backend: {backend_ok} succeeded, {backend_fail} failed")

    # --- Upload frontend dist (recursive) ---
    print("\n[3/4] Uploading frontend dist (recursive)...")

    # Ensure remote dist dir exists
    sftp_makedirs(sftp, FRONTEND_REMOTE_DIST)

    frontend_ok = 0
    frontend_fail = 0

    for root, dirs, files in os.walk(FRONTEND_LOCAL_DIST):
        # Compute relative path from local dist root
        rel_root = os.path.relpath(root, FRONTEND_LOCAL_DIST)
        if rel_root == ".":
            remote_dir = FRONTEND_REMOTE_DIST
        else:
            # Convert Windows backslashes to posix
            rel_posix = rel_root.replace("\\", "/")
            remote_dir = posixpath.join(FRONTEND_REMOTE_DIST, rel_posix)

        sftp_makedirs(sftp, remote_dir)

        for filename in files:
            local_file = os.path.join(root, filename)
            remote_file = posixpath.join(remote_dir, filename)
            try:
                sftp.put(local_file, remote_file)
                size = os.path.getsize(local_file)
                print(f"  [OK]   {remote_file}  ({size:,} bytes)")
                frontend_ok += 1
            except Exception as e:
                print(f"  [FAIL] {remote_file}  ERROR: {e}")
                frontend_fail += 1

    print(f"\n  Frontend: {frontend_ok} succeeded, {frontend_fail} failed")

    # --- Post-deploy commands ---
    print("\n[4/4] Running post-deploy commands on server...")

    commands: list[tuple[str, str]] = [
        (
            "Install pdfplumber + ezdxf",
            '/opt/solarica/venv/bin/pip install pdfplumber "ezdxf>=1.1.0" 2>&1'
        ),
        (
            "Create device_repo dirs",
            "mkdir -p /opt/solarica/device_repo/device_repository/solar_db_dump_real"
        ),
    ]
    if parser_engine_has_v7:
        commands.append((
            "Create parser_engine map_parser_v7 dirs",
            "mkdir -p /opt/solarica/parser_engine/src/map_parser_v7/core "
            "/opt/solarica/parser_engine/src/map_parser_v7/schemas "
            "/opt/solarica/parser_engine/src/map_parser_v7/steps "
            "/opt/solarica/parser_engine/src/map_parser_v7/utils"
        ))
        commands.append((
            "Install parser_engine (map_parser_v7)",
            '/opt/solarica/venv/bin/pip install -e /opt/solarica/parser_engine --quiet 2>&1'
        ))
    elif parser_engine_upload:
        print(
            "\n  (Skipping pip install -e /opt/solarica/parser_engine — "
            "map_parser_v7 sources not in this workspace.)"
        )

    commands.append((
        "Restart solarica-backend",
        "systemctl restart solarica-backend && sleep 3 && systemctl status solarica-backend | head -20"
    ))

    for label, cmd in commands:
        print(f"\n  --- {label} ---")
        print(f"  CMD: {cmd}")
        try:
            stdin, stdout, stderr = client.exec_command(cmd, timeout=60)
            out = stdout.read().decode(errors="replace")
            err = stderr.read().decode(errors="replace")
            exit_code = stdout.channel.recv_exit_status()
            if out:
                for line in out.rstrip().splitlines():
                    _print_remote_line("    ", line)
            if err:
                for line in err.rstrip().splitlines():
                    _print_remote_line("  STDERR: ", line)
            print(f"  Exit code: {exit_code}")
        except Exception as e:
            print(f"  FAILED: {e}")

    sftp.close()
    client.close()

    # --- Summary ---
    print("\n" + "=" * 60)
    print("DEPLOYMENT SUMMARY")
    print("=" * 60)
    print(f"  Backend files : {backend_ok} OK, {backend_fail} FAILED")
    print(f"  Frontend files: {frontend_ok} OK, {frontend_fail} FAILED")
    total_fail = backend_fail + frontend_fail
    if total_fail == 0:
        print("  Overall       : SUCCESS")
    else:
        print(f"  Overall       : PARTIAL — {total_fail} file(s) failed")
    print("=" * 60)


if __name__ == "__main__":
    deploy()
