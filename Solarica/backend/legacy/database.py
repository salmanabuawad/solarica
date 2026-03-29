"""Database connection and initialization. Supports PostgreSQL and SQLite."""
import os
import re
import sqlite3
from pathlib import Path

from config import settings

_use_sqlite = False
_pg_pool = None  # psycopg2 ThreadedConnectionPool (PostgreSQL only)


def _get_pg_pool():
    global _pg_pool
    if _pg_pool is None:
        from psycopg2 import pool as pg_pool
        _pg_pool = pg_pool.ThreadedConnectionPool(1, 8, settings.database_url)
    return _pg_pool


def _adapt_sql_for_sqlite(sql: str) -> str:
    """Convert PostgreSQL %(name)s and %s to SQLite :name and ?."""
    sql = re.sub(r"%\((\w+)\)s", r":\1", sql)
    sql = sql.replace("%s", "?")
    return sql


def _resolve_sqlite_path(url: str) -> str:
    path = url.replace("sqlite:///", "").strip()
    if path.startswith("./"):
        path = str(Path(__file__).parent.parent / path[2:])
    return path


def get_connection():
    """Get a raw DB connection (not from pool). Use only for init_db / one-off tasks."""
    global _use_sqlite
    url = settings.database_url.strip().lower()
    if url.startswith("sqlite"):
        _use_sqlite = True
        return _SqliteConnWrapper(sqlite3.connect(_resolve_sqlite_path(url)))
    import psycopg2
    return psycopg2.connect(settings.database_url)


class _SqliteCursorWrapper:
    """Wraps sqlite3 cursor to accept %s placeholders (PostgreSQL style)."""

    def __init__(self, cursor):
        self._cur = cursor

    def execute(self, sql, params=None):
        if params is not None:
            sql = sql.replace("%s", "?")
        return self._cur.execute(sql, params or ())

    def fetchone(self):
        return self._cur.fetchone()

    def fetchall(self):
        return self._cur.fetchall()

    @property
    def lastrowid(self):
        return self._cur.lastrowid

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self._cur.close()


class _SqliteConnWrapper:
    """Wraps sqlite3 connection to provide cursor() with %s->? translation."""

    def __init__(self, conn):
        self._conn = conn

    def cursor(self):
        return _SqliteCursorWrapper(self._conn.cursor())

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


def get_db_connection():
    """Generator for FastAPI Depends - yields DB connection, returns it to pool when done."""
    url = settings.database_url.strip().lower()
    if url.startswith("sqlite"):
        conn = get_connection()
        try:
            yield conn
        finally:
            conn.close()
    else:
        pool = _get_pg_pool()
        conn = pool.getconn()
        try:
            yield conn
        finally:
            conn.reset()
            pool.putconn(conn)


def init_db():
    """Create tables from init_db.sql (PostgreSQL) or init_db_sqlite.sql."""
    url = settings.database_url.strip().lower()
    if url.startswith("sqlite"):
        sql_file = "init_db_sqlite.sql"
    else:
        sql_file = "init_db.sql"
    sql_path = os.path.join(os.path.dirname(__file__), sql_file)
    with open(sql_path) as f:
        sql = f.read()
    if url.startswith("sqlite"):
        conn = sqlite3.connect(_resolve_sqlite_path(url))
    else:
        conn = get_connection()
    try:
        if url.startswith("sqlite"):
            conn.executescript(sql)
        else:
            conn.autocommit = True
            with conn.cursor() as cur:
                for stmt in sql.split(";"):
                    stmt = stmt.strip()
                    # Remove leading -- comments but keep the statement (e.g. "CREATE TABLE...")
                    while stmt.startswith("--"):
                        stmt = stmt[stmt.find("\n") + 1:].strip() if "\n" in stmt else ""
                    if stmt:
                        try:
                            cur.execute(stmt)
                        except Exception as e:
                            if "already exists" in str(e).lower() or "does not exist" in str(e).lower():
                                pass
                            else:
                                raise
    finally:
        conn.close()
