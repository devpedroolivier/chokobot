# -*- coding: utf-8 -*-
# app/services/encomendas.py
from datetime import datetime
from app.application.service_registry import get_delivery_gateway, get_order_gateway
from app.utils.mensagens import responder_usuario
from app.services.estados import estados_entrega
from app.config import DOCES_URL  # mantido por compatibilidade
from app.services.precos import TRADICIONAL_BASE, _alias_fruta, calcular_total, montar_resumo, TRADICIONAL_ADICIONAIS
from app.services.encomendas_utils import (
    TORTAS_ALIASES,
    REDONDOS_ALIASES,
    GOURMET_ALIASES,
    TAMANHO_MAP,
    LIMITE_HORARIO_ENTREGA,
    _horario_entrega_permitido,
    _linha_canonica,
    _normaliza_produto,
    _valida_data,
    parse_doces_input_flex,
    _parse_hora,
    _normaliza_tamanho,
)
import re
from app.services.precos import calcular_preco_simples



# ====== PAGAMENTO ======

MSG_ESCOLHER_FORMA = (
    "💳 *Forma de pagamento*\n"
    "1️⃣ PIX\n"
    "2️⃣ Cartão (débito/crédito)\n"
    "3️⃣ Dinheiro\n\n"
    "Digite *1*, *2* ou *3*."
)

MSG_PEDIR_TROCO = (
    "💸 Você escolheu *dinheiro*.\n"
    "Para facilitar, me diga: *troco para quanto?*\n"
    "Exemplos: 50, 100, 200."
)

def msg_resumo_pagamento(forma, troco):
    base = f"💳 Pagamento: *{forma}*"
    if forma == "Dinheiro" and troco is not None:
        base += f" — troco para *R${troco:.2f}*"
    return base


def _monta_pedido_final(dados: dict) -> dict:
    """
    Constrói o dicionário 'pedido' conforme a linha escolhida.
    Também inclui campos de doces quando existirem.
    """
    linha = _linha_canonica(dados.get("linha") or "tradicional")

    base = {
        "kit_festou": bool(dados.get("kit_festou")),
        "quantidade": 1,
        "data_entrega": dados.get("data_entrega"),
        "horario_retirada": dados.get("horario_retirada"),
        "doces_itens": dados.get("doces_itens", []),
        "doces_total": dados.get("doces_total", 0.0),
    }

    # Tradicional (com tamanho) ou quando tem tamanho e não tem produto (fallback)
    if linha in ["tradicional", "pronta_entrega"] or ("tamanho" in dados and not dados.get("produto")):
        adicional_txt = (dados.get("adicional") or "").strip().lower()
        fruta_nozes = None if adicional_txt in ["", "nenhum", "nao", "não"] else (dados.get("adicional") or "").title()
        desc = dados.get("descricao") or f'{dados.get("massa", "")} | {dados.get("recheio")} + {dados.get("mousse")}'
        base.update(
            {
                "categoria": "tradicional",
                "tamanho": dados.get("tamanho"),
                "fruta_ou_nozes": fruta_nozes,
                "descricao": (desc or "").strip(),
            }
        )
        return base

    if linha == "gourmet":
        base.update({"categoria": "ingles", "produto": dados.get("produto")})
        return base

    if linha == "redondo":
        base.update({"categoria": "redondo", "produto": dados.get("produto")})
        return base

    if linha == "torta":
        base.update({"categoria": "torta", "produto": dados.get("produto")})
        return base

    # fallback seguro
    base.update(
        {
            "categoria": "tradicional",
            "tamanho": dados.get("tamanho"),
            "fruta_ou_nozes": None,
            "descricao": dados.get("descricao", ""),
        }
    )
    return base

def _prepara_dados_para_salvar(dados: dict) -> dict:
    """
    Normaliza e prepara o dicionário 'dados' antes de salvar no banco.
    Garante consistência com o painel e evita campos nulos.
    """
    from datetime import datetime

    # cria cópia segura para não alterar o estado original do fluxo
    d = dict(dados or {})

    # — normaliza texto de descrição —
    d["descricao"] = (
        d.get("descricao")
        or d.get("sabor")
        or d.get("produto")
        or f"{d.get('massa', '')} | {d.get('recheio', '')} + {d.get('mousse', '')}"
        or "Bolo personalizado"
    ).strip()

    # — categoria coerente —
    d["categoria"] = (
        d.get("categoria")
        or d.get("linha")
        or "tradicional"
    ).strip().lower()

    # — fruta_ou_nozes e adicional unificados —
    adicional = d.get("adicional") or d.get("fruta_ou_nozes")
    if adicional in ["", None, "nenhum", "nao", "não"]:
        adicional = None
    d["fruta_ou_nozes"] = str(adicional).title() if adicional else None

    # — valor total sempre float —
    try:
        d["valor_total"] = float(d.get("valor_total") or 0)
    except:
        d["valor_total"] = 0.0

    # — kit festou como boolean —
    d["kit_festou"] = bool(str(d.get("kit_festou", "")).lower() in ["1", "true", "sim", "yes"])

    # — datas para formato ISO (YYYY-MM-DD) —
    if d.get("data_entrega"):
        try:
            d["data_entrega"] = datetime.strptime(d["data_entrega"], "%d/%m/%Y").strftime("%Y-%m-%d")
        except Exception:
            pass

    # — pagamento padronizado —
    pagamento = d.get("pagamento") or {}
    forma = pagamento.get("forma") or d.get("forma_pagamento") or "Pendente"
    troco = pagamento.get("troco_para") or d.get("troco_para")
    d["pagamento"] = {"forma": forma, "troco_para": troco}
    d["forma_pagamento"] = forma
    d["troco_para"] = troco
    try:
        d["taxa_entrega"] = float(d.get("taxa_entrega") or 0)
    except:
        d["taxa_entrega"] = 0.0

    return d

async def _iniciar_entrega(telefone, dados, nome_cliente, cliente_id):
    """
    Prepara o pedido para entrega, salva no banco e inicia o fluxo de endereço.
    """
    order_gateway = get_order_gateway()
    if not _horario_entrega_permitido(dados.get("horario_retirada")):
        await responder_usuario(
            telefone,
            f"🚚 As entregas são realizadas até as *{LIMITE_HORARIO_ENTREGA}*.\n"
            f"Informe um horário até *{LIMITE_HORARIO_ENTREGA}* ou escolha *retirada na loja*."
        )
        return

    pedido = _monta_pedido_final(dados)
    pedido["doces_forminha"] = dados.get("doces_forminha", [])
    pedido["pagamento"] = dados.get("pagamento", {})

    total, serve = calcular_total(pedido)
    taxa = float(dados.get("taxa_entrega") or 10.0)
    total += taxa

    pedido["taxa_entrega"] = taxa
    pedido["valor_total"] = total
    pedido["serve_pessoas"] = serve
    pedido["modo_recebimento"] = "entrega"
    pedido["endereco"] = dados.get("endereco", "")
    pedido["referencia"] = dados.get("referencia", "")

    dados.update(pedido)
    dados["taxa_entrega"] = taxa

    dados = _prepara_dados_para_salvar(dados)
    print(f"💾 Salvando encomenda normalizada ({dados.get('linha', 'n/d')}) — Cliente: {nome_cliente}")
    encomenda_id = order_gateway.create_order(
        phone=telefone,
        dados=dados,
        nome_cliente=nome_cliente,
        cliente_id=cliente_id,
    )

    estados_entrega[telefone] = {
        "etapa": 1,
        "dados": {
            "encomenda_id": encomenda_id,
            "data": dados["data_entrega"],
            "pedido": pedido,
            "endereco": "",
            "referencia": "",
        },
        "nome": nome_cliente,
    }

    await responder_usuario(
        telefone,
        "📍 Informe o *endereço completo* para entrega (Rua, número, bairro):"
    )

async def processar_encomenda(telefone, texto, estado, nome_cliente, cliente_id):
    """
    Roteia o fluxo de encomendas.
    Observação: comandos globais 'menu' e 'cancelar' são tratados no handler principal.
    """
    order_gateway = get_order_gateway()
    delivery_gateway = get_delivery_gateway()
    etapa = estado["etapa"]
    dados = estado.setdefault("dados", {})
    
    # ====== ETAPA 1 – ESCOLHA DA LINHA ======
    if etapa == 1:
        t = (texto or "").strip().lower()

        # 1️⃣ Monte seu bolo
        if t in ["1", "monte seu bolo", "normal", "tradicional", "personalizado"]:
            estado["linha"] = "tradicional"
            dados["linha"] = "tradicional"
            estado["etapa"] = 2
            await responder_usuario(
                telefone,
                "🍰 *Monte seu bolo tradicional!*\n\n"
                "1️⃣ Escolha a *massa*:\n- Branca\n- Chocolate\n- Mesclada",
            )
            return

        # 2️⃣ Linha Gourmet (Inglês e Redondo)
        # 2️⃣ Linha Gourmet (Inglês e Redondo)
        if t in ["2", "gourmet", "ingles", "redondo", "p6"]:
            estado["linha"] = "gourmet"
            dados["linha"] = "gourmet"
            estado["etapa"] = "gourmet_tipo"
            await responder_usuario(
                telefone,
                "✨ *Linha Gourmet*\n\n"
                "Escolha o tipo de bolo:\n"
                "1️⃣ Inglês (formato inglês)\n"
                "2️⃣ Redondo (P6 – serve até 20 pessoas)\n\n"
                "📝 Digite *1* ou *2* para escolher."
            )
            return


        # 3️⃣ Linha Mesversário ou Revelação
        if t in ["3", "mesversario", "mesversário", "revelacao", "revelação"]:
            estado["linha"] = "mesversario"
            dados["linha"] = "mesversario"
            estado["etapa"] = "mesversario"  # 🔹 fluxo personalizado
            dados["subetapa"] = "tamanho"
            await responder_usuario(
                telefone,
                "🎉 *Linha Mesversário, Personalizados e Chá Revelação!*\n\n"
                "🎂 P6 Redondo — Serve 20 pessoas — R$165\n"
                "🎂 P4 Redondo — Serve 8 pessoas — R$120\n\n"
                "📝 Digite *P6* ou *P4* para escolher o tamanho."
            )
            return

        # 4️⃣ Linha Individual Baby Cake
        if t in ["4", "individual", "baby cake", "babycake"]:
            estado["linha"] = "babycake"
            dados["linha"] = "babycake"
            estado["etapa"] = "babycake"
            await responder_usuario(
                telefone,
                "🧁 *Linha Individual Baby Cake*\n\n"
                "📏 Tamanho individual (~300g)\n\n"
                "Opções de sabores:\n"
                "1️⃣ Branco com Doce de Leite e Creme Mágico (chocolate branco)\n"
                "2️⃣ Branco com Belga e Creme Mágico (chocolate branco)\n\n"
                "📝 Digite *1* ou *2* para escolher o sabor."
            )
            return

        # 5️⃣ Tortas
        if t in ["5", "torta", "tortas"]:
            estado["linha"] = "torta"
            dados["linha"] = "torta"
            estado["etapa"] = "gourmet"
            await responder_usuario(
                telefone,
                "🥧 *Tortas (serve 16 fatias)*\n\n"
                "• Argentina — R$130\n"
                "• Banoffee — R$130\n"
                "• Cheesecake Tradicional Versão Baixa — R$120\n"
                "• Cheesecake Tradicional Versão Alta — R$160\n"
                "• Cheesecake Pistache — R$250\n"
                "• Citrus Pie — R$150\n"
                "• Limão — R$150\n\n"
                "📷 Fotos/preços: https://keepo.io/boloschoko/\n\n"
                "📝 Digite o *nome da torta* desejada exatamente como acima:"
            )
            return
        
        # 6️⃣ Linha Simples
        if t in ["6", "simples", "bolo simples"]:
            estado["linha"] = "simples"
            dados["linha"] = "simples"
            estado["etapa"] = "simples"
            await responder_usuario(
                telefone,
                "🍰 *Linha Simples* — serve 8 fatias\n\n"
                "Sabores disponíveis:\n"
                "1️⃣ Chocolate\n"
                "2️⃣ Cenoura\n\n"
                "📝 Digite *1* ou *2* para escolher o sabor."
            )
            return

        # fallback
        await responder_usuario(
            telefone,
            "🎂 *Escolha uma linha para começar:*\n"
            "1️⃣ Monte seu bolo (B3 | B4 | B6 | B7)\n"
            "2️⃣ Linha Gourmet (Inglês ou Redondo P6)\n"
            "3️⃣ Linha Mesversário ou Revelação\n"
            "4️⃣ Linha Individual Baby Cake\n"
            "5️⃣ Tortas\n"
            "6️⃣ Linha Simples\n"
            "7️⃣ Cestas Box"
        )
        return

    # ====== ETAPA 2 – MASSA ======
    if etapa == 2:
        massas_validas = ["branca", "chocolate", "mesclada"]
        massa = (texto or "").strip().lower()
        if massa not in massas_validas:
            await responder_usuario(telefone, "⚠️ Massa inválida. Escolha: Branca | Chocolate | Mesclada")
            return

        dados["massa"] = massa.capitalize()
        estado["etapa"] = 3

        await responder_usuario(
            telefone,
            "🍫 *Escolha 1 recheio:*\n"
            "- Beijinho\n- Brigadeiro\n- Brigadeiro de Nutella\n"
            "- Brigadeiro Branco Gourmet\n- Brigadeiro Branco de Ninho\n"
            "- Casadinho (Brigadeiro Branco + Brigadeiro Preto)\n"
            "- Doce de Leite\n\n"
            "📌 *Escolha 1 mousse:*\n"
            "- Ninho\n- Trufa Branca\n- Chocolate\n- Trufa Preta\n\n"
            "📝 Envie juntos no formato: *Brigadeiro + Ninho*\n\n"
            "💡 *Observação:* O recheio *Casadinho* já combina Brigadeiro Branco e Preto — "
            "por isso, não precisa escolher mousse adicional. 😉"
        )
        return

    # ====== ETAPA 3 – RECHEIO + MOUSSE ======
    if etapa == 3:
        texto_limpo = (texto or "").strip()
        # caso especial: Casadinho
        if "casadinho" in texto_limpo.lower():
            dados["recheio"] = "Casadinho (Brigadeiro Branco + Brigadeiro Preto)"
            dados["mousse"] = None  # pular mousse
            estado["etapa"] = 4
            await responder_usuario(
                telefone,
                "🍫 *Recheio Casadinho selecionado!*\n"
                "👉 Esse sabor já combina dois recheios (Brigadeiro Branco e Preto), "
                "por isso não precisa de mousse adicional.\n"
                "📏 Agora escolha o *tamanho* (digite):\n"
                "- B3 (serve até 15 pessoas) — R$120\n"
                "- B4 (serve até 30 pessoas) — R$180\n"
                "- B6 (serve até 50 pessoas) — R$300\n"
                "- B7 (serve até 80 pessoas) — R$380"
            )
            return

        # padrão (demais recheios + mousse)
        if "+" not in texto_limpo:
            await responder_usuario(telefone, "⚠️ Envie no formato: *Brigadeiro + Ninho*")
            return

        recheio, mousse = map(str.strip, texto_limpo.split("+", 1))
        dados["recheio"] = recheio
        dados["mousse"] = mousse
        estado["etapa"] = 4
        await responder_usuario(
            telefone,
            "📏 *Escolha o tamanho* (digite):\n"
            "- B3 (serve até 15 pessoas) — R$120\n"
            "- B4 (serve até 30 pessoas) — R$180\n"
            "- B6 (serve até 50 pessoas) — R$300\n"
            "- B7 (serve até 80 pessoas) — R$380",
        )
        return

    # ====== ETAPA GOURMET – ESCOLHA DO TIPO ======
    if etapa == "gourmet_tipo":
        escolha = (texto or "").strip().lower()

        if escolha in ["1", "ingles", "inglês"]:
            dados["sub_linha"] = "ingles"
            estado["etapa"] = "gourmet_ingles"
            await responder_usuario(
                telefone,
                "🇬🇧 *Linha Gourmet – Formato Inglês*\n\n"
                "Sabores e preços (~serve 10 pessoas):\n"
                "• Belga — R$130\n"
                "• Floresta Negra — R$140\n"
                "• Língua de Gato — R$130\n"
                "• Ninho com Morango — R$140\n"
                "• Nozes com Doce de Leite — R$140\n"
                "• Olho de Sogra — R$120\n"
                "• Red Velvet — R$120\n\n"
                "📷 Fotos/preços: https://keepo.io/boloschoko/\n"
                "📝 Digite o *nome do bolo inglês* desejado exatamente como acima."
            )
            return

        # ====== ETAPA GOURMET – INGLÊS (Kit Festou opcional) ======
        if etapa == "gourmet_ingles":
            produto = _normaliza_produto("gourmet", texto)

            if not produto:
                await responder_usuario(
                    telefone,
                    "⚠️ Bolo não reconhecido. Tente novamente.\n"
                    "Sugestões: Belga, Floresta Negra, Língua de Gato, Ninho com Morango, "
                    "Nozes com Doce de Leite, Olho de Sogra, Red Velvet"
                )
                return

            dados["produto"] = produto
            estado["etapa"] = "gourmet_kit"
            await responder_usuario(
                telefone,
                "🎉 Deseja adicionar o *Kit Festou* (25 brigadeiros + 1 balão personalizado 🎈) (+R$35)?\n"
                "1️⃣ Sim\n2️⃣ Não"
            )
            return

        if etapa == "gourmet_kit":
            resposta = (texto or "").strip().lower()
            dados["kit_festou"] = resposta in ["1", "sim", "s", "yes"]

            # Após resposta, segue fluxo normal (pede data)
            estado["etapa"] = "data_entrega"
            await responder_usuario(
                telefone,
                "📆 Informe a *data de retirada/entrega* (DD/MM/AAAA):"
            )
            return


        elif escolha in ["2", "redondo", "p6"]:
            dados["sub_linha"] = "redondo"
            estado["etapa"] = "gourmet_redondo"
            await responder_usuario(
                telefone,
                "🎂 *Linha Gourmet – Redondo P6 (~serve 20 pessoas)*\n\n"
                "Sabores e preços:\n"
                "• Língua de Gato de Chocolate — R$165\n"
                "• Língua de Gato de Chocolate Branco — R$165\n"
                "• Língua de Gato Branco Camafeu — R$175\n"
                "• Belga — R$180\n"
                "• Naked Cake — R$175\n"
                "• Red Velvet — R$220\n\n"
                "📷 Fotos/preços: https://keepo.io/boloschoko/\n"
                "📝 Digite o *nome do bolo redondo* desejado exatamente como acima."
            )
            return

        else:
            await responder_usuario(
                telefone,
                "⚠️ Escolha inválida. Digite *1* (Inglês) ou *2* (Redondo)."
            )
            return

    # ====== ETAPA 4 – TAMANHO ======
    if etapa == 4:
        dados["tamanho"] = _normaliza_tamanho(texto)
        estado["etapa"] = 5
        await responder_usuario(
            telefone,
            "🍓 Deseja adicionar *fruta ou nozes*? (tem adicional)\n\n"
            "- Morango | Ameixa | Nozes | Cereja | Abacaxi\n"
            "💡 Digite *valores* para consultar a tabela de preços por tamanho.\n\n"
            "Ou digite *não* para pular."
        )
        return
    
    # ====== ETAPA 5 – ADICIONAL ======
    if etapa == 5:
        adicional_txt = (texto or "").strip().lower()

        # consulta de valores (somente o acréscimo)
        if adicional_txt in ["valores", "consultar", "consultar valores", "tabela"]:
            msg = ["💰 *Valores de adicionais (acréscimos sobre o bolo):*", ""]
            for tam, opcoes in TRADICIONAL_ADICIONAIS.items():
                preco_base = TRADICIONAL_BASE[tam]["preco"]
                msg.append(f"📏 {tam}")
                for fruta, preco_total in opcoes.items():
                    adicional = preco_total - preco_base
                    msg.append(f"- {fruta} +R${adicional:.2f}")
                msg.append("")
            await responder_usuario(telefone, "\n".join(msg).strip())
            return

        if adicional_txt in ["", "nenhum", "nao", "não"]:
            dados["adicional"] = None
        else:
            dados["adicional"] = _alias_fruta(texto)  # normaliza para "Morango", "Nozes", etc.

        estado["etapa"] = "data_entrega"
        await responder_usuario(
            telefone,
            "📆 Informe a *data de retirada/entrega* (DD/MM/AAAA):"
        )
        return

    # (Bloco de 'etapa == 5' para normalização de tamanho removido — duplicado)

    # ====== ETAPA GOURMET – INGLÊS (Kit Festou opcional) ======
    if etapa == "gourmet_ingles":
        produto = _normaliza_produto("gourmet", texto)

        if not produto:
            await responder_usuario(
                telefone,
                "⚠️ Bolo não reconhecido. Tente novamente.\n"
                "Sugestões: Belga, Floresta Negra, Língua de Gato, Ninho com Morango, "
                "Nozes com Doce de Leite, Olho de Sogra, Red Velvet"
            )
            return

        dados["produto"] = produto
        estado["etapa"] = "gourmet_kit"
        await responder_usuario(
            telefone,
            "🎉 Deseja adicionar o *Kit Festou* (25 brigadeiros + 1 balão personalizado 🎈) (+R$35)?\n"
            "1️⃣ Sim\n2️⃣ Não"
        )
        return

    if etapa == "gourmet_kit":
        resposta = (texto or "").strip().lower()
        dados["kit_festou"] = resposta in ["1", "sim", "s", "yes"]

        # Após resposta, segue fluxo normal (pede data)
        estado["etapa"] = "data_entrega"
        await responder_usuario(
            telefone,
            "📆 Informe a *data de retirada/entrega* (DD/MM/AAAA):"
        )
        return

    # ====== ETAPA GOURMET/REDONDO/TORTA – CAPTURA PRODUTO ======
    if etapa in ["gourmet", "gourmet_redondo"]:
        linha = estado.get("linha")
        sub_linha = dados.get("sub_linha")  # ingles ou redondo
        produto = _normaliza_produto(linha, texto)

        if not produto:
            if sub_linha == "ingles":
                msg_lista = (
                    "Belga, Floresta Negra, Língua de Gato, Ninho com Morango, "
                    "Nozes com Doce de Leite, Olho de Sogra, Red Velvet"
                )
            elif sub_linha == "redondo":
                msg_lista = (
                    "Língua de Gato de Chocolate, Língua de Gato de Chocolate Branco, "
                    "Língua de Gato Branco Camafeu, Belga, Naked Cake, Red Velvet"
                )
            elif linha == "torta":
                msg_lista = (
                    "Argentina, Banoffee, Cheesecake Tradicional Versão Baixa, Cheesecake Tradicional Versão Alta, "
                    "Cheesecake Pistache, Citrus Pie, Limão"
                )
            else:
                msg_lista = (
                    "Belga, Floresta Negra, Língua de Gato, Ninho com Morango, "
                    "Nozes com Doce de Leite, Olho de Sogra, Red Velvet"
                )

            await responder_usuario(
                telefone,
                f"⚠️ Bolo não reconhecido. Tente novamente.\n"
                f"Sugestões: {msg_lista}"
            )
            return

        # Salva o bolo escolhido e continua o fluxo
        dados["produto"] = produto
        estado["etapa"] = "data_entrega"
        await responder_usuario(
            telefone,
            "📆 Informe a *data de retirada/entrega* (DD/MM/AAAA):"
        )
        return


    # ====== ETAPA MESVERSÁRIO / REVELAÇÃO ======
    if etapa == "mesversario":
        # Obter subetapa atual
        subetapa = dados.get("subetapa")

        # Primeira entrada — mostrar tamanhos e sabores
        if not subetapa:
            # 🔹 Define antes de enviar
            dados["subetapa"] = "tamanho"
            estado["dados"] = dados  # 🔹 garante persistência no dict global
            await responder_usuario(
                telefone,
                "🎉 *Linha Mesversário, Personalizados e Chá Revelação!*\n\n"
                "🎂 P6 Redondo — Serve 20 pessoas — R$165\n"
                "🎂 P4 Redondo — Serve 8 pessoas — R$120\n\n"
                "📝 Digite *P6* ou *P4* para escolher o tamanho."
            )
            return

        # Escolha de tamanho
        if subetapa == "tamanho":
            tam = (texto or "").strip().upper()
            if tam not in ["P4", "P6"]:
                await responder_usuario(telefone, "⚠️ Tamanho inválido. Digite *P4* ou *P6*.")
                return

            dados["tamanho"] = tam
            dados["preco_base"] = 165.0 if tam == "P6" else 120.0
            dados["serve_pessoas"] = 20 if tam == "P6" else 8
            dados["subetapa"] = "massa"
            estado["dados"] = dados
            await responder_usuario(
                telefone,
                "🍰 *Escolha a massa:*\n- Branca\n- Chocolate"
            )
            return

        # Escolha de massa
        if subetapa == "massa":
            massa = (texto or "").strip().lower()
            if massa not in ["branca", "chocolate"]:
                await responder_usuario(telefone, "⚠️ Massa inválida. Escolha: Branca | Chocolate")
                return
            dados["massa"] = massa.capitalize()
            dados["subetapa"] = "recheio"
            estado["dados"] = dados
            await responder_usuario(
                telefone,
                "🍫 *Escolha o recheio (envie o nome completo):*\n"
                "- Brigadeiro com Ninho\n"
                "- Brigadeiro de Nutella com Ninho\n"
                "- Brigadeiro e Beijinho\n"
                "- Brigadeiro Branco com Brigadeiro Preto (Casadinho)\n"
                "- Brigadeiro Branco Gourmet com Ninho\n"
                "- Brigadeiro Branco de Ninho com Ninho\n"
                "- Beijinho com Ninho\n"
                "- Doce de Leite e Brigadeiro\n"
                "- Doce de Leite com Ninho"
            )
            return

        # Escolha de recheio
        if subetapa == "recheio":
            recheio = (texto or "").strip()
            dados["recheio"] = recheio
            dados["subetapa"] = "mousse"
            estado["dados"] = dados
            await responder_usuario(
                telefone,
                "🍫 Deseja trocar o *Ninho por Mousse de Chocolate*?\n"
                "Digite *sim* ou *não*."
            )
            return

        # Troca de mousse
        if subetapa == "mousse":
            if (texto or "").strip().lower() in ["sim", "s"]:
                dados["mousse"] = "Chocolate"
            else:
                dados["mousse"] = "Ninho"
            dados["subetapa"] = None
            estado["dados"] = dados
            estado["etapa"] = "data_entrega"
            await responder_usuario(telefone, "📆 Informe a *data da festa* (DD/MM/AAAA):")
            return
        
    # ====== ETAPA BABY CAKE ======
    if etapa == "babycake":
        subetapa = dados.get("subetapa")

        # Evita reenvio duplicado do menu inicial
        if not subetapa and texto in ["4", "baby", "baby cake", "individual", "babycake"]:
            print(f"⚠️ Ignorado reenvio duplicado de menu Baby Cake ({telefone})")
            return

        # Primeira entrada — exibe o menu de sabores
        if not subetapa:
            dados["subetapa"] = "sabor"
            estado["dados"] = dados
            await responder_usuario(
                telefone,
                "🧁 *Linha Individual Baby Cake*\n\n"
                "📏 Tamanho individual (~300g)\n\n"
                "Opções de sabores:\n"
                "1️⃣ Branco com Doce de Leite e Creme Mágico (chocolate branco)\n"
                "2️⃣ Branco com Belga e Creme Mágico (chocolate branco)\n\n"
                "📝 Digite *1* ou *2* para escolher o sabor."
            )
            return

        # Escolha do sabor
        if subetapa == "sabor":
            s = (texto or "").strip()
            if s not in ["1", "2"]:
                await responder_usuario(telefone, "⚠️ Opção inválida. Digite *1* ou *2*.")
                return

            sabor = (
                "Branco com Doce de Leite e Creme Mágico (chocolate branco)"
                if s == "1"
                else "Branco com Belga e Creme Mágico (chocolate branco)"
            )

            # Salva e avança
            dados["sabor"] = sabor
            dados["subetapa"] = None
            estado["dados"] = dados
            estado["etapa"] = "babycake_frase"
            await responder_usuario(
                telefone,
                "✍️ Deseja adicionar uma *frase personalizada* no bolo?\n"
                "Exemplo: 'Feliz Aniversário!' ou 'Te amo, mãe!'\n"
                "Se não quiser, digite *não*."
            )
            return


    # ====== ETAPA BABY CAKE – FRASE ======
    if etapa == "babycake_frase":
        frase = (texto or "").strip()
        if frase.lower() not in ["", "não", "nao", "sem frase"]:
            dados["frase"] = frase
        else:
            dados["frase"] = None

        estado["dados"] = dados
        estado["etapa"] = "data_entrega"  # 👈 avança direto
        await responder_usuario(
            telefone,
            "📆 Informe a *data de entrega* (DD/MM/AAAA):"
        )
        return


    # ====== ETAPA LINHA SIMPLES ======
    if etapa == "simples":
        escolha = (texto or "").strip().lower()
        sabores = {"1": "Chocolate", "2": "Cenoura"}
        if escolha not in sabores:
            await responder_usuario(telefone, "⚠️ Escolha inválida. Digite *1* (Chocolate) ou *2* (Cenoura).")
            return

        dados["sabor"] = sabores[escolha]
        estado["etapa"] = "simples_cobertura"
        await responder_usuario(
            telefone,
            "🍫 Escolha a *cobertura*:\n"
            "1️⃣ Vulcão — R$35\n"
            "2️⃣ Simples — R$25\n\n"
            "📝 Digite *1* ou *2* para escolher."
        )
        return

    if etapa == "simples_cobertura":
        escolha = (texto or "").strip().lower()
        coberturas = {"1": "Vulcão", "2": "Simples"}

        if escolha not in coberturas:
            await responder_usuario(telefone, "⚠️ Escolha inválida. Digite *1* (Vulcão) ou *2* (Simples).")
            return

        cobertura = coberturas[escolha]

        # 🔹 Calcula preço direto pelo módulo de preços
        from app.services.precos import calcular_preco_simples
        preco = calcular_preco_simples(cobertura)

        dados["cobertura"] = cobertura
        dados["valor_total"] = preco
        dados["serve_pessoas"] = 8
        dados["categoria"] = "simples"
        dados["descricao"] = f"{dados.get('sabor')} com cobertura {cobertura}"
        dados["taxa_entrega"] = 5.0

        estado["etapa"] = "data_entrega"
        await responder_usuario(
            telefone,
            "📅 Informe a *data de retirada/entrega* (DD/MM/AAAA):"
        )
        return

    # ====== MONTA PEDIDO FINAL MESVERSÁRIO ======
    if dados.get("linha") == "mesversario" and etapa == 6:
        pedido = {
            "categoria": "mesversario",
            "tamanho": dados.get("tamanho"),
            "massa": dados.get("massa"),
            "recheio": dados.get("recheio"),
            "mousse": dados.get("mousse"),
            "quantidade": 1,
            "data_entrega": dados.get("data_entrega"),
            "horario_retirada": dados.get("horario_retirada"),
        }

        # cálculo manual (sem depender do TRADICIONAL_BASE)
        preco_base = 165.0 if pedido["tamanho"] == "P6" else 120.0
        serve = 20 if pedido["tamanho"] == "P6" else 8
        total = preco_base

        pedido["valor_total"] = total
        pedido["serve_pessoas"] = serve
        dados["pedido_preview"] = pedido
        estado["modo_recebimento"] = "retirada"
        estado["etapa"] = "confirmar_pedido"

        await responder_usuario(telefone, montar_resumo(pedido, total))
        await responder_usuario(
            telefone,
            "Está tudo correto?\n1️⃣ Confirmar pedido\n2️⃣ Corrigir"
        )
        return

    # ====== DATA / HORA (compartilhado) ======
    if etapa == "data_entrega":
        texto_limpo = (texto or "").strip()

        # Se o cliente não informar uma data, assume o dia seguinte (para encomendas)
        if not texto_limpo:
            from datetime import datetime, timedelta
            amanha = datetime.now() + timedelta(days=1)
            dados["data_entrega"] = amanha.strftime("%d/%m/%Y")

            await responder_usuario(
                telefone,
                f"📅 Nenhuma data informada — será agendada automaticamente para *amanhã ({dados['data_entrega']})*."
            )
            estado["etapa"] = "hora_retirada"
            await responder_usuario(telefone, "⏰ Informe o *horário de retirada/entrega* (HH:MM ou 24h):")
            return

        # Se o cliente digitou algo, validar normalmente
        if not _valida_data(texto_limpo):
            await responder_usuario(telefone, "⚠️ Data inválida. Use o formato *DD/MM/AAAA*.")
            return

        dados["data_entrega"] = texto_limpo
        estado["etapa"] = "hora_retirada"
        await responder_usuario(telefone, "⏰ Informe o *horário de retirada/entrega* (HH:MM ou 24h):")
        return


    if etapa == "hora_retirada":
        hora_normalizada = _parse_hora(texto)
        if not hora_normalizada:
            await responder_usuario(telefone, "⚠️ Hora inválida. Use o formato *HH:MM* (24h).")
            return
        dados["horario_retirada"] = hora_normalizada
        estado["etapa"] = "doces_oferta"
        await responder_usuario(
            telefone,
            "🍬 Deseja adicionar *doces* ao pedido? Responda *sim* ou *não*.\n"
            f"Cardápio: {DOCES_URL}",
        )
        return

        # ====== DOCES — oferta ======
    if etapa == "doces_oferta":
        if (texto or "").strip().lower() in ["sim", "s", "yes"]:
            estado["etapa"] = "doces_captura"
            await responder_usuario(
                telefone,
                "Envie os doces (pode mandar vários itens em linhas separadas).\n"
                "Ex.:\n"
                "Brigadeiro de Ninho x25\n"
                "Bombom Prestígio x30"
            )
            return
        else:
            estado["etapa"] = 6
            await responder_usuario(
                telefone,
                "📦 Como você prefere receber?\n"
                "1️⃣ Retirar na loja\n"
                f"2️⃣ Receber em casa (taxa de entrega: R$ {float(dados.get('taxa_entrega') or 10.0):.2f})",
            )
            return

    # ====== DOCES — captura ======
    if etapa == "doces_captura":
        from app.services.precos import parse_doces_input

        try:
            itens, total_doces = parse_doces_input(texto)
        except ValueError as e:
            # se o nome não for reconhecido, avisa o cliente e mantém na mesma etapa
            await responder_usuario(telefone, str(e))
            return

        dados["doces_itens"] = itens
        dados["doces_total"] = total_doces
        estado["etapa"] = "doces_tipo_forminha"
        await responder_usuario(
            telefone,
            "🎀 Deseja forminha *Tradicional* ou *Pétala*?"
        )
        return

    # ====== DOCES — tipo de forminha ======
    if etapa == "doces_tipo_forminha":
        tipo = (texto or "").strip().lower()
        if tipo not in ["tradicional", "pétala", "petala"]:
            await responder_usuario(
                telefone,
                "⚠️ Tipo inválido. Escolha: *Tradicional* ou *Pétala*."
            )
            return

        dados["doces_tipo_forminha"] = "Pétala" if "p" in tipo else "Tradicional"
        estado["etapa"] = "doces_forminha"
        await responder_usuario(
            telefone,
            "🎨 Escolha a *cor da forminha* dos doces:\n"
            "- Marrom, Amarelo, Azul Claro, Azul Escuro\n"
            "- Verde Claro, Verde Escuro, Rosa Claro, Pink\n"
            "- Laranja, Lilás, Preto ou Branco"
        )
        return

    # ====== DOCES — forminha ======
    if etapa == "doces_forminha":
        entrada = (texto or "").strip()
        cores_validas = [
            "Marrom", "Amarelo", "Azul Claro", "Azul Escuro",
            "Verde Claro", "Verde Escuro", "Rosa Claro", "Pink",
            "Laranja", "Lilás", "Preto", "Branco"
        ]

        # divide por vírgula ou quebra de linha
        cores_escolhidas = [
            c.strip().title()
            for c in re.split(r"(?:,|\n| e )", entrada, flags=re.IGNORECASE)
            if c.strip()
        ]

        # valida cada cor
        invalidas = [c for c in cores_escolhidas if c not in cores_validas]
        if invalidas:
            await responder_usuario(
                telefone,
                f"⚠️ Cor inválida: {', '.join(invalidas)}\n"
                "Escolha entre: " + ", ".join(cores_validas)
            )
            return

        # limita a 4 cores
        if len(cores_escolhidas) > 4:
            cores_escolhidas = cores_escolhidas[:4]

        dados["doces_forminha"] = cores_escolhidas
        estado["etapa"] = 6

        await responder_usuario(
            telefone,
            f"✅ Doces adicionados com forminha escolhida!\n"
            f"Tipo: {dados.get('doces_tipo_forminha', 'Tradicional')}\n"
            f"Cores escolhidas: {', '.join(cores_escolhidas)}\n\n"
            "Agora, escolha a forma de receber:\n"
            "1️⃣ Retirar na loja\n"
            f"2️⃣ Receber em casa (taxa de entrega: R$ {float(dados.get('taxa_entrega') or 10.0):.2f})",
        )
        return

    # ====== ETAPA 6 – RETIRADA OU ENTREGA ======
    if etapa == 6:
        t = (texto or "").strip().lower()

        if t in ["1", "retirada", "retirar", "loja", "r"]:
            dados["taxa_entrega"] = 0.0
            pedido = _monta_pedido_final(dados)
            pedido["doces_forminha"] = dados.get("doces_forminha", [])
            total, serve = calcular_total(pedido)
            pedido["valor_total"] = total
            pedido["serve_pessoas"] = serve
            dados["pedido_preview"] = pedido
            estado["modo_recebimento"] = "retirada"
            estado["etapa"] = "confirmar_pedido"
            await responder_usuario(telefone, montar_resumo(pedido, total))
            await responder_usuario(
                telefone,
                "Está tudo correto?\n1️⃣ Confirmar pedido\n2️⃣ Corrigir\n3️⃣ Falar com atendente",
            )
            return

        if t in ["2", "entregar", "entrega", "receber", "e"]:
            if not _horario_entrega_permitido(dados.get("horario_retirada")):
                estado["etapa"] = "ajustar_hora_entrega"
                await responder_usuario(
                    telefone,
                    f"🚚 As entregas são realizadas até as *{LIMITE_HORARIO_ENTREGA}*.\n"
                    f"Informe um novo horário até *{LIMITE_HORARIO_ENTREGA}* ou digite *retirada*."
                )
                return

            if "pagamento" not in dados:
                dados["pagamento"] = {}
                dados["pos_pagamento"] = "entrega"
                await responder_usuario(telefone, MSG_ESCOLHER_FORMA)
                estado["etapa"] = "pagamento_forma"
                return

            await _iniciar_entrega(telefone, dados, nome_cliente, cliente_id)
            return

        await responder_usuario(
            telefone,
            "Por favor, escolha:\n1️⃣ Retirar na loja\n"
            f"2️⃣ Receber em casa (taxa de entrega: R$ {float(dados.get('taxa_entrega') or 10.0):.2f})",
        )
        return

    if etapa == "ajustar_hora_entrega":
        t = (texto or "").strip().lower()

        if t in ["retirada", "retirar", "loja", "1", "r"]:
            dados["taxa_entrega"] = 0.0
            pedido = _monta_pedido_final(dados)
            pedido["doces_forminha"] = dados.get("doces_forminha", [])
            total, serve = calcular_total(pedido)
            pedido["valor_total"] = total
            pedido["serve_pessoas"] = serve
            dados["pedido_preview"] = pedido
            estado["modo_recebimento"] = "retirada"
            estado["etapa"] = "confirmar_pedido"
            await responder_usuario(telefone, montar_resumo(pedido, total))
            await responder_usuario(
                telefone,
                "Está tudo correto?\n1️⃣ Confirmar pedido\n2️⃣ Corrigir\n3️⃣ Falar com atendente",
            )
            return

        hora_normalizada = _parse_hora(texto)
        if not hora_normalizada or not _horario_entrega_permitido(hora_normalizada):
            await responder_usuario(
                telefone,
                f"⚠️ Para entrega, informe um horário válido até *{LIMITE_HORARIO_ENTREGA}* ou digite *retirada*."
            )
            return

        dados["horario_retirada"] = hora_normalizada
        estado["etapa"] = 6

        if "pagamento" not in dados:
            dados["pagamento"] = {}
            dados["pos_pagamento"] = "entrega"
            await responder_usuario(telefone, MSG_ESCOLHER_FORMA)
            estado["etapa"] = "pagamento_forma"
            return

        await _iniciar_entrega(telefone, dados, nome_cliente, cliente_id)
        return

    # ====== PRONTA ENTREGA – ITEM ======
    if etapa == "pronta_item":
        tam = _normaliza_tamanho(texto)
        if tam not in ["B3", "B4"]:
            await responder_usuario(telefone, "⚠️ Opção inválida. Digite *B3* ou *B4* (pode mandar só 3 / 4).")
            return
        dados["tamanho"] = tam
        estado["etapa"] = "pronta_kit"
        await responder_usuario(
            telefone,
            "🎉 Deseja adicionar o *Kit Festou(25 brigadeiros + 1 Balão 🎈 personalizado)* (+R$35)?\n"
            "1️⃣ Sim\n2️⃣ Não"
        )
        return

    # ====== PRONTA ENTREGA – KIT FESTOU ======
    if etapa == "pronta_kit":
        t = (texto or "").strip().lower()
        dados["kit_festou"] = t in ["1", "sim", "s", "yes"]
        estado["etapa"] = "pronta_data"
        await responder_usuario(telefone, "📆 Informe a *data de retirada* (DD/MM/AAAA):")
        return

    # ====== PRONTA ENTREGA – DATA / HORA ======
    if etapa == "pronta_data":
        if not _valida_data(texto):
            await responder_usuario(telefone, "⚠️ Data inválida. Use o formato *DD/MM/AAAA*.")
            return
        dados["data_entrega"] = (texto or "").strip()
        estado["etapa"] = "pronta_hora"
        await responder_usuario(telefone, "⏰ Informe o *horário de retirada/entrega* (HH:MM ou 24h):")
        return

    if etapa == "pronta_hora":
        if not _parse_hora(texto):
            await responder_usuario(telefone, "⚠️ Hora inválida. Use o formato *HH:MM* (24h).")
            return
        dados["horario_retirada"] = (texto or "").strip()

        # Monta pedido pronto (retirada)
        pedido = {
            "categoria": "tradicional",
            "tamanho": dados["tamanho"],
            "fruta_ou_nozes": None,
            "descricao": "Mesclado Brigadeiro + Ninho",
            "kit_festou": bool(dados.get("kit_festou")),
            "quantidade": 1,
            "data_entrega": dados["data_entrega"],
            "horario_retirada": dados["horario_retirada"],
            "doces_itens": dados.get("doces_itens", []),
            "doces_total": dados.get("doces_total", 0.0),
        }
        total, serve = calcular_total(pedido)
        pedido["valor_total"] = total
        pedido["serve_pessoas"] = serve

        dados["pedido_preview"] = pedido
        estado["modo_recebimento"] = "retirada"  # pronta entrega é retirada
        estado["etapa"] = "confirmar_pedido"

        await responder_usuario(telefone, montar_resumo(pedido, total))
        await responder_usuario(
            telefone,
            "Está tudo correto?\n"
            "1️⃣ Confirmar pedido\n"
            "2️⃣ Corrigir\n"
            "3️⃣ Falar com atendente"
        )
        return

    # ====== CONFIRMAÇÃO DO PEDIDO (retirada e pronta-entrega) ======
    if etapa == "confirmar_pedido":
        opc = (texto or "").strip().lower()

        # ====== PAGAMENTO ======
        # Se ainda não foi escolhida forma de pagamento, iniciamos aqui
        if "pagamento" not in dados:
            dados["pagamento"] = {}
            await responder_usuario(telefone, MSG_ESCOLHER_FORMA)
            estado["etapa"] = "pagamento_forma"
            return

        if opc in ["1", "confirmar", "ok", "c", "sim", "s", "confirmar pedido", "pedido confirmado", "confirmo"]:
            # Confirmar retirada
            pedido = dados.get("pedido_preview")
            if not pedido:
                await responder_usuario(
                    telefone,
                    "Não encontrei o pedido para confirmar. Vamos recomeçar do início. 🙂"
                )
                estado["etapa"] = 1
                estado["dados"] = {}
                return

            # Persiste a encomenda e registra retirada
            dados.update(pedido)
            dados = _prepara_dados_para_salvar(dados)
            print(f"💾 Salvando encomenda normalizada ({dados.get('linha', 'n/d')}) — Cliente: {nome_cliente}")
            encomenda_id = order_gateway.create_order(
                phone=telefone,
                dados=dados,
                nome_cliente=nome_cliente,
                cliente_id=cliente_id,
            )


            delivery_gateway.create_delivery(
                encomenda_id=encomenda_id,
                tipo="retirada",
                data_agendada=dados.get("data_entrega"),
                status="Retirar na loja",
            )

            await responder_usuario(
                telefone,
                "Pedido confirmado com sucesso ✅\n"
                "Obrigada por encomendar com a *Choko* ❤\n"
                "✨ Se registrar o momento nas redes sociais, lembre de nos marcar @chokodelicia"
            )
            return "finalizar"

        if opc in ["2", "corrigir", "ajustar", "editar"]:
            await responder_usuario(telefone, "Sem problema! Vamos refazer a montagem do pedido. 😊")
            estado["etapa"] = 1
            estado["dados"] = {}
            await responder_usuario(
                telefone,
                "🎂 *Escolha uma linha para começar:*\n"
                "1️⃣ Monte seu bolo (B3 | B4 | B6 | B7)\n"
                "2️⃣ Linha Gourmet (Inglês ou Redondo P6)\n"
                "3️⃣ Linha Mesversário ou Revelação\n"
                "4️⃣ Linha Individual Baby Cake\n"
                "5️⃣ Tortas"
            )
            return

        await responder_usuario(
            telefone,
            "Responda com:\n"
            "1️⃣ Confirmar pedido\n"
            "2️⃣ Corrigir"
        )
        return

    # ====== ETAPA PAGAMENTO – ESCOLHER FORMA ======
    if etapa == "pagamento_forma":
        escolha = texto.strip()
        from app.services.estados import FORMAS_PAGAMENTO
        if escolha not in FORMAS_PAGAMENTO:
            await responder_usuario(telefone, "Não entendi.\n" + MSG_ESCOLHER_FORMA)
            return

        forma = FORMAS_PAGAMENTO[escolha]
        dados["pagamento"]["forma"] = forma

        if forma == "Dinheiro":
            estado["etapa"] = "pagamento_troco"
            await responder_usuario(telefone, MSG_PEDIR_TROCO)
            return
        else:
            dados["pagamento"]["troco_para"] = None
            if dados.get("pos_pagamento") == "entrega":
                dados.pop("pos_pagamento", None)
                await responder_usuario(telefone, "✅ Pagamento registrado!\n" + msg_resumo_pagamento(forma, 0))
                await _iniciar_entrega(telefone, dados, nome_cliente, cliente_id)
                return
            estado["etapa"] = "confirmar_pedido"
            await responder_usuario(telefone, "✅ Pagamento registrado!\n" + msg_resumo_pagamento(forma, 0))
            await responder_usuario(telefone, "Confirma o pedido?\n1️⃣ Sim\n2️⃣ Corrigir")
            return

    # ====== ETAPA PAGAMENTO – TROCO ======
    if etapa == "pagamento_troco":
        valor = texto.strip().replace(",", ".")
        try:
            troco = float(valor)
            if troco <= 0:
                raise ValueError()
        except Exception:
            await responder_usuario(telefone, "Valor inválido. Informe apenas números. Exemplo: 50 ou 100.")
            return

        dados["pagamento"]["troco_para"] = troco
        if dados.get("pos_pagamento") == "entrega":
            dados.pop("pos_pagamento", None)
            await responder_usuario(telefone, "✅ Pagamento registrado!\n" + msg_resumo_pagamento("Dinheiro", troco))
            await _iniciar_entrega(telefone, dados, nome_cliente, cliente_id)
            return
        estado["etapa"] = "confirmar_pedido"
        await responder_usuario(telefone, "✅ Pagamento registrado!\n" + msg_resumo_pagamento("Dinheiro", troco))
        await responder_usuario(telefone, "Confirma o pedido?\n1️⃣ Sim\n2️⃣ Corrigir")
    return
