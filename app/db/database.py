# app/db/database.py
import os, sqlite3

from app.observability import increment_counter, log_event

def get_db_path() -> str:
    return os.getenv("DB_PATH", "dados/chokobot.db")

def get_connection():
    db_path = get_db_path()
    increment_counter("db_connections_total", db_path=os.path.abspath(db_path))
    log_event("db_connect", db_path=os.path.abspath(db_path))
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn
