from sqlite3 import Connection


def criar_tabela_customer_processes(conn: Connection):
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS customer_processes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT NOT NULL,
            customer_id INTEGER,
            process_type TEXT NOT NULL,
            stage TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            source TEXT,
            draft_payload TEXT NOT NULL DEFAULT '{}',
            order_id INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES clientes(id),
            FOREIGN KEY (order_id) REFERENCES encomendas(id)
        );
        """
    )
    cursor.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ux_customer_processes_phone_type
        ON customer_processes(phone, process_type)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_customer_processes_status_updated
        ON customer_processes(status, updated_at)
        """
    )
    conn.commit()
