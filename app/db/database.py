import os
import sqlite3

from app.observability import increment_counter, log_event
from app.settings import get_settings

def get_db_path() -> str:
    return get_settings().db_path

def get_connection():
    db_path = get_db_path()
    increment_counter("db_connections_total", db_path=os.path.abspath(db_path))
    log_event("db_connect", db_path=os.path.abspath(db_path))
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn
