#!/usr/bin/env bash
# Create PostgreSQL role 'solarica' + database 'solarica' (public schema).
# Optionally sets the postgres superuser password.
# Run on the server as root (uses sudo -u postgres).
#
# Usage:
#   bash init_solarica_postgres.sh /path/to/db_password_file
#
# The password file must contain one line: the plain-text DB password.
# File is deleted after use.
#
# Env overrides:
#   SOLARICA_DB_NAME           (default: solarica)
#   SOLARICA_DB_USER           (default: solarica)
#   POSTGRES_SUPERUSER_PASSWORD  set to update the postgres system role password
set -euo pipefail

SECRET_FILE="${1:?Usage: $0 <db_password_file>}"
if [ ! -f "$SECRET_FILE" ]; then
  echo "Secret file not found: $SECRET_FILE" >&2
  exit 1
fi

DB_NAME="${SOLARICA_DB_NAME:-solarica}"
DB_USER="${SOLARICA_DB_USER:-solarica}"
PG_SUPERUSER_PW="${POSTGRES_SUPERUSER_PASSWORD:-}"

python3 - "$DB_USER" "$DB_NAME" "$SECRET_FILE" "$PG_SUPERUSER_PW" <<'PY'
import pathlib, random, re, string, subprocess, sys

user, db_name, secret_path, pg_super_pw = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]

if not re.fullmatch(r"[a-z_][a-z0-9_]*", user):
    sys.exit(f"Unsafe DB user name: {user!r}")
if not re.fullmatch(r"[a-zA-Z0-9_]+", db_name):
    sys.exit(f"Unsafe DB name: {db_name!r}")

pw = pathlib.Path(secret_path).read_text(encoding="utf-8").strip("\r\n")
if not pw:
    sys.exit("Empty password in secret file")


def dollar_tag(body: str) -> str:
    """Generate a dollar-quote tag that does not appear in body."""
    for _ in range(30):
        t = "t" + "".join(random.choices(string.ascii_letters, k=14))
        if f"${t}$" not in body:
            return t
    raise SystemExit("Could not build dollar-quote tag")


def psql(db: str, sql: str) -> None:
    subprocess.run(
        ["sudo", "-u", "postgres", "psql", "-v", "ON_ERROR_STOP=1", "-d", db, "-c", sql],
        check=True,
    )


def psql_query(sql: str) -> str:
    return subprocess.run(
        ["sudo", "-u", "postgres", "psql", "-d", "postgres", "-Atq", "-c", sql],
        check=True, capture_output=True, text=True,
    ).stdout.strip()


tag = dollar_tag(pw)
pw_lit = f"${tag}${pw}${tag}$"

# ── Role ─────────────────────────────────────────────────────────────────────
if psql_query(f"SELECT 1 FROM pg_roles WHERE rolname='{user}'") == "1":
    print(f"[db] Role '{user}' exists — updating password.")
    psql("postgres", f"ALTER ROLE {user} LOGIN PASSWORD {pw_lit};")
else:
    print(f"[db] Creating role '{user}'...")
    psql("postgres", f"CREATE ROLE {user} LOGIN PASSWORD {pw_lit};")

# ── Database ──────────────────────────────────────────────────────────────────
if psql_query(f"SELECT 1 FROM pg_database WHERE datname='{db_name}'") == "1":
    print(f"[db] Database '{db_name}' already exists — skipping CREATE.")
else:
    print(f"[db] Creating database '{db_name}' owned by '{user}'...")
    subprocess.run(
        ["sudo", "-u", "postgres", "createdb", "-O", user, db_name],
        check=True,
    )

# ── Schema grants (public) ───────────────────────────────────────────────────
psql(db_name, (
    f"GRANT ALL ON SCHEMA public TO {user}; "
    f"ALTER DEFAULT PRIVILEGES FOR ROLE {user} IN SCHEMA public "
    f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {user}; "
    f"ALTER DEFAULT PRIVILEGES FOR ROLE {user} IN SCHEMA public "
    f"GRANT USAGE, SELECT ON SEQUENCES TO {user};"
))

# ── postgres superuser password (optional) ────────────────────────────────────
if pg_super_pw:
    tag2 = dollar_tag(pg_super_pw)
    pg_pw_lit = f"${tag2}${pg_super_pw}${tag2}$"
    psql("postgres", f"ALTER ROLE postgres PASSWORD {pg_pw_lit};")
    print("[db] postgres superuser password updated.")
else:
    print("[db] POSTGRES_SUPERUSER_PASSWORD not set — postgres role password unchanged.")

print(f"\n[db] OK  database={db_name}  user={user}  schema=public")
print(f"     DATABASE_URL=postgresql://{user}:<password>@127.0.0.1:5432/{db_name}")
PY

rm -f "$SECRET_FILE"
echo "[db] Secret file deleted."
