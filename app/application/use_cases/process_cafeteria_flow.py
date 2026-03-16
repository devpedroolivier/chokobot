from __future__ import annotations

from typing import Awaitable, Callable

from app.application.service_registry import get_order_gateway
from app.utils.mensagens import responder_usuario

PRONTA_ENTREGA_BOLOS_MSG = (
    "🎂 Bolos Pronta Entrega:\n"
    "- B3 (ate 15 pessoas) — R$120 — sabor padrao: Mesclado com Brigadeiro + Ninho\n"
    "- B4 (ate 30 pessoas) — R$180 — sabor padrao: Mesclado com Brigadeiro + Ninho\n"
    "🎉 Kit Festou opcional: +R$35\n"
    "- Regra atual do fluxo: retirada na loja"
)

ResponderUsuarioFn = Callable[[str, str], Awaitable[bool]]


async def process_cafeteria_flow(
    telefone: str,
    texto: str,
    estado: dict,
    *,
    responder_usuario_fn: ResponderUsuarioFn = responder_usuario,
    order_gateway=None,
):
    subetapa = estado.get("subetapa")
    nome = estado.get("nome", "Nome não informado")
    order_gateway = order_gateway or get_order_gateway()

    if subetapa == "aguardando_cardapio":
        if texto == "1":
            msg = "📋 Cardápio *Cafeteria*:\nhttp://bit.ly/44ZlKlZ\n"
        elif texto == "2":
            msg = "📋 Cardápio *Doces Avulsos*:\nhttps://bit.ly/doceschoko\n"
        elif texto == "3":
            msg = PRONTA_ENTREGA_BOLOS_MSG + "\n"
        else:
            await responder_usuario_fn(telefone, "❌ Opção inválida. Digite 1, 2 ou 3.")
            return None

        msg += (
            "\n📖 Deseja ver outro cardápio ou voltar ao menu principal?\n"
            "1️⃣ Ver outro cardápio\n"
            "2️⃣ Voltar ao menu"
        )
        estado["subetapa"] = "cardapio_exibido"
        await responder_usuario_fn(telefone, msg)
        return None

    if subetapa == "cardapio_exibido":
        if texto == "1":
            estado["subetapa"] = "aguardando_cardapio"
            await responder_usuario_fn(
                telefone,
                "📋 Qual cardápio de pronta entrega você deseja ver?\n"
                "1️⃣ Cardápio Cafeteria\n"
                "2️⃣ Cardápio Doces Avulsos\n"
                "3️⃣ Bolos Pronta Entrega",
            )
        elif texto == "2":
            return "voltar_menu"
        else:
            await responder_usuario_fn(
                telefone,
                "❌ Digite 1 para ver outro cardápio ou 2 para voltar ao menu.",
            )
        return None

    if "itens" in estado:
        if texto.lower() in ["finalizar", "só isso", "obrigado", "obrigada"]:
            order_gateway.save_cafeteria_order(phone=telefone, itens=estado["itens"], nome_cliente=nome)
            await responder_usuario_fn(telefone, "☕ Pedido finalizado! Em breve confirmaremos com você.")
            return "finalizar"

        estado["itens"].append(texto)
        await responder_usuario_fn(
            telefone,
            "✅ Pedido registrado! Digite outro item ou *finalizar* para encerrar.",
        )

    return None
