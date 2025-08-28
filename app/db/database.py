# app/db/database.py
import os, sqlite3

DB_PATH = os.getenv("DB_PATH", "dados/chokobot.db")

def get_connection():
    print(f"[DB] Conectando em: {os.path.abspath(DB_PATH)}")
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn
