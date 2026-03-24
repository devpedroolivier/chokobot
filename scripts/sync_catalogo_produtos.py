from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from app.settings import get_settings


CATALOG_PATH = Path("app/ai/knowledge/catalogo_produtos.json")


def _connect() -> sqlite3.Connection:
    db_path = Path(get_settings().db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _load_items() -> list[dict]:
    payload = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    return payload["items"]


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS catalogo_produtos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            catalog TEXT NOT NULL,
            section TEXT NOT NULL,
            name TEXT NOT NULL,
            variant TEXT,
            description TEXT,
            availability_note TEXT,
            price_brl REAL NOT NULL,
            unit TEXT,
            size TEXT,
            weight_approx TEXT,
            options_json TEXT,
            source_pdf TEXT NOT NULL,
            synced_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE UNIQUE INDEX IF NOT EXISTS ux_catalogo_produtos_identity
        ON catalogo_produtos(catalog, section, name, COALESCE(variant, ''), source_pdf);

        CREATE INDEX IF NOT EXISTS ix_catalogo_produtos_catalog_section
        ON catalogo_produtos(catalog, section);
        """
    )


def sync_catalog() -> int:
    items = _load_items()
    conn = _connect()
    try:
        with conn:
            _ensure_schema(conn)
            source_pdfs = sorted({item["source_pdf"] for item in items})
            conn.executemany(
                "DELETE FROM catalogo_produtos WHERE source_pdf = ?",
                [(source_pdf,) for source_pdf in source_pdfs],
            )
            conn.executemany(
                """
                INSERT INTO catalogo_produtos (
                    catalog,
                    section,
                    name,
                    variant,
                    description,
                    availability_note,
                    price_brl,
                    unit,
                    size,
                    weight_approx,
                    options_json,
                    source_pdf
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        item["catalog"],
                        item["section"],
                        item["name"],
                        item.get("variant"),
                        item.get("description"),
                        item.get("availability_note"),
                        item["price_brl"],
                        item.get("unit"),
                        item.get("size"),
                        item.get("weight_approx"),
                        json.dumps(item.get("options", []), ensure_ascii=True),
                        item["source_pdf"],
                    )
                    for item in items
                ],
            )
        return len(items)
    finally:
        conn.close()


if __name__ == "__main__":
    inserted = sync_catalog()
    print(f"catalogo_produtos sincronizado com {inserted} registros.")
