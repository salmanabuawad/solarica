from psycopg import connect
from psycopg.rows import dict_row
from .config import DATABASE_URL

def get_conn():
    return connect(DATABASE_URL, row_factory=dict_row)
