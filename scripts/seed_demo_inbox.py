"""Seed de demonstracao: cria cliente + pedido + conversa vinculados.

Executar dentro do container:
    docker compose exec chokobot python scripts/seed_demo_inbox.py

Imprime um resumo no stdout com phone e order_id usados.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app.infrastructure.repositories.sqlite_customer_process_repository import (
    SQLiteCustomerProcessRepository,
)
from app.infrastructure.repositories.sqlite_customer_repository import SQLiteCustomerRepository
from app.infrastructure.repositories.sqlite_order_repository import SQLiteOrderRepository
from app.models import criar_tabelas
from app.services.estados import append_conversation_message, set_recent_message


DEMO_PHONE = "5511900000001"
DEMO_NAME = "Cliente Demo (Seed)"


def seed() -> dict:
    criar_tabelas()

    customer_repo = SQLiteCustomerRepository()
    order_repo = SQLiteOrderRepository()
    process_repo = SQLiteCustomerProcessRepository()

    customer_id = customer_repo.upsert_customer(DEMO_NAME, DEMO_PHONE)

    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%d/%m/%Y")
    order_id = order_repo.create_order(
        nome=DEMO_NAME,
        telefone=DEMO_PHONE,
        categoria="tradicional",
        produto="Bolo",
        tamanho="B3",
        massa="Chocolate",
        recheio="Brigadeiro",
        mousse="Ninho",
        adicional="Morango",
        horario="14:00",
        valor_total="130,00",
        data_entrega=tomorrow,
    )

    process_repo.upsert_process(
        phone=DEMO_PHONE,
        customer_id=customer_id,
        process_type="encomenda_tradicional",
        stage="confirmado",
        status="active",
        source="seed",
        draft_payload={
            "resumo": f"Bolo B3 Chocolate/Brigadeiro/Ninho • {tomorrow} 14:00",
            "fonte": "seed_demo_inbox",
        },
        order_id=order_id,
    )

    now = datetime.now()
    messages = [
        (now - timedelta(minutes=18), "cliente", "Cliente", "Oi, boa tarde!"),
        (now - timedelta(minutes=17), "ia", "Bot", "Oi, tudo bem? Em que posso ajudar?"),
        (now - timedelta(minutes=15), "cliente", "Cliente", "Quero encomendar um bolo para amanha, tamanho B3."),
        (now - timedelta(minutes=14), "ia", "Bot", "Perfeito! Qual sabor de massa, recheio e mousse?"),
        (now - timedelta(minutes=12), "cliente", "Cliente", "Massa de chocolate, recheio de brigadeiro e mousse de ninho. Pode colocar morango tambem."),
        (now - timedelta(minutes=10), "ia", "Bot", f"Anotado! Bolo tradicional B3, Chocolate/Brigadeiro/Ninho com morango. Entrega em {tomorrow} as 14:00. Valor R$ 130,00. Confirma?"),
        (now - timedelta(minutes=8), "cliente", "Cliente", "Confirmo! Pago no PIX."),
        (now - timedelta(minutes=7), "ia", "Bot", "Excelente. Pedido confirmado e registrado no painel."),
    ]
    for seen_at, role, actor, content in messages:
        append_conversation_message(
            DEMO_PHONE,
            role=role,
            actor_label=actor,
            content=content,
            seen_at=seen_at,
        )

    last_msg = messages[-1]
    set_recent_message(DEMO_PHONE, last_msg[3], last_msg[0])

    return {
        "customer_id": customer_id,
        "phone": DEMO_PHONE,
        "nome": DEMO_NAME,
        "order_id": order_id,
        "data_entrega": tomorrow,
        "messages_count": len(messages),
    }


if __name__ == "__main__":
    summary = seed()
    print("=" * 60)
    print("SEED DEMO INBOX — dados adicionados")
    print("=" * 60)
    for key, value in summary.items():
        print(f"  {key}: {value}")
    print("=" * 60)
    print("Abra o painel em http://localhost:3000 e procure por:")
    print(f"  telefone: {summary['phone']}")
    print(f"  pedido:   #{summary['order_id']}")
