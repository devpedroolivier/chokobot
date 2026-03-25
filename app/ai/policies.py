from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from zoneinfo import ZoneInfo

from app.utils.datetime_utils import get_bot_timezone, normalize_to_bot_timezone, now_in_bot_timezone


DELIVERY_CUTOFF = (17, 30)


def current_timezone() -> ZoneInfo:
    return get_bot_timezone()


def current_local_datetime() -> datetime:
    return now_in_bot_timezone()


def normalize_reference_time(now: datetime | None = None) -> datetime:
    return normalize_to_bot_timezone(now)


def is_after_delivery_cutoff(now: datetime | None = None) -> bool:
    current_time = normalize_reference_time(now)
    return (current_time.hour, current_time.minute) > DELIVERY_CUTOFF


def same_day_reference_tokens(now: datetime | None = None) -> tuple[str, ...]:
    current_time = normalize_reference_time(now)
    return (
        current_time.strftime("%d/%m/%Y"),
        current_time.strftime("%d/%m"),
        current_time.strftime("%d-%m-%Y"),
        current_time.strftime("%d-%m"),
    )


def mentions_same_day(text: str, now: datetime | None = None) -> bool:
    normalized = (text or "").casefold()
    if re.search(r"\b(hoje|hj)\b", normalized):
        return True
    return any(token in normalized for token in same_day_reference_tokens(now))


def mentions_order_intent(text: str) -> bool:
    normalized = (text or "").casefold()
    return bool(
        re.search(
            r"\b(bolo|encomenda\w*|torta|mesvers[aá]rio|baby\s*cake|babycake|gourmet|b3|b4|b6|b7|p4|p6)\b",
            normalized,
        )
    )


def requests_human_handoff(text: str) -> bool:
    normalized = (text or "").casefold()
    patterns = (
        r"\bfalar com (um )?(humano|atendente|pessoa)\b",
        r"\bquero falar com (um )?(humano|atendente|pessoa)\b",
        r"\b(atendente|humano) real\b",
        r"\bme passa para (um )?(humano|atendente)\b",
        r"\btransfer(e|ir) .* (humano|atendente)\b",
        r"\bdesativar (o )?(chat|bot)\b",
        r"\bquero (um )?humano\b",
    )
    return any(re.search(pattern, normalized) for pattern in patterns)


def normalize_intent_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text or "")
    return "".join(char for char in normalized if not unicodedata.combining(char)).casefold()


def _mentions_non_easter_egg_context(normalized: str) -> bool:
    patterns = (
        r"\b(pao|lanche|misto|croissant|sanduiche|sanduíche|omelete|tapioca)\b.*\bovo\b",
        r"\bovo\b.*\b(oregano|orégano|misto|lanche|croissant|sanduiche|sanduíche|omelete|tapioca)\b",
        r"\bsem\b.*\bovo\b",
    )
    return any(re.search(pattern, normalized) for pattern in patterns)


def _mentions_specific_easter_item(normalized: str) -> bool:
    patterns = (
        r"\b\d+\s*(g|kg|kilo)\b",
        r"\b(supremo|intenso|lotus|cookie|pudim|trufad|crocant|colher|vertical|drage|kinder|brownie)\b",
        r"\b(trio|tablete|mini ovos|mini ovo|blister|caneca|box|pelucia)\b",
        r"\b(brigadeiro|cereja|maracuja|negresco|nutella|alpino|ovomaltine|rafaello|amarena|cheesecake|pistache)\b",
        r"\b(prestigio|sensacao|sensação|pacoca|paçoca)\b",
    )
    return any(re.search(pattern, normalized) for pattern in patterns)


def requests_easter_catalog(text: str) -> bool:
    normalized = normalize_intent_text(text)
    if _mentions_non_easter_egg_context(normalized):
        return False
    if re.search(r"\bpronta\s*entrega\b", normalized):
        return False
    if _mentions_specific_easter_item(normalized):
        return False

    explicit_catalog_patterns = (
        r"\b(cardapio|catalogo|menu|link)\b.*\bpascoa\b",
        r"\bpascoa\b.*\b(cardapio|catalogo|menu|link)\b",
        r"\b(link|cardapio|catalogo|menu)\b.*\bovos?\b",
        r"\bquero\s+ver\b.*\bpascoa\b",
        r"\bme\s+manda\b.*\bpascoa\b",
        r"\bpre[\s-]?pascoa\b",
    )
    if any(re.search(pattern, normalized) for pattern in explicit_catalog_patterns):
        return True

    generic_egg_patterns = (
        r"\b(encomendar|encomenda|comprar|pedido|pedir|quero)\b.*\bovos?\b",
        r"\bovos?\s+de\s+pascoa\b",
        r"\btem\s+ovos?\b",
        r"\btem\s+ovo\b",
    )
    return any(re.search(pattern, normalized) for pattern in generic_egg_patterns)


def response_conflicts_with_cutoff(reply: str | None, *, user_text: str, now: datetime | None = None) -> bool:
    if not reply or is_after_delivery_cutoff(now) or not mentions_same_day(user_text, now):
        return False

    normalized = reply.casefold()
    if re.search(r"(j[aá]\s+)?passou\s+das?\s+17[:h]30", normalized):
        return True
    if re.search(r"encomendas?\s+para\s+hoje\s+se\s+encerraram", normalized):
        return True
    return False


def build_time_conflict_retry_instruction(now: datetime | None = None) -> str:
    current_time = normalize_reference_time(now)
    return (
        "CORRECAO DE SISTEMA: use exclusivamente o horario oficial de Brasilia. "
        f"Agora sao {current_time.strftime('%H:%M')} em Brasilia e ainda NAO passou das 17:30. "
        "Reescreva a resposta sem afirmar que o horario limite de hoje foi ultrapassado."
    )


def should_force_same_day_cafeteria_handoff(
    session: dict,
    user_text: str,
    now: datetime | None = None,
) -> bool:
    if not is_after_delivery_cutoff(now) or not mentions_same_day(user_text, now):
        return False

    current_agent = session.get("current_agent")
    if current_agent == "CakeOrderAgent":
        return True
    if current_agent == "TriageAgent" and mentions_order_intent(user_text):
        return True
    return False


def build_system_time_context(now: datetime | None = None) -> str:
    current_time = normalize_reference_time(now)
    cutoff_status = "depois do limite" if is_after_delivery_cutoff(current_time) else "antes do limite"
    return (
        current_time.strftime("Hoje é %d/%m/%Y, e agora são %H:%M.")
        + " Horario oficial de Brasilia (America/Sao_Paulo)."
        + f" Status do corte das 17:30: {cutoff_status}."
    )
