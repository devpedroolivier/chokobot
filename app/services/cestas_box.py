# -*- coding: utf-8 -*-
# app/services/cestas_box.py
from app.utils.mensagens import responder_usuario
from app.utils.banco import salvar_encomenda_sqlite
from app.models.entregas import salvar_entrega
from app.services.encomendas_utils import LIMITE_HORARIO_ENTREGA, _horario_entrega_permitido

# Catálogo de cestas box
CESTAS_BOX_CATALOGO = {
    "1": {
        "nome": "BOX P CHOCOLATES",
        "preco": 99.90,
        "descricao": "2 trufas, 1 chokobom, 1 cake, 6 bombons, 1 tablete de chocolate",
        "serve": 1,
    },
    "2": {
        "nome": "BOX P CHOCOLATES (com Balão)",
        "preco": 119.90,
        "descricao": "2 trufas, 1 chokobom, 1 cake, 6 bombons, 1 tablete de chocolate, Balão Personalizado",
        "serve": 1,
    },
    "3": {
        "nome": "BOX M CHOCOLATES",
        "preco": 149.90,
        "descricao": "3 trufas, 2 chokobons, 2 cakes, 6 bombons, 1 tablete de chocolate",
        "serve": 2,
    },
    "4": {
        "nome": "BOX M CHOCOLATES BALÃO",
        "preco": 189.90,
        "descricao": "3 trufas, 2 chokobons, 2 cakes, 6 bombons, 1 tablete de chocolate, Balão Personalizado",
        "serve": 2,
    },
    "5": {
        "nome": "BOX M CAFÉ",
        "preco": 179.90,
        "descricao": "5 bombons, 1 tablete de chocolate, 1 pote cheesecake, 1 pão de queijo, 1 croissant, 1 suco natural, Bolachinhas, 1 cappuccino em pó",
        "serve": 2,
    },
    "6": {
        "nome": "BOX M CAFÉ BALÃO",
        "preco": 219.90,
        "descricao": "5 bombons, 1 tablete de chocolate, 1 pote cheesecake, 1 pão de queijo, 1 croissant, 1 suco natural, Bolachinhas, 1 cappuccino em pó, Balão Personalizado",
        "serve": 2,
    },
}

def montar_menu_cestas() -> str:
    """Monta a mensagem com o menu de cestas box."""
    linhas = ["🎁 *Cestas Box Café ou Chocolate*\n"]
    
    for chave, info in CESTAS_BOX_CATALOGO.items():
        linhas.append(f"{chave}. {info['nome']} — R${info['preco']:.2f}")
    
    linhas.append("\n📝 Digite o *número da cesta* desejada:")
    return "\n".join(linhas)


async def processar_cestas_box(telefone, texto, estado, nome_cliente, cliente_id):
    """
    Roteia o fluxo de cestas box.
    Estados:
      - "selecao": aguardando seleção da cesta
      - "data_entrega": aguardando data
      - "hora_retirada": aguardando horário
      - "modo_recebimento": escolher retirada ou entrega
      - "endereco": endereço (se entrega)
      - "confirmar_pedido": confirmação final
      - "pagamento_forma": escolher forma de pagamento
      - "pagamento_troco": informar troco (se dinheiro)
    """
    etapa = estado.get("etapa", "selecao")
    dados = estado.setdefault("dados", {})

    # ====== SELEÇÃO DE CESTA ======
    if etapa == "selecao":
        escolha = (texto or "").strip().lower()
        
        if escolha not in CESTAS_BOX_CATALOGO:
            await responder_usuario(telefone, montar_menu_cestas())
            return
        
        cesta_info = CESTAS_BOX_CATALOGO[escolha]
        dados["cesta_numero"] = escolha
        dados["cesta_nome"] = cesta_info["nome"]
        dados["cesta_preco"] = cesta_info["preco"]
        dados["cesta_descricao"] = cesta_info["descricao"]
        dados["cesta_serve"] = cesta_info["serve"]
        dados["categoria"] = "cesta_box"
        
        estado["etapa"] = "data_entrega"
        await responder_usuario(
            telefone,
            f"✅ Cesta selecionada: *{cesta_info['nome']}*\n"
            f"R${cesta_info['preco']:.2f}\n\n"
            f"📆 Informe a *data de retirada/entrega* (DD/MM/AAAA):"
        )
        return

    # ====== DATA ======
    if etapa == "data_entrega":
        from app.services.encomendas_utils import _valida_data
        
        texto_limpo = (texto or "").strip()
        
        if not texto_limpo:
            await responder_usuario(telefone, "⚠️ Por favor, informe uma data válida (DD/MM/AAAA).")
            return
        
        if not _valida_data(texto_limpo):
            await responder_usuario(telefone, "⚠️ Data inválida. Digite no formato DD/MM/AAAA.")
            return
        
        dados["data_entrega"] = texto_limpo
        estado["etapa"] = "hora_retirada"
        await responder_usuario(telefone, "⏰ Informe o *horário de retirada/entrega* (HH:MM ou 24h):")
        return

    # ====== HORA ======
    if etapa == "hora_retirada":
        from app.services.encomendas_utils import _parse_hora
        
        if not _parse_hora(texto):
            await responder_usuario(telefone, "⚠️ Horário inválido. Digite no formato HH:MM (ex: 14:30).")
            return
        
        dados["horario_retirada"] = (texto or "").strip()
        estado["etapa"] = "modo_recebimento"
        await responder_usuario(
            telefone,
            "📍 Como você deseja receber?\n"
            "1️⃣ Retirada na loja\n"
            "2️⃣ Entrega em casa (taxa: R$10,00)"
        )
        return

    # ====== MODO DE RECEBIMENTO ======
    if etapa == "modo_recebimento":
        modo = (texto or "").strip().lower()
        
        if modo in ["1", "retirada"]:
            dados["modo_recebimento"] = "retirada"
            dados["endereco"] = ""
            estado["etapa"] = "confirmar_pedido"
            await montar_resumo_e_confirmar(telefone, estado, dados)
            return
        
        elif modo in ["2", "entrega"]:
            if not _horario_entrega_permitido(dados.get("horario_retirada")):
                estado["etapa"] = "hora_retirada"
                await responder_usuario(
                    telefone,
                    f"🚚 As entregas são realizadas até as *{LIMITE_HORARIO_ENTREGA}*.\n"
                    f"Informe um horário até *{LIMITE_HORARIO_ENTREGA}* para entrega."
                )
                return

            dados["modo_recebimento"] = "entrega"
            dados["taxa_entrega"] = 10.0
            estado["etapa"] = "endereco"
            await responder_usuario(
                telefone,
                "📍 Qual é o *endereço de entrega*? (logradouro, número, complemento)"
            )
            return
        
        else:
            await responder_usuario(
                telefone,
                "⚠️ Digite *1* para retirada ou *2* para entrega."
            )
            return

    # ====== ENDEREÇO ======
    if etapa == "endereco":
        endereco = (texto or "").strip()
        
        if not endereco:
            await responder_usuario(telefone, "⚠️ Por favor, informe o endereço.")
            return
        
        dados["endereco"] = endereco
        estado["etapa"] = "confirmar_pedido"
        await montar_resumo_e_confirmar(telefone, estado, dados)
        return

    # ====== CONFIRMAÇÃO ======
    if etapa == "confirmar_pedido":
        resposta = (texto or "").strip().lower()
        
        if resposta in ["1", "sim", "confirmar"]:
            # Passa para pagamento
            if "pagamento" not in dados:
                dados["pagamento"] = {}
                await responder_usuario(
                    telefone,
                    "💳 *Forma de pagamento*\n"
                    "1️⃣ PIX\n"
                    "2️⃣ Cartão (débito/crédito)\n"
                    "3️⃣ Dinheiro\n\n"
                    "Digite *1*, *2* ou *3*."
                )
                estado["etapa"] = "pagamento_forma"
                return
        
        elif resposta in ["2", "nao", "não", "corrigir"]:
            await responder_usuario(
                telefone,
                "🔄 Vamos recomeçar...\n\n" + montar_menu_cestas()
            )
            estado["etapa"] = "selecao"
            estado["dados"] = {}
            return
        
        else:
            await responder_usuario(
                telefone,
                "⚠️ Digite *1* para confirmar ou *2* para corrigir."
            )
            return

    # ====== PAGAMENTO – FORMA ======
    if etapa == "pagamento_forma":
        escolha = (texto or "").strip()
        formas_pagamento = {
            "1": "PIX",
            "2": "Cartão",
            "3": "Dinheiro"
        }
        
        if escolha not in formas_pagamento:
            await responder_usuario(
                telefone,
                "Não entendi.\n"
                "💳 *Forma de pagamento*\n"
                "1️⃣ PIX\n"
                "2️⃣ Cartão (débito/crédito)\n"
                "3️⃣ Dinheiro"
            )
            return
        
        forma = formas_pagamento[escolha]
        dados["pagamento"]["forma"] = forma
        
        if forma == "Dinheiro":
            estado["etapa"] = "pagamento_troco"
            await responder_usuario(
                telefone,
                "💸 Você escolheu *dinheiro*.\n"
                "Para facilitar, me diga: *troco para quanto?*\n"
                "Exemplos: 50, 100, 200."
            )
            return
        else:
            dados["pagamento"]["troco_para"] = None
            estado["etapa"] = "finalizar_venda"
            await responder_usuario(
                telefone,
                f"✅ Pagamento registrado: *{forma}*"
            )
            await salvar_pedido_cesta(telefone, estado, dados, nome_cliente, cliente_id)
            return "finalizar"

    # ====== PAGAMENTO – TROCO ======
    if etapa == "pagamento_troco":
        valor = (texto or "").strip().replace(",", ".")
        try:
            troco = float(valor)
            if troco <= 0:
                raise ValueError()
        except Exception:
            await responder_usuario(telefone, "Valor inválido. Informe apenas números. Exemplo: 50 ou 100.")
            return
        
        dados["pagamento"]["troco_para"] = troco
        estado["etapa"] = "finalizar_venda"
        await responder_usuario(
            telefone,
            f"✅ Pagamento registrado: *Dinheiro* — troco para *R${troco:.2f}*"
        )
        await salvar_pedido_cesta(telefone, estado, dados, nome_cliente, cliente_id)
        return "finalizar"


async def salvar_pedido_cesta(telefone, estado, dados, nome_cliente, cliente_id):
    """Salva a encomenda de cesta box."""
    try:
        pedido_final = {
            "categoria": "cesta_box",
            "cesta_nome": dados.get("cesta_nome"),
            "cesta_preco": dados.get("cesta_preco"),
            "cesta_descricao": dados.get("cesta_descricao"),
            "data_entrega": dados.get("data_entrega"),
            "horario_retirada": dados.get("horario_retirada"),
            "modo_recebimento": dados.get("modo_recebimento"),
            "endereco": dados.get("endereco", ""),
            "valor_total": dados.get("cesta_preco", 0.0) + dados.get("taxa_entrega", 0.0),
            "pagamento": dados.get("pagamento", {}),
        }
        
        encomenda_id = salvar_encomenda_sqlite(
            telefone, pedido_final, nome_cliente, cliente_id
        )
        
        if dados.get("modo_recebimento") == "entrega":
            salvar_entrega(
                encomenda_id,
                "cesta_box",
                dados.get("data_entrega"),
                "agendada"
            )
        
        total = dados.get("cesta_preco", 0.0) + dados.get("taxa_entrega", 0.0)
        await responder_usuario(
            telefone,
            f"✅ *Pedido confirmado com sucesso!* ✅\n"
            f"ID: #{encomenda_id}\n"
            f"Cesta: {dados.get('cesta_nome')}\n"
            f"Data: {dados.get('data_entrega')}\n"
            f"Horário: {dados.get('horario_retirada')}\n\n"
            f"💰 *Total: R${total:.2f}*\n\n"
            f"Obrigada por sua compra! 🎁\n"
            f"✨ Se registrar o momento nas redes sociais, lembre de nos marcar @chokodelicia"
        )
    
    except Exception as e:
        print(f"❌ Erro ao salvar cesta box: {e}")
        await responder_usuario(telefone, f"❌ Erro ao processar pedido: {str(e)}")



async def montar_resumo_e_confirmar(telefone, estado, dados):
    """Monta o resumo do pedido e pede confirmação."""
    modo_txt = "🏪 Retirada na loja" if dados.get("modo_recebimento") == "retirada" else "🚚 Entrega em casa"
    endereco_txt = f"\n📍 Endereço: {dados.get('endereco', '')}" if dados.get("endereco") else ""
    preco_base = dados.get("cesta_preco", 0.0)
    taxa = dados.get("taxa_entrega", 0.0)
    total = preco_base + taxa
    
    taxa_txt = f"Taxa de entrega: R${taxa:.2f}\n" if taxa else ""
    resumo = (
        f"✅ *Resumo do seu pedido*\n\n"
        f"🎁 *Cesta*: {dados.get('cesta_nome')}\n"
        f"R${preco_base:.2f}\n\n"
        f"📋 *Detalhes*:\n{dados.get('cesta_descricao')}\n\n"
        f"📅 *Data*: {dados.get('data_entrega')}\n"
        f"⏰ *Horário*: {dados.get('horario_retirada')}\n"
        f"{modo_txt}{endereco_txt}\n\n"
        f"———\n"
        f"{taxa_txt}"
        f"*Total: R${total:.2f}*\n"
        f"———\n\n"
        f"Tudo correto?\n"
        f"1️⃣ Confirmar pedido\n"
        f"2️⃣ Corrigir"
    )
    
    await responder_usuario(telefone, resumo)
