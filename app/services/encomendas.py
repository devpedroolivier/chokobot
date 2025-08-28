# app/services/encomendas.py
from datetime import datetime
from app.models.entregas import salvar_entrega
from app.utils.mensagens import responder_usuario
from app.utils.banco import salvar_encomenda_sqlite
from app.services.estados import estados_entrega
from app.config import DOCES_URL  # mantido por compatibilidade
from app.services.precos import calcular_total, montar_resumo, parse_doces_input

# === ALIASES DE PRODUTO (evita KeyError por variações de digitação) ===
TORTAS_ALIASES = {
    "argentina": "Argentina",
    "argentino": "Argentina",
    "banoffee": "Banoffee",
    "cheesecake": "Cheesecake Tradicional",
    "cheesecake tradicional": "Cheesecake Tradicional",
    "cheesecake pistache": "Cheesecake Pistache",
    "pistache": "Cheesecake Pistache",
    "citrus pie": "Citrus Pie",
    "limao": "Limão",
    "limão": "Limão",
}

REDONDOS_ALIASES = {
    "lingua de gato": "Língua de Gato",
    "língua de gato": "Língua de Gato",
    "branco camafeu": "Branco Camafeu",
    "belga": "Belga",
    "naked cake": "Naked Cake",
    "red velvet": "Red Velvet",
}

# encomendas.py – substitua no GOUMERT_ALIASES
GOUMERT_ALIASES = {
    "belga": "Belga",
    "floresta negra": "Floresta Negra",
    "língua de gato": "Língua de Gato",
    "lingua de gato": "Língua de Gato",
    "ninho com morango": "Ninho com Morango",          # <- “com” para casar com precos.INGLES
    "ninho c/ morango": "Ninho com Morango",
    "nozes com doce de leite": "Nozes com Doce de Leite",
    "nozes c/ doce de leite": "Nozes com Doce de Leite",
    "olho de sogra": "Olho de Sogra",
    "red velvet": "Red Velvet",
}


def _normaliza_produto(linha: str, nome: str) -> str | None:
    key = (nome or "").strip().lower()
    if linha == "torta":
        return TORTAS_ALIASES.get(key)
    if linha == "redondo":
        return REDONDOS_ALIASES.get(key)
    if linha == "gourmet":
        return GOUMERT_ALIASES.get(key)
    return None


TAMANHO_MAP = {
    "b3": "B3", "mini": "B3", "15": "B3",
    "b4": "B4", "pequeno": "B4", "30": "B4",
    "b6": "B6", "medio": "B6", "médio": "B6", "50": "B6",
    "b7": "B7", "grande": "B7", "80": "B7",
}

def _valida_data(txt: str) -> bool:
    try:
        datetime.strptime(txt.strip(), "%d/%m/%Y"); return True
    except: return False

def _valida_hora(txt: str) -> bool:
    try:
        datetime.strptime(txt.strip(), "%H:%M"); return True
    except: return False

def _normaliza_tamanho(txt: str) -> str:
    t = txt.strip().lower()
    return TAMANHO_MAP.get(t, t.upper())

def _monta_pedido_final(dados: dict) -> dict:
    """
    Constrói o dicionário 'pedido' conforme a linha escolhida.
    Também inclui campos de doces quando existirem.
    """
    linha = dados.get("linha") or "normal"

    base = {
        "kit_festou": bool(dados.get("kit_festou")),
        "quantidade": 1,
        "data_entrega": dados.get("data_entrega"),
        "horario_retirada": dados.get("horario_retirada"),
        "doces_itens": dados.get("doces_itens", []),
        "doces_total": dados.get("doces_total", 0.0),
    }

    if linha in ["normal", "pronta_entrega"] or ("tamanho" in dados and not dados.get("produto")):
        # B3/B4/B6/B7
        adicional_txt = (dados.get("adicional") or "").strip().lower()
        fruta_nozes = None if adicional_txt in ["", "nenhum", "nao", "não"] else (dados.get("adicional") or "").title()
        desc = dados.get("descricao") or f'{dados.get("massa", "")} | {dados.get("recheio")} + {dados.get("mousse")}'
        base.update({
            "categoria": "tradicional",
            "tamanho": dados.get("tamanho"),
            "fruta_ou_nozes": fruta_nozes,
            "descricao": desc.strip(),
        })
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
    base.update({"categoria": "tradicional", "tamanho": dados.get("tamanho"), "fruta_ou_nozes": None, "descricao": dados.get("descricao", "")})
    return base


async def processar_encomenda(telefone, texto, estado, nome_cliente):
    etapa = estado["etapa"]
    dados = estado.setdefault("dados", {})

    # ====== ETAPA 1 – ESCOLHA DA LINHA ======
    if etapa == 1:
        if texto in ["1", "normal", "personalizado", "montar", "monte seu bolo"]:
            estado["linha"] = "normal"
            dados["linha"] = "normal"
            estado["etapa"] = 2
            await responder_usuario(
                telefone,
                "🍰 *Monte seu bolo!*\n\n"
                "1️⃣ Escolha a *massa*:\n- Branca\n- Chocolate\n- Mesclada"
            )
            return

        if texto in ["2", "gourmet"]:
            estado["linha"] = "gourmet"
            estado["etapa"] = "gourmet"
            await responder_usuario(
                telefone,
                "✨ *Linha Gourmet:*\n"
                "- Bolo Inglês (Belga, Floresta Negra, Língua de Gato, Ninho com Morango, Nozes com Doce de Leite, Olho de Sogra, Red Velvet)\n"
                "📷 Fotos/preços: https://keepo.io/boloschoko/\n\n"
                "📝 Digite o *nome do bolo* desejado:"
            )
            return


        if texto in ["3", "p6", "redondo", "bolo redondo"]:
            estado["linha"] = "redondo"
            dados["linha"] = "redondo"
            estado["etapa"] = "gourmet"
            await responder_usuario(
                telefone,
                "🍥 *Bolos Redondos P6 (serve 20):*\n"
                "- Língua de Gato de Chocolate\n"
                "- Língua de Gato de Chocolate Branco\n"
                "- Língua de Gato Branco Camafeu\n"
                "- Belga\n- Naked Cake\n- Red Velvet\n\n"
                "📷 Fotos/preços: https://keepo.io/boloschoko/\n\n"
                "📝 Digite o *nome do bolo* desejado:"
            )
            return


        if texto in ["4", "torta", "tortas"]:
            estado["linha"] = "torta"
            dados["linha"] = "torta"
            estado["etapa"] = "gourmet"
            await responder_usuario(
                telefone,
                "🥧 *Tortas (serve 16):* Argentina, Banoffee, Cheesecake Tradicional/Pistache, Citrus Pie, Limão\n"
                "📷 Fotos/preços: https://keepo.io/boloschoko/\n\n"
                "📝 Digite o *nome da torta* desejada:"
            )
            return

        if texto in ["5", "pronta entrega", "pronta", "pronta-entrega"]:
            estado["linha"] = "pronta_entrega"
            estado["etapa"] = "pronta_item"
            await responder_usuario(
                telefone,
                "📦 *Pronta entrega de hoje:*\n\n"
                "🎂 B3 serve até 15 pessoas\n"
                "Mesclado Brigadeiro com Ninho\n"
                "$120\n\n"
                "Adicione mais $35 e leve o Kit Festou🎉\n"
                "25 brigadeiros\n"
                "1 Balão 🎈 Personalizado\n\n"
                "🎂 B4 serve até 30 pessoas\n"
                "Mesclado Brigadeiro com Ninho\n"
                "$180\n\n"
                "Adicione mais $35 e leve o Kit Festou🎉\n"
                "25 brigadeiros\n"
                "1 Balão 🎈 Personalizado\n\n"
                "📝 Digite *B3* ou *B4*:"
            )
            return


        # fallback
        await responder_usuario(
            telefone,
            "🎂 *Escolha uma linha para começar:*\n"
            "1️⃣ Monte seu bolo\n"
            "2️⃣ Linha Gourmet\n"
            "3️⃣ Bolos Redondos (P6)\n"
            "4️⃣ Tortas\n"
            "5️⃣ Pronta Entrega"
        )
        return

    # ====== ETAPA 2 – MASSA ======
    if etapa == 2:
        massas_validas = ["branca", "chocolate", "mesclada"]
        massa = texto.strip().lower()
        if massa not in massas_validas:
            await responder_usuario(telefone, "⚠️ Massa inválida. Escolha: Branca | Chocolate | Mesclada")
            return
        dados["massa"] = massa.capitalize()
        estado["etapa"] = 3
        await responder_usuario(
            telefone,
            "🍫 *Escolha 1 recheio:*\n"
            "- Beijinho\n- Brigadeiro\n- Brigadeiro de Nutella\n"
            "- Brigadeiro Branco\n- Branco Gourmet\n- Branco de Ninho\n"
            "- Casadinho\n- Doce de Leite\n\n"
            "📌 *Escolha 1 mousse:*\n"
            "- Ninho (Trufa Branca) ou Chocolate (Trufa Preta)\n\n"
            "📝 Envie juntos no formato: *Brigadeiro + Ninho*"
        )
        return

    # ====== ETAPA 3 – RECHEIO + MOUSSE ======
    if etapa == 3:
        if "+" not in texto:
            await responder_usuario(telefone, "⚠️ Envie no formato: *Brigadeiro + Ninho*")
            return
        recheio, mousse = map(str.strip, texto.split("+", 1))
        dados["recheio"] = recheio
        dados["mousse"] = mousse
        estado["etapa"] = 4
        await responder_usuario(
            telefone,
            "🍓 Deseja adicionar *fruta ou noz*? (tem adicional)\n"
            "- Morango | Abacaxi | Ameixa | Nozes | Cereja\n"
            "Ou digite *não* para pular."
        )
        return

    # ====== ETAPA 4 – ADICIONAL ======
    if etapa == 4:
        dados["adicional"] = texto if texto.lower() != "não" else "Nenhum"
        estado["etapa"] = 5
        await responder_usuario(
            telefone,
            "📏 *Escolha o tamanho* (digite):\n"
            "- B3 (serve até 15) — R$120\n"
            "- B4 (serve até 30) — R$180\n"
            "- B6 (serve até 50) — R$300\n"
            "- B7 (serve até 80) — R$380"
        )
        return

    # ====== ETAPA 5 – TAMANHO → DATA → HORA ======
    if etapa == 5:
        dados["tamanho"] = _normaliza_tamanho(texto)
        estado["etapa"] = "data_entrega"
        await responder_usuario(telefone, "📆 Informe a *data de retirada/entrega* (DD/MM/AAAA):")
        return

    if etapa == "data_entrega":
        if not _valida_data(texto):
            await responder_usuario(telefone, "⚠️ Data inválida. Use o formato *DD/MM/AAAA*.")
            return
        dados["data_entrega"] = texto.strip()
        estado["etapa"] = "hora_retirada"
        await responder_usuario(telefone, "⏰ Informe o *horário de retirada* (HH:MM 24h):")
        return

    if etapa == "hora_retirada":
        if not _valida_hora(texto):
            await responder_usuario(telefone, "⚠️ Hora inválida. Use o formato *HH:MM* (24h).")
            return
        dados["horario_retirada"] = texto.strip()
        estado["etapa"] = "doces_oferta"
        # mensagem simplificada + link novo
        await responder_usuario(
            telefone,
            "🍬 Deseja adicionar *doces* ao pedido? Responda *sim* ou *não*.\n"
            "Cardápio: https://bit.ly/cardapiodoceschoko"
        )
        return

    # ====== DOCES — oferta ======
    if etapa == "doces_oferta":
        if texto.strip().lower() in ["sim", "s", "yes"]:
            estado["etapa"] = "doces_captura"
            await responder_usuario(
                telefone,
                "Envie os doces (pode mandar vários itens separando por ';' ou pulando linha).\n"
                "Ex.: *Brigadeiro de Ninho x25; Bombom Prestígio x30*"
            )
            return
        else:
            estado["etapa"] = 6  # pula doces
            await responder_usuario(
                telefone,
                "📦 Como você prefere receber?\n"
                "1️⃣ Retirar na loja\n"
                "2️⃣ Receber em casa (taxa de entrega: R$ 10,00)"
            )
            return

    # ====== DOCES — captura ======
    if etapa == "doces_captura":
        itens, total_doces = parse_doces_input(texto)
        dados["doces_itens"] = itens
        dados["doces_total"] = total_doces
        estado["etapa"] = 6
        await responder_usuario(
            telefone,
            "✅ Doces adicionados!\n"
            "Agora, escolha a forma de receber:\n"
            "1️⃣ Retirar na loja\n"
            "2️⃣ Receber em casa (taxa de entrega: R$ 10,00)"
        )
        return

    # ====== ETAPA 6 – RETIRADA OU ENTREGA ======
    if etapa == 6:
        # 1) RETIRADA -> confirma antes de salvar
        if texto in ["1", "retirada", "retirar", "loja", "r"]:
            pedido = _monta_pedido_final(dados)
            total, serve = calcular_total(pedido)
            pedido["valor_total"] = total
            pedido["serve_pessoas"] = serve

            dados["pedido_preview"] = pedido
            estado["modo_recebimento"] = "retirada"
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

        # 2) ENTREGA -> coleta endereço primeiro; confirmação vai acontecer no serviço de entregas
        if texto in ["2", "entregar", "entrega", "receber", "e"]:
            pedido = _monta_pedido_final(dados)
            total, serve = calcular_total(pedido)
            # >>> TAXA DE ENTREGA <<<
            total += 10.0  # R$ 10,00
            pedido["valor_total"] = total
            pedido["serve_pessoas"] = serve

            # salvamos a encomenda (para ter ID) e seguimos para coleta de endereço
            dados.update(pedido)
            encomenda_id = salvar_encomenda_sqlite(telefone, dados, nome_cliente)

            # guarda o pedido para confirmar depois que o endereço for informado
            estados_entrega[telefone] = {
                "etapa": 1,
                "dados": {
                    "encomenda_id": encomenda_id,
                    "data": dados["data_entrega"],
                    "pedido": pedido,
                    "endereco": "",
                    "referencia": ""
                },
                "nome": nome_cliente
            }

            await responder_usuario(telefone, "📍 Informe o *endereço completo* para entrega (Rua, número, bairro):")
            return

        await responder_usuario(telefone, "Por favor, escolha:\n1️⃣ Retirar na loja\n2️⃣ Receber em casa (taxa de entrega: R$ 10,00)")
        return

    
    # ====== PRONTA ENTREGA ======
    if etapa == "pronta_item":
        escolha = texto.strip().upper()
        if escolha not in ["B3", "B4"]:
            await responder_usuario(telefone, "⚠️ Responda com *B3* ou *B4*.")
            return
        dados["tamanho"] = escolha
        estado["etapa"] = "pronta_kit"
        await responder_usuario(telefone, "Deseja adicionar o *Kit Festou* (+R$35)? Responda *sim* ou *não*.")
        return

    if etapa == "pronta_kit":
        dados["kit_festou"] = texto.strip().lower() in ["sim", "s", "yes"]
        estado["etapa"] = "pronta_data"
        await responder_usuario(telefone, "📆 Informe a *data* (DD/MM/AAAA):")
        return

    if etapa == "pronta_data":
        if not _valida_data(texto):
            await responder_usuario(telefone, "⚠️ Data inválida. Use o formato *DD/MM/AAAA*.")
            return
        dados["data_entrega"] = texto.strip()
        estado["etapa"] = "pronta_hora"
        await responder_usuario(telefone, "⏰ Informe o *horário de retirada* (HH:MM 24h):")
        return

    if etapa == "pronta_hora":
        if not _valida_hora(texto):
            await responder_usuario(telefone, "⚠️ Hora inválida. Use o formato *HH:MM* (24h).")
            return
        dados["horario_retirada"] = texto.strip()

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
        estado["modo_recebimento"] = "retirada"  # pronta entrega = retirada
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
        opc = texto.strip().lower()

        if opc in ["1", "confirmar", "ok", "c", "sim", "s", "confirmar pedido", "pedido confirmado", "confirmo"]:
            print(f"✅ DEBUG: Pedido confirmado via RETIRADA para {telefone}")
            pedido = dados.get("pedido_preview")
            if not pedido:
                await responder_usuario(telefone, "Não encontrei o pedido para confirmar. Vamos recomeçar do início. 🙂")
                estado["etapa"] = 1
                estado["dados"] = {}
                return

            # Persiste a encomenda e registra retirada
            dados.update(pedido)
            encomenda_id = salvar_encomenda_sqlite(telefone, dados, nome_cliente)
            salvar_entrega(
                encomenda_id=encomenda_id,
                tipo="retirada",
                data_agendada=dados.get("data_entrega"),
                status="Retirar na loja"
            )

            await responder_usuario(telefone, "✅ Pedido confirmado com sucesso!")
            return "finalizar"


        elif opc in ["2", "corrigir", "ajustar", "editar"]:
            # Estratégia simples: reiniciar montagem
            await responder_usuario(telefone, "Sem problema! Vamos refazer a montagem do pedido. 😊")
            estado["etapa"] = 1
            estado["dados"] = {}
            await responder_usuario(
                telefone,
                "🎂 *Escolha uma linha para começar:*\n"
                "1️⃣ Monte seu bolo\n"
                "2️⃣ Linha Gourmet\n"
                "3️⃣ Bolos Redondos (P6)\n"
                "4️⃣ Tortas\n"
                "5️⃣ Pronta Entrega"
            )
            return

        elif opc in ["3", "atendente", "humano", "falar", "ajuda"]:
            await responder_usuario(telefone, "Certo! Vou acionar um atendente. 👩‍🍳")
            return "finalizar"

        else:
            await responder_usuario(
                telefone,
                "Responda com:\n"
                "1️⃣ Confirmar pedido\n"
                "2️⃣ Corrigir\n"
                "3️⃣ Falar com atendente"
            )
            return

    # ====== GOURMET / REDONDO / TORTA – pega produto e segue para data ======
    if etapa == "gourmet":
        linha_escolhida = estado.get("linha")
        nome_digitado = texto.strip()
        nome_normalizado = _normaliza_produto(linha_escolhida, nome_digitado)

        # Caso especial: em Redondo, "Língua de Gato" precisa da variação
        if linha_escolhida == "redondo" and nome_normalizado == "Língua de Gato":
            estado["subetapa"] = "redondo_var_lingua"
            await responder_usuario(
                telefone,
                "Você prefere *Língua de Gato de Chocolate* ou *Língua de Gato de Chocolate Branco*?"
            )
            return

        if not nome_normalizado:
            if linha_escolhida == "torta":
                opcoes = "Argentina, Banoffee, Cheesecake Tradicional, Cheesecake Pistache, Citrus Pie, Limão"
            elif linha_escolhida == "redondo":
                opcoes = (
                    "Língua de Gato de Chocolate, "
                    "Língua de Gato de Chocolate Branco, "
                    "Língua de Gato Branco Camafeu, "
                    "Belga, Naked Cake, Red Velvet"
                )
            else:
                opcoes = (
                    "Belga, Floresta Negra, Língua de Gato, "
                    "Ninho com Morango, Nozes com Doce de Leite, "
                    "Olho de Sogra, Red Velvet"
                )
            await responder_usuario(
                telefone,
                f"⚠️ Não reconheci *{nome_digitado}*.\n"
                f"Envie exatamente um dos nomes: {opcoes}."
            )
            return


        dados["produto"] = nome_normalizado
        dados["linha"] = linha_escolhida
        estado["etapa"] = "data_entrega"
        await responder_usuario(telefone, "📆 Informe a *data* (DD/MM/AAAA):")
        return

    # Subetapa para escolher a variação de Língua de Gato (apenas Redondo)
    if estado.get("subetapa") == "redondo_var_lingua":
        escolha = texto.strip().lower()
        if "branco" in escolha:
            dados["produto"] = "Língua de Gato de Chocolate Branco"
        else:
            dados["produto"] = "Língua de Gato de Chocolate"
        dados["linha"] = "redondo"
        estado.pop("subetapa", None)
        estado["etapa"] = "data_entrega"
        await responder_usuario(telefone, "📆 Informe a *data* (DD/MM/AAAA):")
        return
