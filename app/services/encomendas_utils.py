import re
from datetime import datetime
from typing import Optional, Tuple, List, Dict

# === ALIASES DE PRODUTO (evita KeyError por variações de digitação) ===
TORTAS_ALIASES: Dict[str, str] = {
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

REDONDOS_ALIASES: Dict[str, str] = {
    "lingua de gato": "Língua de Gato",
    "língua de gato": "Língua de Gato",
    "branco camafeu": "Branco Camafeu",
    "belga": "Belga",
    "naked cake": "Naked Cake",
    "red velvet": "Red Velvet",
}

# GOURMET_ALIASES (mapeamento de variações para nomes oficiais)
GOURMET_ALIASES: Dict[str, str] = {
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

TAMANHO_MAP: Dict[str, str] = {
    "b3": "B3", "mini": "B3", "15": "B3", "3": "B3",
    "b4": "B4", "pequeno": "B4", "30": "B4", "4": "B4",
    "b6": "B6", "medio": "B6", "médio": "B6", "50": "B6", "6": "B6",
    "b7": "B7", "grande": "B7", "80": "B7", "7": "B7",
}


def _normaliza_produto(linha: str, nome: str) -> Optional[str]:
    """Normaliza o nome do produto de acordo com a linha escolhida.
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


def _valida_data(txt: str) -> bool:
    try:
        datetime.strptime(txt.strip(), "%d/%m/%Y")
        return True
    except Exception:
        return False


def parse_doces_input_flex(texto: str) -> Tuple[List[Dict[str, int]], int]:
    """Interpreta a lista de doces enviada pelo cliente (flexível).
    Retorna (itens, total_qtd).
    """
    itens: List[Dict[str, int]] = []
    total = 0

    linhas = re.split(r"[;\r\n]+", texto or "")
    for linha in linhas:
        t = (linha or "").strip()
        if not t:
            continue

        m = re.match(r"^(.*)\s+x(\d+)$", t, re.IGNORECASE)
        if m:
            nome, qtd = m.group(1).strip(), int(m.group(2))
        else:
            m2 = re.match(r"^(.*)\s+(\d+)$", t)
            if m2:
                nome, qtd = m2.group(1).strip(), int(m2.group(2))
            else:
                nome, qtd = t, 1

        itens.append({"nome": nome, "qtd": qtd})
        total += qtd

    return itens, total


def _parse_hora(txt: str) -> Optional[str]:
    """Tenta normalizar a hora para HH:MM.
    Aceita: '11h', '11h30', '11:30', '1130', '11'
    """
    if not txt:
        return None
    t = txt.strip().lower()

    m = re.match(r"^(\d{1,2})h?$", t)
    if m:
        h = int(m.group(1))
        if 0 <= h <= 23:
            return f"{h:02d}:00"

    m = re.match(r"^(\d{1,2})h(\d{2})$", t)
    if m:
        h, mnt = int(m.group(1)), int(m.group(2))
        if 0 <= h <= 23 and 0 <= mnt <= 59:
            return f"{h:02d}:{mnt:02d}"

    m = re.match(r"^(\d{1,2})(\d{2})$", t)
    if m:
        h, mnt = int(m.group(1)), int(m.group(2))
        if 0 <= h <= 23 and 0 <= mnt <= 59:
            return f"{h:02d}:{mnt:02d}"

    try:
        dt = datetime.strptime(t, "%H:%M")
        return dt.strftime("%H:%M")
    except Exception:
        return None


def _normaliza_tamanho(txt: str) -> str:
    t = (txt or "").strip().lower()
    return TAMANHO_MAP.get(t, t.upper())


__all__ = [
    "TORTAS_ALIASES",
    "REDONDOS_ALIASES",
    "GOURMET_ALIASES",
    "TAMANHO_MAP",
    "_normaliza_produto",
    "_valida_data",
    "parse_doces_input_flex",
    "_parse_hora",
    "_normaliza_tamanho",
]
