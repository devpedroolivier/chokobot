import sqlite3
from pathlib import Path

# Caminho: raiz_projeto/dados/chokobot.db
DB_PATH = Path(__file__).resolve().parent.parent / "dados" / "chokobot.db"

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn
