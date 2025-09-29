# app/services/precos.py
from typing import Tuple, List, Dict, Any
import re
import unicodedata

# =========================
#  PREÇOS - BOLOS
# =========================

KIT_FESTOU_PRECO = 35.0

TRADICIONAL_BASE = {
    "B3": {"preco": 120.0, "serve": 15},
    "B4": {"preco": 180.0, "serve": 30},
    "B6": {"preco": 300.0, "serve": 50},
    "B7": {"preco": 380.0, "serve": 80},
}

TRADICIONAL_ADICIONAIS = {
    "B3": {"Abacaxi": 130.0, "Ameixa": 130.0, "Cereja": 135.0, "Morango": 135.0, "Nozes": 125.0},
    "B4": {"Abacaxi": 195.0, "Ameixa": 195.0, "Cereja": 210.0, "Morango": 210.0, "Nozes": 190.0},
    "B6": {"Abacaxi": 325.0, "Ameixa": 325.0, "Cereja": 350.0, "Morango": 350.0, "Nozes": 315.0},
    "B7": {"Abacaxi": 415.0, "Ameixa": 430.0, "Cereja": 450.0, "Morango": 450.0, "Nozes": 400.0},
}

EMBRULHADO = {
    "24": {"preco": 150.0, "serve": 24},
    "48": {"preco": 260.0, "serve": 48},
}

INGLES = {
    "Belga": {"preco": 130.0, "serve": 10},
    "Floresta Negra": {"preco": 140.0, "serve": 10},
    "Língua de Gato": {"preco": 130.0, "serve": 10},
    "Ninho com Morango": {"preco": 140.0, "serve": 10},
    "Nozes com Doce de Leite": {"preco": 140.0, "serve": 10},
    "Olho de Sogra": {"preco": 120.0, "serve": 10},
    "Red Velvet": {"preco": 120.0, "serve": 10},
}

REDONDOS_P6 = {
    "Língua de Gato de Chocolate": {"preco": 165.0, "serve": 20},
    "Língua de Gato de Chocolate Branco": {"preco": 165.0, "serve": 20},
    "Língua de Gato Branco Camafeu": {"preco": 175.0, "serve": 20},
    "Belga": {"preco": 180.0, "serve": 20},
    "Naked Cake": {"preco": 175.0, "serve": 20},
    "Red Velvet": {"preco": 220.0, "serve": 20},
}

TORTAS = {
    "Argentina": {"preco": 130.0, "serve": 16},
    "Banoffee": {"preco": 130.0, "serve": 16},
    "Cheesecake Tradicional": {"preco": 160.0, "serve": 16},
    "Cheesecake Pistache": {"preco": 250.0, "serve": 16},
    "Citrus Pie": {"preco": 150.0, "serve": 16},
    "Limão": {"preco": 150.0, "serve": 16},
}

# inclui Cereja nos aliases também
ALIAS_ADICIONAIS = {
    "morango": "Morango",
    "cereja": "Cereja",
    "nozes": "Nozes",
    "ameixa": "Ameixa",
    "abacaxi": "Abacaxi"
}

def _alias_fruta(valor: str | None) -> str | None:
    if not valor:
        return None
    v = valor.strip().lower()
    return ALIAS_ADICIONAIS.get(v, valor.strip().title())

def preco_tradicional(tamanho: str, fruta_ou_nozes: str | None) -> Tuple[float, int]:
    t = tamanho.strip().upper()
    fruta_ou_nozes = _alias_fruta(fruta_ou_nozes)
    serve = TRADICIONAL_BASE[t]["serve"]
    if fruta_ou_nozes:
        preco = TRADICIONAL_ADICIONAIS[t].get(fruta_ou_nozes, TRADICIONAL_BASE[t]["preco"])
    else:
        preco = TRADICIONAL_BASE[t]["preco"]
    return preco, serve

def calcular_total(pedido: dict) -> Tuple[float, int]:
    """
    pedido:
    {
      'categoria': 'tradicional'|'embrulhado'|'ingles'|'redondo'|'torta',
      'tamanho': 'B3'|'B4'|'B6'|'B7',              # tradicional
      'fruta_ou_nozes': 'Morango'|...|None,        # tradicional
      'pedacos': '24'|'48',                        # embrulhado
      'produto': <str>,                            # inglês/redondo/torta
      'kit_festou': bool,
      'quantidade': int,
      'data_entrega': 'DD/MM/AAAA',
      'horario_retirada': 'HH:MM'
    }
    """
    categoria = pedido.get("categoria")
    total = 0.0
    serve = 0

    if categoria == "tradicional":
        preco, serve = preco_tradicional(pedido["tamanho"], pedido.get("fruta_ou_nozes"))
        total += preco
    elif categoria == "embrulhado":
        item = EMBRULHADO[pedido["pedacos"]]
        total += item["preco"]; serve = item["serve"]
    elif categoria == "ingles":
        item = INGLES[pedido["produto"]]
        total += item["preco"]; serve = item["serve"]
    elif categoria == "redondo":
        item = REDONDOS_P6[pedido["produto"]]
        total += item["preco"]; serve = item["serve"]
    elif categoria == "torta":
        item = TORTAS[pedido["produto"]]
        total += item["preco"]; serve = item["serve"]
    else:
        raise ValueError(f"Categoria inválida: {categoria}")

    if pedido.get("kit_festou"):
        total += KIT_FESTOU_PRECO

    q = int(pedido.get("quantidade", 1))
    total *= q
    if q > 1 and serve:
        serve *= q

    return round(total, 2), serve


# =========================
#  PREÇOS - DOCES
# =========================

# Tabela canônica: nome -> preço unitário (R$)
DOCES_UNITARIOS: Dict[str, float] = {
    # Tradicionais
    "Brigadeiro Escama": 1.50,
    "Brigadeiro De Ninho": 1.50,
    "Brigadeiro Power": 1.50,
    "Brigadeiro De Ninho Com Nutella": 2.10,
    "Brigadeiro De Creme Brulee": 2.00,
    "Brigadeiro Granule Melken Ao Leite": 2.00,
    "Brigadeiro Granule Melken Amargo": 2.00,
    "Brigadeiro Belga Callebaut Ao Leite": 3.20,
    "Brigadeiro Belga Callebaut Amargo": 3.20,
    "Beijinho": 1.40,
    "Brigadeiro De Amendoim": 1.40,
    "Brigadeiro De Pacoca": 1.50,
    "Casadinho": 1.60,
    "Brigadeiro De Churros": 2.00,
    "Brigadeiro De Limao": 1.50,
    "Brigadeiro Torta De Limao": 1.60,
    "Olho De Sogra": 2.00,
    "Brigadeiro Romeu E Julieta": 2.00,
    "Brigadeiro De Pistache": 4.00,

    # Finos
    "Damasco": 4.20,
    "Bombom Cookies Brigadeiro De Nutella": 3.30,
    "Bombom Abacaxi": 3.00,
    "Bombom Cereja": 3.00,
    "Bombom Maracuja": 3.00,
    "Bombom Prestigio": 3.00,
    "Mini Cestinha De Cereja": 4.00,

    "Bombom Uva Verde": 3.20,
    "Bombom Preto E Branco": 3.00,
    "Bombom Tradicional": 3.00,
    "Bombom Camafeu": 3.25,
    "Coracao Branco Brigadeiro De Nutella": 3.20,
    "Coracao Dourado Brigadeiro De Nutella": 3.30,
    "Coracao Sensacao": 3.20,
    "Mini Cestinha Branca De Limao": 3.00,
    "Mini Cestinha Maracuja": 3.00,
    "Mini Cestinha Mousse Com Praline De Nozes": 3.20,
    "Mini Cestinha De Pistache": 4.50,
    "Chokobom": 5.90,
    "Pirulito De Chocolate": 5.50,
}

# Aliases para variações de digitação e acentos
DOCES_ALIASES: Dict[str, str] = {
    # normalizações de nutella/nuttela
    "brigadeiro de ninho com nuttela": "Brigadeiro De Ninho Com Nutella",
    "brigadeiro de ninho com nutella": "Brigadeiro De Ninho Com Nutella",
    "ninho com nutella": "Brigadeiro De Ninho Com Nutella",
    "brigadeiro ninho nutella": "Brigadeiro De Ninho Com Nutella",
    "bombom cookies brigadeiro de nuttela": "Bombom Cookies Brigadeiro De Nutella",
    "coracao branco brigadeiro de nuttela": "Coracao Branco Brigadeiro De Nutella",
    "coracao dourado brigadeiro de nuttela": "Coracao Dourado Brigadeiro De Nutella",

    # brigadeiros comuns
    "brigadeiro de ninho": "Brigadeiro De Ninho",
    "brigadeiro ninho": "Brigadeiro De Ninho",
    "ninho": "Brigadeiro De Ninho",

    "brigadeiro escama": "Brigadeiro Escama",
    "escama": "Brigadeiro Escama",

    "brigadeiro power": "Brigadeiro Power",

    "brigadeiro creme brulee": "Brigadeiro De Creme Brulee",
    "creme brulee": "Brigadeiro De Creme Brulee",

    "brigadeiro granule melken ao leite": "Brigadeiro Granule Melken Ao Leite",
    "granule ao leite": "Brigadeiro Granule Melken Ao Leite",

    "brigadeiro granule melken amargo": "Brigadeiro Granule Melken Amargo",
    "granule amargo": "Brigadeiro Granule Melken Amargo",

    "brigadeiro belga ao leite": "Brigadeiro Belga Callebaut Ao Leite",
    "belga ao leite": "Brigadeiro Belga Callebaut Ao Leite",

    "brigadeiro belga amargo": "Brigadeiro Belga Callebaut Amargo",
    "belga amargo": "Brigadeiro Belga Callebaut Amargo",

    "brigadeiro de amendoim": "Brigadeiro De Amendoim",
    "amendoim": "Brigadeiro De Amendoim",

    "brigadeiro de pacoca": "Brigadeiro De Pacoca",
    "brigadeiro pacoca": "Brigadeiro De Pacoca",
    "paçoca": "Brigadeiro De Pacoca",
    "pacoca": "Brigadeiro De Pacoca",

    "brigadeiro de limao": "Brigadeiro De Limao",
    "brigadeiro torta de limao": "Brigadeiro Torta De Limao",
    "limao": "Brigadeiro De Limao",

    "romeu e julieta": "Brigadeiro Romeu E Julieta",

    "olho de sogra": "Olho De Sogra",

    # bombons
    "prestigio": "Bombom Prestigio",
    "maracuja": "Bombom Maracuja",
    "preto e branco": "Bombom Preto E Branco",
    "camafeu": "Bombom Camafeu",
    "uva verde": "Bombom Uva Verde",
    "tradicional": "Bombom Tradicional",
    "cereja": "Bombom Cereja",
    "abacaxi": "Bombom Abacaxi",

    # mini cestinhas
    "mini cestinha cereja": "Mini Cestinha De Cereja",
    "mini cestinha branca de limao": "Mini Cestinha Branca De Limao",
    "mini cestinha maracuja": "Mini Cestinha Maracuja",
    "mini cestinha mousse com praline de nozes": "Mini Cestinha Mousse Com Praline De Nozes",
    "mini cestinha pistache": "Mini Cestinha De Pistache",

    # outros
    "coracao sensacao": "Coracao Sensacao",
    "chokobom": "Chokobom",
    "pirulito de chocolate": "Pirulito De Chocolate",
}


def _to_float_brl(num_str: str) -> float:
    s = num_str.strip().replace(".", "").replace(",", ".")
    try:
        return round(float(s), 2)
    except:
        return 0.0

def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))

def _norm(s: str) -> str:
    return _strip_accents(s).lower().strip()

def _canonical_doce(nome: str) -> str | None:
    """
    Tenta mapear um nome qualquer para o nome canônico da tabela de preços.
    """
    if not nome:
        return None
    base = _norm(nome)
    # mapeia por alias
    if base in DOCES_ALIASES:
        return DOCES_ALIASES[base]
    # tenta bater com chaves canônicas normalizadas
    for can in DOCES_UNITARIOS.keys():
        if _norm(can) == base:
            return can
    return None

def parse_doces_input(texto: str):
    """
    Aceita vários itens separados por ';' ou quebra de linha.
    Formatos por item:
      - "Brigadeiro de Ninho x25"
      - "Bombom Prestígio x30 = 90,00"  (override de preço total do item)
    Retorna: (itens, total_doces)
      itens = [{"nome": str, "qtd": int, "preco": float|None, "unit": float|None}, ...]
      total_doces = soma dos 'preco' (auto ou override)
    """
    itens: List[Dict[str, Any]] = []
    total = 0.0

    partes = re.split(r"[;\n]+", texto)
    for p in partes:
        p = p.strip()
        if not p:
            continue

        # Grupos NOME, QTD e PRECO nomeados (evita confundir quantidade com preço)
        m = re.match(
            r"^\s*(?P<nome>.+?)\s*x\s*(?P<qtd>\d+)(?:\s*=\s*(?P<preco>[\d\.,]+))?\s*$",
            p,
            flags=re.IGNORECASE
        )

        if m:
            nome_raw = m.group("nome").strip()
            qtd = int(m.group("qtd"))
            preco_override = _to_float_brl(m.group("preco")) if m.group("preco") else None
        else:
            # fallback: só o nome -> 1 unidade, sem override
            nome_raw = p
            qtd = 1
            preco_override = None

        can = _canonical_doce(nome_raw)
        unit = DOCES_UNITARIOS.get(can) if can else None

        if preco_override is not None:
            preco_item = preco_override
        elif unit is not None:
            preco_item = round(unit * qtd, 2)
        else:
            preco_item = None  # mantém item no resumo mas sem somar

        if preco_item is not None:
            total += preco_item

        itens.append({
            "nome": can if can else nome_raw.title(),
            "qtd": qtd,
            "preco": preco_item,
            "unit": unit
        })

    return itens, round(total, 2)


# =========================
#  RESUMO (com doces)
# =========================

def _doces_bloco(pedido: dict) -> tuple[str, float]:
    itens = pedido.get("doces_itens") or []
    total_doces = float(pedido.get("doces_total") or 0.0)
    if not itens:
        return "", 0.0

    linhas = ["", "🍬 *Doces*:"]
    for d in itens:
        preco_txt = ""
        if d.get("preco") not in (None, ""):
            preco_txt = f" — R${float(d['preco']):.2f}"
        elif d.get("unit") not in (None, ""):
            preco_txt = f" — R${float(d['unit']):.2f}/un"
        linhas.append(f"- {d['nome']} x{d['qtd']}{preco_txt}")

    return "\n".join(linhas), total_doces

def montar_resumo(pedido: dict, total_bolo: float) -> str:
    data = pedido.get("data_entrega", "")
    hora = pedido.get("horario_retirada", "")
    cat  = pedido.get("categoria")

    linhas = []
    if cat == "tradicional":
        desc = f'{pedido.get("tamanho","")} {pedido.get("descricao","")}'.strip()
        if pedido.get("fruta_ou_nozes"):
            desc += f' + {pedido["fruta_ou_nozes"]}'
        linhas.append(f"- {desc}")
    elif cat == "embrulhado":
        ped = pedido.get("pedacos", "")
        linhas.append(f'- Bolo embrulhado ({ped} pedaços)')
    else:
        if pedido.get("produto"):
            linhas.append(f'- {pedido["produto"]}')

    if pedido.get("kit_festou"):
        linhas.append(f"+ Kit Festou — R${KIT_FESTOU_PRECO:.0f}")

    q = int(pedido.get("quantidade", 1))
    if q > 1 and linhas:
        linhas[-1] = linhas[-1] + f"  x{q}"

    itens_txt = "\n".join(linhas)

    doces_txt, total_doces = _doces_bloco(pedido)
    total_geral = total_bolo + total_doces

    if pedido.get("modo_recebimento") == "entrega":
        corpo = [
            "✅ *Resumo do pedido*",
            f"📅 Data da entrega: {data}",
            f"⏰ Horário da entrega: {hora}",
            f"📍 Endereço: {pedido.get('endereco','')}",
            "📦 Itens:",
            itens_txt,
        ]
    else:
        corpo = [
            "✅ *Resumo do pedido*",
            f"📅 Data: {data}",
            f"⏰ Retirada: {hora}",
            "📦 Itens:",
            itens_txt,
        ]

    if doces_txt:
        corpo.append(doces_txt)

        # >>> NOVO: adiciona forminhas, se existirem <<<
        if pedido.get("doces_forminha"):
            corpo.append(f"🎨 Forminhas: {', '.join(pedido['doces_forminha'])}")

        corpo += [
            "———",
            f"Total do Bolo: R${total_bolo:.2f}",
            f"Total dos Doces: R${total_doces:.2f}",
            "———",
            f"*Total Geral: R${total_geral:.2f}*",
        ]
    else:
        corpo += [
            "———",
            f"*Total: R${total_bolo:.2f}*",
        ]

    return "\n".join(corpo)
