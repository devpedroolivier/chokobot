from __future__ import annotations

from datetime import datetime
from typing import Optional
import sqlite3

from app.db.database import get_connection
from app.domain.repositories.order_write_repository import OrderWriteRepository


def _get_id_from_row(row):
    if row is None:
        return None
    try:
        return row["id"]
    except Exception:
        return row[0] if len(row) else None


def _existing_columns(conn: sqlite3.Connection, table: str, candidates: list[str]) -> list[str]:
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table});")
    existing = {r[1] for r in cur.fetchall()}
    return [c for c in candidates if c in existing]


class SQLiteOrderWriteRepository(OrderWriteRepository):
    def _get_or_create_customer_id(
        self,
        conn: sqlite3.Connection,
        *,
        phone: str,
        nome_cliente: str,
        cliente_id: int | None = None,
    ) -> int:
        cur = conn.cursor()

        if cliente_id:
            return cliente_id

        cur.execute("SELECT id FROM clientes WHERE telefone = ?", (phone,))
        row = cur.fetchone()
        existing_id = _get_id_from_row(row)
        if existing_id:
            return existing_id

        cur.execute("INSERT INTO clientes (nome, telefone) VALUES (?, ?)", (nome_cliente, phone))
        return cur.lastrowid

    @staticmethod
    def _order_payload(dados: dict, cliente_id: int) -> dict:
        pagamento = dados.get("pagamento", {}) or {}
        forma_pagamento = pagamento.get("forma")
        troco_para = pagamento.get("troco_para")

        return {
            "cliente_id": cliente_id,
            "categoria": dados.get("categoria") or dados.get("linha") or "tradicional",
            "linha": dados.get("linha"),
            "massa": dados.get("massa"),
            "recheio": dados.get("recheio"),
            "mousse": dados.get("mousse"),
            "adicional": dados.get("fruta_ou_nozes") or dados.get("adicional"),
            "tamanho": dados.get("tamanho"),
            "data_entrega": dados.get("data_entrega") or dados.get("data") or dados.get("pronta_entrega"),
            "horario_retirada": dados.get("hora_entrega") or dados.get("horario_retirada"),
            "descricao": (dados.get("descricao") or dados.get("resumo") or "Bolo personalizado").strip(),
            "valor_total": dados.get("valor_total") or dados.get("valor") or 0,
            "serve_pessoas": dados.get("serve_pessoas"),
            "gourmet": 1 if str(dados.get("gourmet", "")).lower() in ("1", "true", "sim", "yes", "gourmet") else 0,
            "entrega": dados.get("tipo_entrega") or dados.get("entrega"),
            "produto": dados.get("produto"),
            "quantidade": dados.get("quantidade") or 1,
            "kit_festou": 1 if str(dados.get("kit_festou", "")).lower() in ("1", "true", "sim", "yes") else 0,
            "fruta_ou_nozes": dados.get("fruta_ou_nozes") or dados.get("adicional"),
            "forma_pagamento": forma_pagamento or "Pendente",
            "troco_para": troco_para,
        }

    def save_cafeteria_items(
        self,
        *,
        phone: str,
        itens: list[str],
        nome_cliente: str = "Nome não informado",
    ) -> None:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        try:
            cliente_id = self._get_or_create_customer_id(conn, phone=phone, nome_cliente=nome_cliente)

            data_hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            itens_str = ", ".join(itens or [])

            cols = _existing_columns(conn, "pedidos_cafeteria", ["cliente_id", "itens", "pedido", "criado_em"])
            placeholders = ", ".join("?" for _ in cols)
            sql = f"INSERT INTO pedidos_cafeteria ({', '.join(cols)}) VALUES ({placeholders})"

            values_map = {
                "cliente_id": cliente_id,
                "itens": itens_str,
                "pedido": itens_str,
                "criado_em": data_hora,
            }

            cur = conn.cursor()
            cur.execute(sql, [values_map.get(c) for c in cols])
            conn.commit()
            print(f"☕ Pedido cafeteria salvo — Cliente: {nome_cliente} ({phone}), Itens: {itens_str}")
        except Exception as exc:
            conn.rollback()
            print(f"❌ Erro ao salvar pedido cafeteria: {exc}")
        finally:
            conn.close()

    def save_order_payload(
        self,
        *,
        phone: str,
        dados: dict,
        nome_cliente: str,
        cliente_id: int | None = None,
    ) -> int:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        try:
            resolved_cliente_id = self._get_or_create_customer_id(
                conn,
                phone=phone,
                nome_cliente=nome_cliente,
                cliente_id=cliente_id,
            )

            payload = self._order_payload(dados, resolved_cliente_id)
            candidate_cols = [
                "cliente_id",
                "categoria",
                "linha",
                "massa",
                "recheio",
                "mousse",
                "adicional",
                "tamanho",
                "gourmet",
                "entrega",
                "data_entrega",
                "horario_retirada",
                "descricao",
                "valor_total",
                "serve_pessoas",
                "produto",
                "quantidade",
                "kit_festou",
                "fruta_ou_nozes",
                "forma_pagamento",
                "troco_para",
                "horario",
            ]
            cols = _existing_columns(conn, "encomendas", candidate_cols)
            values_map = dict(payload)
            values_map.setdefault("horario", payload.get("horario_retirada"))

            placeholders = ", ".join("?" for _ in cols)
            sql = f"INSERT INTO encomendas ({', '.join(cols)}) VALUES ({placeholders})"

            cur = conn.cursor()
            cur.execute(sql, [values_map.get(c) for c in cols])
            encomenda_id = cur.lastrowid
            conn.commit()
            print(
                f"📝 Encomenda salva com sucesso — ID {encomenda_id}, "
                f"Cliente: {nome_cliente} ({phone}), Categoria: {payload.get('categoria', 'n/d')}, "
                f"Valor: R${float(payload.get('valor_total') or 0):.2f}"
            )
            return encomenda_id
        except Exception as exc:
            conn.rollback()
            print(f"❌ Erro ao salvar encomenda: {exc}")
            return -1
        finally:
            conn.close()
