from __future__ import annotations

from dataclasses import dataclass

from app.application.service_registry import get_delivery_gateway
from app.services.precos import montar_resumo
from app.utils.mensagens import responder_usuario


@dataclass
class ProcessDeliveryFlow:
    async def execute(self, telefone: str, texto: str, estado: dict) -> str | None:
        delivery_gateway = get_delivery_gateway()
        etapa = estado["etapa"]
        dados = estado["dados"]
        nome = estado["nome"]

        print(f"📍 ETAPA ATUAL (entrega): {etapa}")

        if etapa == 1:
            dados["endereco"] = texto.strip()
            estado["etapa"] = 2
            await responder_usuario(
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
                await responder_usuario(telefone, montar_resumo(pedido, total))
                await responder_usuario(
                    telefone,
                    f"{info_pagamento}\n\n💲 *Obs: já inclui a taxa de entrega de R$ {taxa_entrega:.2f}.*",
                )
            except Exception as exc:
                print(f"⚠️ Não foi possível montar o resumo: {exc}")

            estado["etapa"] = "confirmar_entrega"
            await responder_usuario(
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
                encomenda_id = dados.get("encomenda_id")
                endereco_base = dados.get("endereco", "")
                ref = dados.get("referencia", "")
                endereco_final = f"{endereco_base} | Ref: {ref}" if ref else endereco_base

                delivery_gateway.create_delivery(
                    encomenda_id=encomenda_id,
                    tipo="entrega",
                    endereco=endereco_final,
                    data_agendada=dados.get("data"),
                    status="pendente",
                )

                await responder_usuario(
                    telefone,
                    "Pedido confirmado com sucesso ✅\n"
                    "Obrigada por encomendar com a *Choko* ❤\n"
                    "✨ Se registrar o momento nas redes sociais, lembre de nos marcar @chokodelicia",
                )
                return "finalizar"

            if opc in ["2", "corrigir", "endereco", "endereço", "ajustar", "editar"]:
                estado["etapa"] = 1
                await responder_usuario(telefone, "Sem problema! Envie novamente o *endereço completo*:")
                return None

            await responder_usuario(
                telefone,
                "Escolha uma opção:\n"
                "1️⃣ Confirmar pedido\n"
                "2️⃣ Corrigir endereço",
            )
            return None

        return None
