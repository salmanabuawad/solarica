"""
Solarica Production Deployment Script
Deploys backend files and frontend dist to 185.229.226.37 via SFTP/SSH using paramiko.
"""

import os
import sys
import posixpath
import paramiko

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
    (r"C:\Solarica_OM\backend\app\api\routes\string_scan.py",
     "/opt/solarica/backend/app/api/routes/string_scan.py"),
    (r"C:\Solarica_OM\backend\app\parsers\design\pdf_string_extractor.py",
     "/opt/solarica/backend/app/parsers/design/pdf_string_extractor.py"),
    (r"C:\Solarica_OM\backend\app\parsers\design\extra_patterns.py",
     "/opt/solarica/backend/app/parsers/design/extra_patterns.py"),
    (r"C:\Solarica_OM\backend\app\parsers\design\normalization.py",
     "/opt/solarica/backend/app/parsers/design/normalization.py"),
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

# parser_engine package — uploaded to /opt/solarica/parser_engine and installed via pip
PARSER_ENGINE_FILES = [
    (r"C:\Solarica_OM\parser_engine\pyproject.toml",
     "/opt/solarica/parser_engine/pyproject.toml"),
    (r"C:\Solarica_OM\parser_engine\requirements.txt",
     "/opt/solarica/parser_engine/requirements.txt"),
    # map_parser_v7 package
    (r"C:\Solarica_OM\parser_engine\src\map_parser_v7\__init__.py",
     "/opt/solarica/parser_engine/src/map_parser_v7/__init__.py"),
    (r"C:\Solarica_OM\parser_engine\src\map_parser_v7\cli.py",
     "/opt/solarica/parser_engine/src/map_parser_v7/cli.py"),
    (r"C:\Solarica_OM\parser_engine\src\map_parser_v7\core\engine.py",
     "/opt/solarica/parser_engine/src/map_parser_v7/core/engine.py"),
    (r"C:\Solarica_OM\parser_engine\src\map_parser_v7\core\extractors.py",
     "/opt/solarica/parser_engine/src/map_parser_v7/core/extractors.py"),
    (r"C:\Solarica_OM\parser_engine\src\map_parser_v7\core\progress.py",
     "/opt/solarica/parser_engine/src/map_parser_v7/core/progress.py"),
    (r"C:\Solarica_OM\parser_engine\src\map_parser_v7\schemas\models.py",
     "/opt/solarica/parser_engine/src/map_parser_v7/schemas/models.py"),
    (r"C:\Solarica_OM\parser_engine\src\map_parser_v7\steps\registry.py",
     "/opt/solarica/parser_engine/src/map_parser_v7/steps/registry.py"),
    (r"C:\Solarica_OM\parser_engine\src\map_parser_v7\utils\io.py",
     "/opt/solarica/parser_engine/src/map_parser_v7/utils/io.py"),
    (r"C:\Solarica_OM\parser_engine\src\map_parser_v7\utils\text_patterns.py",
     "/opt/solarica/parser_engine/src/map_parser_v7/utils/text_patterns.py"),
]

FRONTEND_LOCAL_DIST = r"C:\Solarica_OM\frontend\dist"


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
    backend_ok = 0
    backend_fail = 0
    for local_path, remote_path in BACKEND_FILES + PARSER_ENGINE_FILES + DEVICE_REPO_FILES:
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

    commands = [
        (
            "Install ezdxf",
            '/opt/solarica/venv/bin/pip install "ezdxf>=1.1.0" 2>&1'
        ),
        (
            "Create device_repo dirs",
            "mkdir -p /opt/solarica/device_repo/device_repository/solar_db_dump_real"
        ),
        (
            "Create parser_engine sub-package dirs",
            "mkdir -p /opt/solarica/parser_engine/src/map_parser_v7/core "
            "/opt/solarica/parser_engine/src/map_parser_v7/schemas "
            "/opt/solarica/parser_engine/src/map_parser_v7/steps "
            "/opt/solarica/parser_engine/src/map_parser_v7/utils"
        ),
        (
            "Install parser_engine (map_parser_v7)",
            '/opt/solarica/venv/bin/pip install -e /opt/solarica/parser_engine --quiet 2>&1'
        ),
        (
            "Restart solarica-backend",
            "systemctl restart solarica-backend && sleep 3 && systemctl status solarica-backend | head -20"
        ),
    ]

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
                    print(f"    {line}")
            if err:
                for line in err.rstrip().splitlines():
                    print(f"  STDERR: {line}")
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
