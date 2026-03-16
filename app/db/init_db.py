# app/db/init_db.py
from pathlib import Path
from app.db.database import get_connection
from app.observability import log_event

def ensure_views():
    """
    Executa o SQL de criação/atualização de VIEWS (e o que mais você quiser colocar lá).
    Ele lê o arquivo schema.sql e executa no banco apontado por get_connection().
    """
    # tenta resolver schema.sql tanto em dev quanto no container
    candidates = [
        Path("app/db/schema.sql"),
        Path("app") / "db" / "schema.sql",
        Path(__file__).parent / "schema.sql",
        Path("schema.sql"),
    ]
    schema_path = next((p for p in candidates if p.exists()), None)
    if not schema_path:
        log_event("db_schema_missing")
        return

    sql = schema_path.read_text(encoding="utf-8")
    conn = get_connection()
    try:
        with conn:
            conn.executescript(sql)
        log_event("db_views_applied", schema_path=str(schema_path.resolve()))
    finally:
        conn.close()
