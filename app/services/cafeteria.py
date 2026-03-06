from app.utils.mensagens import responder_usuario
from app.utils.banco import salvar_pedido_cafeteria_sqlite

PRONTA_ENTREGA_BOLOS_MSG = (
    "🎂 Pronta Entrega de bolo no sistema:\n"
    "- B3 (ate 15 pessoas) — R$120 — sabor padrao: Mesclado com Brigadeiro + Ninho\n"
    "- B4 (ate 30 pessoas) — R$180 — sabor padrao: Mesclado com Brigadeiro + Ninho\n"
    "- Kit Festou opcional: +R$35\n"
    "- Regra atual do fluxo: retirada na loja"
)


async def processar_cafeteria(telefone, texto, estado):
    subetapa = estado.get("subetapa")
    nome = estado.get("nome", "Nome não informado")

    # 📋 Navegação de cardápios
    if subetapa == "aguardando_cardapio":
        if texto == "1":
            msg = "📋 Cardápio *Cafeteria*:\nhttp://bit.ly/44ZlKlZ\n"
        elif texto == "2":
            msg = "📋 Cardápio *Doces Avulsos*:\nhttps://bit.ly/doceschoko\n"
        elif texto == "3":
            msg = PRONTA_ENTREGA_BOLOS_MSG + "\n"
        else:
            await responder_usuario(telefone, "❌ Opção inválida. Digite 1, 2 ou 3.")
            return

        msg += (
            "\n📖 Deseja ver outro cardápio ou voltar ao menu principal?\n"
            "1️⃣ Ver outro cardápio\n"
            "2️⃣ Voltar ao menu"
        )
        estado["subetapa"] = "cardapio_exibido"
        await responder_usuario(telefone, msg)
        return

    elif subetapa == "cardapio_exibido":
        if texto == "1":
            estado["subetapa"] = "aguardando_cardapio"
            await responder_usuario(
                telefone,
                "📋 Qual cardápio de pronta entrega você deseja ver?\n"
                "1️⃣ Cardápio Cafeteria\n"
                "2️⃣ Cardápio Doces Avulsos\n"
                "3️⃣ Bolos Pronta Entrega"
            )
        elif texto == "2":
            return "voltar_menu"
        else:
            await responder_usuario(telefone, "❌ Digite 1 para ver outro cardápio ou 2 para voltar ao menu.")
        return

    # ☕ Pedido direto
    if "itens" in estado:
        if texto.lower() in ["finalizar", "só isso", "obrigado", "obrigada"]:
            salvar_pedido_cafeteria_sqlite(telefone, estado["itens"], nome)
            await responder_usuario(telefone, "☕ Pedido finalizado! Em breve confirmaremos com você.")
            return "finalizar"
        else:
            estado["itens"].append(texto)
            await responder_usuario(telefone, "✅ Pedido registrado! Digite outro item ou *finalizar* para encerrar.")
