from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable

from app.application.service_registry import (
    get_customer_process_repository,
    get_delivery_gateway,
    get_order_gateway,
)
from app.observability import log_event
from app.services.precos import montar_resumo
from app.utils.mensagens import responder_usuario


@dataclass
class ProcessDeliveryFlow:
    responder_usuario_fn: Callable[[str, str], Awaitable[bool]] = responder_usuario
    order_gateway: object | None = None
    delivery_gateway: object | None = None
    customer_process_repository: object | None = None

    async def execute(self, telefone: str, texto: str, estado: dict) -> str | None:
        responder_fn = self.responder_usuario_fn
        order_gateway = self.order_gateway or get_order_gateway()
        delivery_gateway = self.delivery_gateway or get_delivery_gateway()
        process_repository = self.customer_process_repository or get_customer_process_repository()
        etapa = estado["etapa"]
        dados = estado["dados"]
        nome = estado["nome"]

        log_event("delivery_flow_step", telefone=telefone, etapa=etapa, nome=nome)

        if etapa == 1:
            dados["endereco"] = texto.strip()
            estado["etapa"] = 2
            await responder_fn(
                telefone,
                "📞 Informe um *telefone alternativo* ou *referência* (ex.: portaria, bloco, ponto de referência):",
            )
            return None

        if etapa == 2:
            dados["referencia"] = texto.strip()

            pedido = dados.get("pedido") or {}
            pedido["endereco"] = dados.get("endereco", "")
            pedido["referencia"] = dados.get("referencia", "")

            pagamento = pedido.get("pagamento") or dados.get("pagamento") or {}
            forma_pagamento = pagamento.get("forma")
            troco_para = pagamento.get("troco_para")

            if forma_pagamento:
                if forma_pagamento.lower() == "dinheiro" and troco_para:
                    info_pagamento = f"💵 {forma_pagamento} — troco para R${troco_para:.2f}"
                else:
                    info_pagamento = f"💳 {forma_pagamento}"
            else:
                info_pagamento = "💳 Pagamento não informado"

            try:
                taxa_entrega = float(pedido.get("taxa_entrega") or 10.0)
                total = float(pedido.get("valor_total", 0))
                await responder_fn(telefone, montar_resumo(pedido, total))
                await responder_fn(
                    telefone,
                    f"{info_pagamento}\n\n💲 *Obs: já inclui a taxa de entrega de R$ {taxa_entrega:.2f}.*",
                )
            except Exception as exc:
                log_event(
                    "delivery_flow_summary_failed",
                    telefone=telefone,
                    error_type=type(exc).__name__,
                )

            process_repository.upsert_process(
                phone=telefone,
                customer_id=estado.get("cliente_id"),
                process_type="delivery_order",
                stage="aguardando_confirmacao",
                status="active",
                source="legacy_delivery",
                draft_payload=pedido,
            )
            estado["etapa"] = "confirmar_entrega"
            await responder_fn(
                telefone,
                "Está tudo correto?\n"
                "1️⃣ Confirmar pedido\n"
                "2️⃣ Corrigir endereço\n"
                "3️⃣ Falar com atendente",
            )
            return None

        if etapa == "confirmar_entrega":
            opc = texto.strip().lower()

            if opc in [
                "1",
                "confirmar",
                "ok",
                "c",
                "sim",
                "s",
                "confirmar pedido",
                "pedido confirmado",
                "confirmo",
            ]:
                endereco_base = dados.get("endereco", "")
                ref = dados.get("referencia", "")
                endereco_final = f"{endereco_base} | Ref: {ref}" if ref else endereco_base
                pedido = dict(dados.get("pedido") or {})
                pedido["endereco"] = endereco_base
                pedido["referencia"] = ref
                pedido["modo_recebimento"] = "entrega"

                delivery_payload = {
                    "tipo": "entrega",
                    "endereco": endereco_final,
                    "data_agendada": dados.get("data"),
                    "status": "pendente",
                }
                process_payload = {
                    "process_type": "delivery_order",
                    "stage": "pedido_confirmado",
                    "status": "converted",
                    "source": "legacy_delivery",
                    "draft_payload": pedido,
                }

                if hasattr(order_gateway, "create_order_bundle"):
                    encomenda_id = order_gateway.create_order_bundle(
                        phone=telefone,
                        dados=pedido,
                        nome_cliente=nome,
                        cliente_id=estado.get("cliente_id"),
                        delivery_data=delivery_payload,
                        process_data=process_payload,
                    )
                else:
                    encomenda_id = order_gateway.create_order(
                        phone=telefone,
                        dados=pedido,
                        nome_cliente=nome,
                        cliente_id=estado.get("cliente_id"),
                    )

                if encomenda_id <= 0:
                    await responder_fn(
                        telefone,
                        "⚠️ Nao consegui confirmar seu pedido agora. Pode tentar novamente em instantes?",
                    )
                    return None

                if not hasattr(order_gateway, "create_order_bundle"):
                    delivery_gateway.create_delivery(
                        encomenda_id=encomenda_id,
                        **delivery_payload,
                    )
                    process_repository.upsert_process(
                        phone=telefone,
                        customer_id=estado.get("cliente_id"),
                        process_type="delivery_order",
                        stage="pedido_confirmado",
                        status="converted",
                        source="legacy_delivery",
                        draft_payload=pedido,
                        order_id=encomenda_id,
                    )

                await responder_fn(
                    telefone,
                    "Pedido confirmado com sucesso ✅\n"
                    "Obrigada por encomendar com a *Choko* ❤\n"
                    "✨ Se registrar o momento nas redes sociais, lembre de nos marcar @chokodelicia",
                )
                return "finalizar"

            if opc in ["2", "corrigir", "endereco", "endereço", "ajustar", "editar"]:
                process_repository.upsert_process(
                    phone=telefone,
                    customer_id=estado.get("cliente_id"),
                    process_type="delivery_order",
                    stage="coletando_endereco",
                    status="active",
                    source="legacy_delivery",
                    draft_payload=dados.get("pedido") or {},
                )
                estado["etapa"] = 1
                await responder_fn(telefone, "Sem problema! Envie novamente o *endereço completo*:")
                return None

            await responder_fn(
                telefone,
                "Escolha uma opção:\n"
                "1️⃣ Confirmar pedido\n"
                "2️⃣ Corrigir endereço",
            )
            return None

        return None
