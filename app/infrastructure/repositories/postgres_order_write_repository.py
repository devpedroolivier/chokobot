"""Postgres implementation of OrderWriteRepository (Phase B.8a).

Mirrors ``SQLiteOrderWriteRepository`` but every INSERT carries
``tenant_id`` and writes happen inside a single transaction. The
upsert on ``customer_processes`` uses Postgres ``ON CONFLICT`` instead
of SQLite's ``ON CONFLICT(...) DO UPDATE`` flavour.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from app.db.database import open_postgres_connection, resolve_tenant_pk
from app.domain.repositories.order_write_repository import OrderWriteRepository
from app.observability import log_event


class PostgresOrderWriteRepository(OrderWriteRepository):
    @staticmethod
    def _get_or_create_customer_id(
        cur: Any,
        *,
        phone: str,
        nome_cliente: str,
        cliente_id: int | None,
        tenant_pk: int,
    ) -> int:
        if cliente_id:
            return cliente_id

        cur.execute(
            "SELECT id FROM clientes WHERE telefone = %s AND tenant_id = %s",
            (phone, tenant_pk),
        )
        row = cur.fetchone()
        if row is not None:
            return int(row[0])

        cur.execute(
            "INSERT INTO clientes (nome, telefone, tenant_id) "
            "VALUES (%s, %s, %s) RETURNING id",
            (nome_cliente, phone, tenant_pk),
        )
        return int(cur.fetchone()[0])

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
    def _insert_order(cur: Any, payload: dict, tenant_pk: int) -> int:
        cur.execute(
            """
            INSERT INTO encomendas (
                cliente_id, categoria, produto, tamanho, massa, recheio,
                mousse, adicional, kit_festou, quantidade, data_entrega,
                horario, valor_total, serve_pessoas, tenant_id
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            RETURNING id
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
                tenant_pk,
            ),
        )
        order_id = int(cur.fetchone()[0])
        if order_id <= 0:
            raise RuntimeError("invalid_order_id")
        return order_id

    @staticmethod
    def _insert_delivery(cur: Any, *, order_id: int, delivery_data: dict, tenant_pk: int) -> None:
        if not delivery_data:
            return
        cur.execute(
            """
            INSERT INTO entregas (
                encomenda_id, tipo, endereco, data_agendada, status,
                atualizado_em, tenant_id
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                order_id,
                delivery_data.get("tipo", "entrega"),
                delivery_data.get("endereco"),
                delivery_data.get("data_agendada"),
                delivery_data.get("status", "pendente"),
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                tenant_pk,
            ),
        )

    @staticmethod
    def _insert_sweet_items(
        cur: Any, *, order_id: int, sweet_items: list[dict], tenant_pk: int
    ) -> None:
        if not sweet_items:
            return
        for item in sweet_items:
            cur.execute(
                "INSERT INTO encomenda_doces "
                "(encomenda_id, nome, qtd, preco, unit, tenant_id) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (
                    order_id,
                    item.get("nome"),
                    item.get("qtd"),
                    item.get("preco"),
                    item.get("unit"),
                    tenant_pk,
                ),
            )

    @staticmethod
    def _upsert_process(
        cur: Any,
        *,
        phone: str,
        customer_id: int | None,
        order_id: int,
        process_data: dict,
        tenant_pk: int,
    ) -> None:
        if not process_data:
            return
        process_type = str(process_data.get("process_type") or "").strip()
        stage = str(process_data.get("stage") or "").strip()
        if not process_type or not stage:
            raise ValueError("invalid_process_data")

        draft_payload = process_data.get("draft_payload") or {}
        payload_json = json.dumps(draft_payload, ensure_ascii=False, sort_keys=True)
        cur.execute(
            """
            INSERT INTO customer_processes (
                phone, customer_id, process_type, stage, status, source,
                draft_payload, order_id, updated_at, tenant_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s)
            ON CONFLICT (phone, process_type) DO UPDATE SET
                customer_id = EXCLUDED.customer_id,
                stage = EXCLUDED.stage,
                status = EXCLUDED.status,
                source = COALESCE(EXCLUDED.source, customer_processes.source),
                draft_payload = EXCLUDED.draft_payload,
                order_id = EXCLUDED.order_id,
                updated_at = NOW()
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
                tenant_pk,
            ),
        )

    def save_cafeteria_items(
        self,
        *,
        phone: str,
        itens: list[str],
        nome_cliente: str = "Nome não informado",
        tenant_id: str | None = None,
    ) -> None:
        tenant_pk = resolve_tenant_pk(tenant_id)
        data_hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        itens_str = ", ".join(itens or [])

        try:
            with open_postgres_connection() as conn:
                with conn.cursor() as cur:
                    cliente_id = self._get_or_create_customer_id(
                        cur,
                        phone=phone,
                        nome_cliente=nome_cliente,
                        cliente_id=None,
                        tenant_pk=tenant_pk,
                    )
                    cur.execute(
                        "INSERT INTO pedidos_cafeteria "
                        "(cliente_id, pedido, criado_em, tenant_id) "
                        "VALUES (%s, %s, %s, %s)",
                        (cliente_id, itens_str, data_hora, tenant_pk),
                    )
            log_event(
                "cafeteria_order_saved",
                phone=phone,
                nome_cliente=nome_cliente,
                itens=itens_str,
            )
        except Exception as exc:
            log_event(
                "cafeteria_order_save_failed",
                error_type=type(exc).__name__,
                phone=phone,
            )

    def save_order_payload(
        self,
        *,
        phone: str,
        dados: dict,
        nome_cliente: str,
        cliente_id: int | None = None,
        tenant_id: str | None = None,
    ) -> int:
        return self.save_order_bundle(
            phone=phone,
            dados=dados,
            nome_cliente=nome_cliente,
            cliente_id=cliente_id,
            tenant_id=tenant_id,
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
        tenant_id: str | None = None,
    ) -> int:
        tenant_pk = resolve_tenant_pk(tenant_id)
        try:
            with open_postgres_connection() as conn:
                with conn.cursor() as cur:
                    resolved_cliente_id = self._get_or_create_customer_id(
                        cur,
                        phone=phone,
                        nome_cliente=nome_cliente,
                        cliente_id=cliente_id,
                        tenant_pk=tenant_pk,
                    )
                    payload = self._order_payload(dados, resolved_cliente_id)
                    order_id = self._insert_order(cur, payload, tenant_pk)
                    self._insert_sweet_items(
                        cur, order_id=order_id,
                        sweet_items=sweet_items or [], tenant_pk=tenant_pk,
                    )
                    self._insert_delivery(
                        cur, order_id=order_id,
                        delivery_data=delivery_data or {}, tenant_pk=tenant_pk,
                    )
                    self._upsert_process(
                        cur,
                        phone=phone,
                        customer_id=resolved_cliente_id,
                        order_id=order_id,
                        process_data=process_data or {},
                        tenant_pk=tenant_pk,
                    )
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
            log_event(
                "order_bundle_save_failed",
                error_type=type(exc).__name__,
                phone=phone,
            )
            return -1
