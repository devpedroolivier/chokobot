import os
import tempfile
import unittest

os.environ.setdefault("ZAPI_TOKEN", "test-token")
os.environ.setdefault("ZAPI_BASE", "https://example.test")

from app.db.database import get_connection
from app.models import criar_tabelas


class SQLiteSchemaIndexesTests(unittest.TestCase):
    def test_criar_tabelas_creates_indexes_for_hot_lookup_paths(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "chokobot.db")
            previous_db_path = os.environ.get("DB_PATH")
            os.environ["DB_PATH"] = db_path
            try:
                criar_tabelas()

                conn = get_connection()
                try:
                    cur = conn.cursor()
                    cur.execute("PRAGMA index_list('clientes')")
                    clientes_indexes = {row["name"] for row in cur.fetchall()}

                    cur.execute("PRAGMA index_list('entregas')")
                    entregas_indexes = {row["name"] for row in cur.fetchall()}

                    cur.execute("PRAGMA index_list('pedidos_cafeteria')")
                    cafeteria_indexes = {row["name"] for row in cur.fetchall()}
                finally:
                    conn.close()
            finally:
                if previous_db_path is None:
                    os.environ.pop("DB_PATH", None)
                else:
                    os.environ["DB_PATH"] = previous_db_path

        self.assertIn("ix_clientes_telefone", clientes_indexes)
        self.assertIn("ix_clientes_criado_em", clientes_indexes)
        self.assertIn("ix_entregas_encomenda_id", entregas_indexes)
        self.assertIn("ix_pedidos_cafeteria_cliente_id", cafeteria_indexes)


if __name__ == "__main__":
    unittest.main()
