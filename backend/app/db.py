"""DB connection factory.

Uses PyMySQL against the MariaDB instance at the URL given by DATABASE_URL
(``mysql://user:pass@host:port/db``). The cursor class is DictCursor so
existing code that does ``row["col"]`` keeps working. Autocommit is off; call
``conn.commit()`` explicitly, matching the previous psycopg pattern.
"""
from urllib.parse import urlparse, unquote

import pymysql
from pymysql.cursors import DictCursor

from .config import DATABASE_URL


def _parse(url: str):
    u = urlparse(url)
    return {
        "host": u.hostname or "127.0.0.1",
        "port": u.port or 3306,
        "user": unquote(u.username) if u.username else "solarica",
        "password": unquote(u.password) if u.password else "",
        "database": (u.path or "/solarica").lstrip("/") or "solarica",
    }


def get_conn():
    cfg = _parse(DATABASE_URL)
    return pymysql.connect(
        cursorclass=DictCursor,
        charset="utf8mb4",
        autocommit=False,
        **cfg,
    )
