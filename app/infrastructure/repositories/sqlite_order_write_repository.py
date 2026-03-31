from __future__ import annotations

import json
from datetime import datetime
import sqlite3

from app.db.database import get_connection
from app.domain.repositories.order_write_repository import OrderWriteRepository
from app.observability import log_event


def _get_id_from_row(row):
    if row is None:
        return None
    try:
        return row["id"]
    except Exception:
        return row[0] if len(row) else None


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

    @staticmethod
    def _insert_order(conn: sqlite3.Connection, payload: dict) -> int:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO encomendas (
                cliente_id,
                categoria,
                produto,
                tamanho,
                massa,
                recheio,
                mousse,
                adicional,
                kit_festou,
                quantidade,
                data_entrega,
                horario,
                valor_total,
                serve_pessoas
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.get("cliente_id"),
                payload.get("categoria"),
                payload.get("produto"),
                payload.get("tamanho"),
                payload.get("massa"),
                payload.get("recheio"),
                payload.get("mousse"),
                payload.get("adicional"),
                payload.get("kit_festou"),
                payload.get("quantidade"),
                payload.get("data_entrega"),
                payload.get("horario_retirada"),
                payload.get("valor_total"),
                payload.get("serve_pessoas"),
            ),
        )
        order_id = int(cur.lastrowid or 0)
        if order_id <= 0:
            raise RuntimeError("invalid_order_id")
        return order_id

    @staticmethod
    def _insert_delivery(conn: sqlite3.Connection, *, order_id: int, delivery_data: dict) -> None:
        if not delivery_data:
            return
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO entregas (encomenda_id, tipo, endereco, data_agendada, status, atualizado_em)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                order_id,
                delivery_data.get("tipo", "entrega"),
                delivery_data.get("endereco"),
                delivery_data.get("data_agendada"),
                delivery_data.get("status", "pendente"),
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )

    @staticmethod
    def _insert_sweet_items(conn: sqlite3.Connection, *, order_id: int, sweet_items: list[dict]) -> None:
        if not sweet_items:
            return
        cur = conn.cursor()
        for item in sweet_items:
            cur.execute(
                "INSERT INTO encomenda_doces (encomenda_id, nome, qtd, preco, unit) VALUES (?, ?, ?, ?, ?)",
                (
                    order_id,
                    item.get("nome"),
                    item.get("qtd"),
                    item.get("preco"),
                    item.get("unit"),
                ),
            )

    @staticmethod
    def _upsert_process(
        conn: sqlite3.Connection,
        *,
        phone: str,
        customer_id: int | None,
        order_id: int,
        process_data: dict,
    ) -> None:
        if not process_data:
            return
        process_type = str(process_data.get("process_type") or "").strip()
        stage = str(process_data.get("stage") or "").strip()
        if not process_type or not stage:
            raise ValueError("invalid_process_data")

        draft_payload = process_data.get("draft_payload") or {}
        payload_json = json.dumps(draft_payload, ensure_ascii=False, sort_keys=True)
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO customer_processes (
                phone,
                customer_id,
                process_type,
                stage,
                status,
                source,
                draft_payload,
                order_id,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(phone, process_type) DO UPDATE SET
                customer_id = excluded.customer_id,
                stage = excluded.stage,
                status = excluded.status,
                source = COALESCE(excluded.source, customer_processes.source),
                draft_payload = excluded.draft_payload,
                order_id = excluded.order_id,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                phone,
                customer_id,
                process_type,
                stage,
                process_data.get("status", "active"),
                process_data.get("source"),
                payload_json,
                order_id,
            ),
        )

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

            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO pedidos_cafeteria (cliente_id, pedido, criado_em)
                VALUES (?, ?, ?)
                """,
                (cliente_id, itens_str, data_hora),
            )
            conn.commit()
            log_event(
                "cafeteria_order_saved",
                phone=phone,
                nome_cliente=nome_cliente,
                itens=itens_str,
            )
        except Exception as exc:
            conn.rollback()
            log_event("cafeteria_order_save_failed", error_type=type(exc).__name__, phone=phone)
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
        return self.save_order_bundle(
            phone=phone,
            dados=dados,
            nome_cliente=nome_cliente,
            cliente_id=cliente_id,
        )

    def save_order_bundle(
        self,
        *,
        phone: str,
        dados: dict,
        nome_cliente: str,
        cliente_id: int | None = None,
        delivery_data: dict | None = None,
        process_data: dict | None = None,
        sweet_items: list[dict] | None = None,
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
            order_id = self._insert_order(conn, payload)
            self._insert_sweet_items(conn, order_id=order_id, sweet_items=sweet_items or [])
            self._insert_delivery(conn, order_id=order_id, delivery_data=delivery_data or {})
            self._upsert_process(
                conn,
                phone=phone,
                customer_id=resolved_cliente_id,
                order_id=order_id,
                process_data=process_data or {},
            )
            conn.commit()
            log_event(
                "order_bundle_saved",
                order_id=order_id,
                phone=phone,
                nome_cliente=nome_cliente,
                categoria=payload.get("categoria", "n/d"),
                valor_total=float(payload.get("valor_total") or 0),
            )
            return order_id
        except Exception as exc:
            conn.rollback()
            log_event("order_bundle_save_failed", error_type=type(exc).__name__, phone=phone)
            return -1
        finally:
            conn.close()
