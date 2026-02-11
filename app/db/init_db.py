from pathlib import Path

from app.db.database import get_connection


def ensure_views():
    """
    Executa o SQL de criacao/atualizacao de views.
    """
    candidates = [
        Path("app/db/schema.sql"),
        Path("app") / "db" / "schema.sql",
        Path(__file__).parent / "schema.sql",
        Path("schema.sql"),
    ]
    schema_path = next((p for p in candidates if p.exists()), None)
    if not schema_path:
        print("[DB] schema.sql nao encontrado; pulando ensure_views()")
        return

    sql = schema_path.read_text(encoding="utf-8")
    conn = get_connection()
    try:
        with conn:
            conn.executescript(sql)
        print(f"[DB] Views aplicadas a partir de: {schema_path.resolve()}")
    finally:
        conn.close()
