# app/services/encomendas.py
from datetime import datetime
from app.models.entregas import salvar_entrega
from app.utils.mensagens import responder_usuario
from app.utils.banco import salvar_encomenda_sqlite
from app.services.estados import estados_entrega, estados_encomenda
from app.config import DOCES_URL  # mantido por compatibilidade
from app.services.precos import TRADICIONAL_BASE, _alias_fruta, calcular_total, montar_resumo, parse_doces_input, TRADICIONAL_ADICIONAIS
import re
from datetime import datetime

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

# Corrigido: GOURMET_ALIASES (antes estava GOUMERT_ALIASES)
GOURMET_ALIASES = {
    "belga": "Belga",
    "floresta negra": "Floresta Negra",
    "língua de gato": "Língua de Gato",
    "lingua de gato": "Língua de Gato",
    "ninho com morango": "Ninho com Morango",
    "ninho c/ morango": "Ninho com Morango",
    "nozes com doce de leite": "Nozes com Doce de Leite",
    "nozes c/ doce de leite": "Nozes com Doce de Leite",
    "olho de sogra": "Olho de Sogra",
    "red velvet": "Red Velvet",
}

def _normaliza_produto(linha: str, nome: str) -> str | None:
    """
    Normaliza o nome do produto de acordo com a linha escolhida.
    Retorna o nome oficial ou None se não encontrou alias.
    """
    key = (nome or "").strip().lower()
    if linha == "torta":
        return TORTAS_ALIASES.get(key)
    if linha == "redondo":
        return REDONDOS_ALIASES.get(key)
    if linha == "gourmet":
        return GOURMET_ALIASES.get(key)
    return None

TAMANHO_MAP = {
    "b3": "B3", "mini": "B3", "15": "B3", "3": "B3",
    "b4": "B4", "pequeno": "B4", "30": "B4", "4": "B4",
    "b6": "B6", "medio": "B6", "médio": "B6", "50": "B6", "6": "B6",
    "b7": "B7", "grande": "B7", "80": "B7", "7": "B7",
}

def _valida_data(txt: str) -> bool:
    try:
        datetime.strptime(txt.strip(), "%d/%m/%Y")
        return True
    except Exception:
        return False

def parse_doces_input_flex(texto: str):
    """
    Interpreta a lista de doces enviada pelo cliente.
    Aceita:
      - Brigadeiro de Ninho x25
      - Brigadeiro de Ninho 25
      - Itens separados por ';' ou por Enter
    Retorna lista compatível com o resumo (nome, qtd).
    """
    itens = []
    total = 0

    # Divide por ponto e vírgula OU quebra de linha (\r\n ou \n)
    linhas = re.split(r"[;\r\n]+", texto or "")
    for linha in linhas:
        t = (linha or "").strip()
        if not t:
            continue

        # "Produto x25"
        m = re.match(r"^(.*)\s+x(\d+)$", t, re.IGNORECASE)
        if m:
            nome, qtd = m.group(1).strip(), int(m.group(2))
        else:
            # "Produto 25"
            m2 = re.match(r"^(.*)\s+(\d+)$", t)
            if m2:
                nome, qtd = m2.group(1).strip(), int(m2.group(2))
            else:
                nome, qtd = t, 1  # fallback

        itens.append({"nome": nome, "qtd": qtd})
        total += qtd

    return itens, total

def _parse_hora(txt: str) -> str | None:
    """
    Tenta normalizar a hora para HH:MM.
    Aceita formatos: '11h', '11h30', '11:30', '1130', '11'
    Retorna string HH:MM ou None se inválido.
    """
    if not txt:
        return None
    t = txt.strip().lower()

    # casos simples: 11h, 11
    m = re.match(r"^(\d{1,2})h?$", t)
    if m:
        h = int(m.group(1))
        if 0 <= h <= 23:
            return f"{h:02d}:00"

    # casos tipo 11h30
    m = re.match(r"^(\d{1,2})h(\d{2})$", t)
    if m:
        h, mnt = int(m.group(1)), int(m.group(2))
        if 0 <= h <= 23 and 0 <= mnt <= 59:
            return f"{h:02d}:{mnt:02d}"

    # casos 1130
    m = re.match(r"^(\d{1,2})(\d{2})$", t)
    if m:
        h, mnt = int(m.group(1)), int(m.group(2))
        if 0 <= h <= 23 and 0 <= mnt <= 59:
            return f"{h:02d}:{mnt:02d}"

    # HH:MM padrão
    try:
        dt = datetime.strptime(t, "%H:%M")
        return dt.strftime("%H:%M")
    except:
        return None

def _normaliza_tamanho(txt: str) -> str:
    t = (txt or "").strip().lower()
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

    # Tradicional (com tamanho) ou quando tem tamanho e não tem produto (fallback)
    if linha in ["normal", "pronta_entrega"] or ("tamanho" in dados and not dados.get("produto")):
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

async def processar_encomenda(telefone, texto, estado, nome_cliente):
    """
    Roteia o fluxo de encomendas.
    Observação: comandos globais 'menu' e 'cancelar' são tratados no handler principal.
    """
    etapa = estado["etapa"]
    dados = estado.setdefault("dados", {})

    # ====== ETAPA 1 – ESCOLHA DA LINHA ======
    if etapa == 1:
        t = (texto or "").strip().lower()

        # 1️⃣ Monte seu bolo
        if t in ["1", "monte seu bolo", "normal", "personalizado"]:
            estado["linha"] = "normal"
            dados["linha"] = "normal"
            estado["etapa"] = 2
            await responder_usuario(
                telefone,
                "🍰 *Monte seu bolo!*\n\n"
                "1️⃣ Escolha a *massa*:\n- Branca\n- Chocolate\n- Mesclada",
            )
            return

        # 2️⃣ Linha Gourmet (Inglês e Redondo)
        if t in ["2", "gourmet", "ingles", "redondo", "p6"]:
            estado["linha"] = "gourmet"
            dados["linha"] = "gourmet"
            estado["etapa"] = "gourmet"
            await responder_usuario(
                telefone,
                "✨ *LINHA GOURMET (INGLÊS E REDONDO P6)*\n"
                "- Belga, Floresta Negra, Língua de Gato, Ninho com Morango,\n"
                "Nozes com Doce de Leite, Olho de Sogra, Red Velvet\n"
                "📷 Fotos/preços: https://keepo.io/boloschoko/\n\n"
                "📝 Digite o *nome do bolo* desejado:"
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
                "🥧 *Tortas (serve 16 fatias)*: Argentina, Banoffee, Cheesecake Tradicional/Pistache, Citrus Pie, Limão\n"
                "📷 Fotos/preços: https://keepo.io/boloschoko/\n\n"
                "📝 Digite o *nome da torta* desejada:"
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
            "5️⃣ Tortas"
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
            "- Casadinho (Brigadeiro Branco + Brigadeiro Preto)\n- Doce de Leite\n\n"
            "📌 *Escolha 1 mousse:*\n"
            "- Ninho\n- Trufa Branca\n- Chocolate\n- Trufa Preta\n\n"
            "📝 Envie juntos no formato: *Brigadeiro + Ninho*",
        )

        return

  
    # ====== ETAPA 3 – RECHEIO + MOUSSE ======
    if etapa == 3:
        if "+" not in (texto or ""):
            await responder_usuario(telefone, "⚠️ Envie no formato: *Brigadeiro + Ninho*")
            return
        recheio, mousse = map(str.strip, texto.split("+", 1))
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






    # ====== ETAPA 5 – TAMANHO → DATA → HORA ======
    if etapa == 5:
        dados["tamanho"] = _normaliza_tamanho(texto)
        estado["etapa"] = "data_entrega"
        await responder_usuario(telefone, "📆 Informe a *data de retirada/entrega* (DD/MM/AAAA):")
        return

    # ====== ETAPA GOURMET/REDONDO/TORTA – CAPTURA PRODUTO ======
    if etapa == "gourmet":
        linha = estado.get("linha")
        produto = _normaliza_produto(linha, texto)
        if not produto:
            # Mensagem específica por linha para ajudar o usuário
            if linha == "gourmet":
                msg_lista = "Belga, Floresta Negra, Língua de Gato, Ninho com Morango, Nozes com Doce de Leite, Olho de Sogra, Red Velvet"
            elif linha == "redondo":
                msg_lista = "Língua de Gato (choc / branco), Branco Camafeu, Belga, Naked Cake, Red Velvet"
            else:  # torta
                msg_lista = "Argentina, Banoffee, Cheesecake Tradicional/Pistache, Citrus Pie, Limão"

            await responder_usuario(
                telefone,
                "⚠️ Produto não reconhecido. Tente novamente.\n"
                f"Sugestões: {msg_lista}"
            )
            return

        dados["produto"] = produto
        estado["etapa"] = "data_entrega"
        await responder_usuario(telefone, "📆 Informe a *data de retirada/entrega* (DD/MM/AAAA):")
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
        # ====== ETAPA BABY CAKE ======
    if etapa == "babycake":
        subetapa = dados.get("subetapa")

        # evita reenvio duplicado do menu inicial
        if not subetapa and texto in ["4", "baby", "baby cake", "individual", "babycake"]:
            print(f"⚠️ Ignorado reenvio duplicado de menu Baby Cake ({telefone})")
            return

        # Primeira entrada
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

        # Escolha de sabor
        if subetapa == "sabor":
            s = (texto or "").strip()
            if s not in ["1", "2"]:
                await responder_usuario(telefone, "⚠️ Opção inválida. Digite *1* ou *2*.")
                return

            sabor = (
                "Branco com Doce de Leite e Creme Mágico"
                if s == "1"
                else "Branco com Belga e Creme Mágico"
            )

            dados["sabor"] = sabor
            dados["subetapa"] = None
            estado["dados"] = dados
            estado["etapa"] = "babycake_frase"  # 👈 define nova etapa para não repetir
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
        if not _valida_data(texto):
            await responder_usuario(telefone, "⚠️ Data inválida. Use o formato *DD/MM/AAAA*.")
            return
        dados["data_entrega"] = (texto or "").strip()
        estado["etapa"] = "hora_retirada"
        await responder_usuario(telefone, "⏰ Informe o *horário de retirada/entrega* (HH:MM ou 24h):")
        return

    if etapa == "hora_retirada":
        if not _parse_hora(texto):
            await responder_usuario(telefone, "⚠️ Hora inválida. Use o formato *HH:MM* (24h).")
            return
        dados["horario_retirada"] = (texto or "").strip()
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
                "2️⃣ Receber em casa (taxa de entrega: R$ 10,00)",
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
            "2️⃣ Receber em casa (taxa de entrega: R$ 10,00)",
        )
        return




    # ====== ETAPA 6 – RETIRADA OU ENTREGA ======
    if etapa == 6:
        t = (texto or "").strip().lower()

        if t in ["1", "retirada", "retirar", "loja", "r"]:
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
            pedido = _monta_pedido_final(dados)
            pedido["doces_forminha"] = dados.get("doces_forminha", [])
            total, serve = calcular_total(pedido)
            total += 10.0
            pedido["valor_total"] = total
            pedido["serve_pessoas"] = serve
            
            dados.update(pedido)
            pedido["modo_recebimento"] = "entrega"
            pedido["endereco"] = dados.get("endereco", "")
            pedido["referencia"] = dados.get("referencia", "")


            # Persiste a encomenda e inicia fluxo de endereço para entrega
            encomenda_id = salvar_encomenda_sqlite(telefone, dados, nome_cliente)
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
            await responder_usuario(telefone, "📍 Informe o *endereço completo* para entrega (Rua, número, bairro):")
            return

        await responder_usuario(
            telefone,
            "Por favor, escolha:\n1️⃣ Retirar na loja\n2️⃣ Receber em casa (taxa de entrega: R$ 10,00)",
        )
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
    # ====== CONFIRMAÇÃO DO PEDIDO (retirada e pronta-entrega) ======
    if etapa == "confirmar_pedido":
        opc = (texto or "").strip().lower()

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
            encomenda_id = salvar_encomenda_sqlite(telefone, dados, nome_cliente)
            salvar_entrega(
                encomenda_id=encomenda_id,
                tipo="retirada",
                data_agendada=dados.get("data_entrega"),
                status="Retirar na loja"
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

