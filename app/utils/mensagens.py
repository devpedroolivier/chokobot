import re
import unicodedata

from app.application.service_registry import get_messaging_gateway

SAUDACOES = ["oi", "iae", "salve", "olá", "ola", "bom dia", "boa tarde", "boa noite"]

def is_saudacao(texto: str) -> bool:
    return any(sauda in (texto or "").lower() for sauda in SAUDACOES)

_HEADING_ICON_RULES = (
    ("kit festou", "🎉"),
    ("bolos pronta entrega", "🎂"),
    ("bolo pronta entrega", "🎂"),
    ("monte seu bolo", "🎂"),
    ("tradicional", "🎂"),
    ("cafeteria", "☕"),
    ("vitrine", "☕"),
    ("doces avulsos", "🍬"),
    ("linha gourmet", "✨"),
    ("ingles", "🍰"),
    ("redondo", "🍰"),
    ("mesversario", "🎈"),
    ("revelacao", "🎈"),
    ("baby cake", "🧁"),
    ("tortas", "🥧"),
    ("linha simples", "🍰"),
    ("cestas", "🎁"),
    ("presentes", "🎁"),
    ("entregas", "🚚"),
    ("pagamento", "💳"),
    ("pronta entrega", "🛍️"),
    ("encomendas", "📦"),
)


def _normalize_heading(texto: str) -> str:
    base = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(char for char in base if not unicodedata.combining(char))
    return sem_acento.casefold()


def _heading_icon(titulo: str) -> str:
    normalized = _normalize_heading(titulo)
    for pattern, icon in _HEADING_ICON_RULES:
        if pattern in normalized:
            return icon
    return "📌"


def formatar_mensagem_saida(mensagem: str) -> str:
    linhas_formatadas = []
    for linha in mensagem.splitlines():
        match = re.match(r"^\s*#{2,6}\s+(.*\S)\s*$", linha)
        if not match:
            linhas_formatadas.append(linha)
            continue

        titulo = re.sub(r"^\d+\.\s*", "", match.group(1)).strip()
        linhas_formatadas.append(f"{_heading_icon(titulo)} {titulo}")
    return "\n".join(linhas_formatadas)

async def responder_usuario(phone: str, mensagem: str) -> bool:
    """
    Envia mensagem de forma confiável com retry controlado e lock por telefone.
    Garante que apenas uma mensagem por número é enviada por vez, evitando duplicidade.
    """
    mensagem = formatar_mensagem_saida(mensagem)
    return await get_messaging_gateway().send_text(phone, mensagem)
