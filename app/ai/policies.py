from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

from app.services.commercial_rules import (
    DELIVERY_CUTOFF,
    DELIVERY_CUTOFF_LABEL,
    SAME_DAY_CAKE_ORDER_CUTOFF,
    SAME_DAY_CAKE_ORDER_CUTOFF_LABEL,
)
from app.services.store_schedule import build_calendar_reference_context, build_operational_calendar_context
from app.utils.datetime_utils import get_bot_timezone, normalize_to_bot_timezone, now_in_bot_timezone


def current_timezone() -> ZoneInfo:
    return get_bot_timezone()


def current_local_datetime() -> datetime:
    return now_in_bot_timezone()


def normalize_reference_time(now: datetime | None = None) -> datetime:
    return normalize_to_bot_timezone(now)


def is_after_same_day_cake_order_cutoff(now: datetime | None = None) -> bool:
    current_time = normalize_reference_time(now)
    return (current_time.hour, current_time.minute) > SAME_DAY_CAKE_ORDER_CUTOFF


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
        r"\bquero (um )?humano\b",
    )
    return any(re.search(pattern, normalized) for pattern in patterns)


def normalize_intent_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text or "")
    return "".join(char for char in normalized if not unicodedata.combining(char)).casefold()


def requests_opt_out(text: str) -> bool:
    normalized = normalize_intent_text(text)
    if not normalized:
        return False
    patterns = (
        r"\b(desativar|desligar|parar|pausar)\s+(o\s+)?(chat|bot)s?\b",
        r"\bquero\s+(desativar|parar)\s+(o\s+)?(chat|bot)\b",
    )
    return any(re.search(pattern, normalized) for pattern in patterns)


def caseirinho_clarification_message(text: str) -> str | None:
    normalized = normalize_intent_text(text)
    if not normalized:
        return None

    mentions_caseirinho = any(
        token in normalized
        for token in ("caseirinho", "bolo caseiro", "bolo simples", "linha simples")
    )
    if not mentions_caseirinho:
        return None

    has_flavor = bool(re.search(r"\b(chocolate|cenoura)\b", normalized))
    has_coverage = bool(re.search(r"\b(vulcao|vulcaozinho|simples)\b", normalized))

    if has_flavor and has_coverage:
        return None
    if not has_flavor and not has_coverage:
        return (
            "Perfeito! No caseirinho, me confirme o sabor (Chocolate ou Cenoura) "
            "e a cobertura (Vulcao R$35 ou Simples R$25)."
        )
    if not has_flavor:
        return "Perfeito! Qual sabor do caseirinho voce prefere: Chocolate ou Cenoura?"
    return "Perfeito! Qual cobertura do caseirinho voce prefere: Vulcao (R$35) ou Simples (R$25)?"


@lru_cache(maxsize=1)
def _load_catalog_aliases() -> set[str]:
    aliases: set[str] = set()
    catalog_paths = (
        Path("app/ai/knowledge/catalogo_produtos.json"),
        Path("app/ai/knowledge/catalogo_presentes_regulares.json"),
    )
    for catalog_path in catalog_paths:
        if not catalog_path.exists():
            continue
        payload = json.loads(catalog_path.read_text(encoding="utf-8"))
        for item in payload.get("items", []):
            name = item.get("name")
            if name:
                aliases.add(normalize_intent_text(name))
            for alias in item.get("aliases", []):
                if alias:
                    aliases.add(normalize_intent_text(alias))
    return aliases


def _mentions_catalog_item(text: str) -> bool:
    normalized = normalize_intent_text(text)
    if not normalized:
        return False
    aliases = _load_catalog_aliases()
    return any(alias in normalized for alias in aliases)


@lru_cache(maxsize=1)
def _load_present_aliases() -> set[str]:
    aliases: set[str] = set()
    catalog_path = Path("app/ai/knowledge/catalogo_presentes_regulares.json")
    if not catalog_path.exists():
        return aliases
    payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    for item in payload.get("items", []):
        name = item.get("name")
        if name:
            aliases.add(normalize_intent_text(name))
        for alias in item.get("aliases", []):
            if alias:
                aliases.add(normalize_intent_text(alias))
    return aliases


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
    """Retorna True para qualquer mensagem sobre Páscoa — envia o link direto, sem IA."""
    normalized = normalize_intent_text(text)
    if _mentions_non_easter_egg_context(normalized):
        return False
    if _mentions_catalog_item(text) and not re.search(r"\b(ovo|ovos|pascoa)\b", normalized):
        return False
    if re.search(r"\bpronta\s*entrega\b", normalized):
        return False

    # Qualquer menção a Páscoa → link direto, sem envolver IA
    if re.search(r"\bpascoa\b", normalized):
        return True

    # Itens específicos de Páscoa citados sem a palavra "páscoa" → link direto
    if _mentions_specific_easter_item(normalized):
        return True

    # Padrões genéricos de ovo em contexto de Páscoa
    generic_egg_patterns = (
        r"\b(encomendar|encomenda|comprar|pedido|pedir|quero)\b.*\bovos?\b",
        r"\bovos?\s+de\s+pascoa\b",
        r"\btem\s+ovos?\b",
        r"\btem\s+ovo\b",
    )
    return any(re.search(pattern, normalized) for pattern in generic_egg_patterns)


def requests_easter_ready_delivery_handoff(text: str) -> bool:
    normalized = normalize_intent_text(text)
    if _mentions_non_easter_egg_context(normalized):
        return False

    egg_patterns = (
        r"\bovo\b",
        r"\bovos\b",
        r"\bpascoa\b",
        r"\bpascoa\b",
    )
    ready_patterns = (
        r"\bpronta\s*entrega\b",
        r"\bpronto\s*entrega\b",
        r"\btem\s+pronta\s*entrega\b",
        r"\bdisponivel\s+hoje\b",
        r"\bdisponiveis\s+hoje\b",
        r"\bpara\s+hoje\b",
        r"\bhoje\b",
    )
    has_egg = any(re.search(pattern, normalized) for pattern in egg_patterns)
    has_ready = any(re.search(pattern, normalized) for pattern in ready_patterns)
    return has_egg and has_ready


def requests_regular_gift_topic(text: str) -> bool:
    normalized = normalize_intent_text(text)
    if not normalized:
        return False
    if "pascoa" in normalized:
        return False
    present_aliases = _load_present_aliases()
    if any(alias in normalized for alias in present_aliases):
        return True
    patterns = (
        r"\bcesta(s)?\b",
        r"\bcesta(s)?\s+box\b",
        r"\bbox\b.*\b(cafe|chocolate)\b",
        r"\bcaixinha\b.*\bchocolate\b",
        r"\bcaixa\b.*\bchocolate\b",
        r"\bflores\b",
        r"\bbuque\b",
        r"\bbuque\b",
        r"\bpresente(s)?\b",
    )
    return any(re.search(pattern, normalized) for pattern in patterns)


def requests_post_purchase_topic(text: str) -> str | None:
    normalized = normalize_intent_text(text)
    if not normalized:
        return None

    tokens = set(re.findall(r"[a-z0-9]+", normalized))
    if not tokens:
        return None

    def _matches_any(*choices: str) -> bool:
        return any(choice in tokens for choice in choices)

    def _contains_fragment(fragment: str) -> bool:
        return any(fragment in token for token in tokens)

    if (_matches_any("status", "situacao") and _matches_any("pedido", "encomenda")):
        return "status"
    if "pix" in tokens and (
        _contains_fragment("confirm")
        or _matches_any("comprovante", "recebido")
    ):
        return "pix"
    if (
        (_contains_fragment("cancel") or _contains_fragment("desist") or _contains_fragment("devolv"))
        and _matches_any("pedido", "encomenda")
    ):
        return "cancel"
    if ("nota" in tokens and "fiscal" in tokens) or "nf" in tokens or _contains_fragment("fatura"):
        return "invoice"
    return None


def requests_easter_gift_topic(text: str) -> bool:
    normalized = normalize_intent_text(text)
    if not normalized or "pascoa" not in normalized:
        return False
    patterns = (
        r"\bmimos?\b",
        r"\bpresente(s)?\b",
        r"\bbox\b",
        r"\bpelucia\b",
        r"\bcookie na caixinha\b",
        r"\bcaneca\b",
        r"\btablete\b",
        r"\bmini ovos?\b",
    )
    return any(re.search(pattern, normalized) for pattern in patterns)


def requests_sweet_order_topic(text: str) -> bool:
    normalized = normalize_intent_text(text)
    if not normalized or "pascoa" in normalized:
        return False
    if requests_regular_gift_topic(text) or requests_easter_gift_topic(text):
        return False
    if not re.search(r"\b(brigadeir[oa]s?|bombons?|beijinhos?|doces?|camafeus?|trios?)\b", normalized):
        return False
    if re.search(r"\b(encomenda|pedido|quantidade|caixa|duzia|doces? avulsos|doces? em quantidade)\b", normalized):
        return True
    if re.search(r"\b\d+\b.*\b(brigadeir[oa]s?|bombons?|doces?)\b", normalized):
        return True
    return False


def requests_cake_order_topic(text: str) -> bool:
    normalized = normalize_intent_text(text)
    if not normalized:
        return False
    if requests_sweet_order_topic(text) or requests_regular_gift_topic(text) or requests_easter_gift_topic(text):
        return False
    if requests_easter_catalog(text) or requests_easter_ready_delivery_handoff(text):
        return False
    if re.search(r"\b(cafeteria|croissant|capuccino|cappuccino|cafe|cafe com leite|mocaccino)\b", normalized):
        return False
    return mentions_order_intent(text)


def _mentions_cafeteria_order_intent(normalized: str) -> bool:
    patterns = (
        r"\b(quero|queria|vou querer|pedir|pedido|me ve|separa|separe|adiciona|adicionar|inclui|incluir|manda|manda um|manda uma)\b",
    )
    return any(re.search(pattern, normalized) for pattern in patterns)


def _mentions_information_only_request(normalized: str) -> bool:
    patterns = (
        r"\b(qual|quais|quanto|preco|valor|tem|t[eê]m|opcoes|opcao|sabores|sabor|cardapio|catalogo|menu)\b",
    )
    return any(re.search(pattern, normalized) for pattern in patterns)


def _has_explicit_quantity(normalized: str) -> bool:
    return bool(
        re.search(
            r"\b(\d+|um|uma|dois|duas|tres|quatro|cinco|seis|sete|oito|nove|dez)\b",
            normalized,
        )
    )


def _mentions_any(normalized: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(pattern, normalized) for pattern in patterns)


def cafeteria_order_needs_specificity(user_text: str) -> bool:
    normalized = normalize_intent_text(user_text)
    if not normalized or not _mentions_cafeteria_order_intent(normalized):
        return False
    if _mentions_information_only_request(normalized):
        return False

    has_quantity = _has_explicit_quantity(normalized)

    if _mentions_any(normalized, (r"\b(cafeteria|pronta entrega|alguma coisa|algum item|item da cafeteria|lanche|bebida)\b",)):
        return True

    if _mentions_any(normalized, (r"\bcroissant\b", r"\bcroassant\b", r"\bcroasant\b")):
        has_option = _mentions_any(
            normalized,
            (
                r"\bfrango\b",
                r"\brequeijao\b",
                r"\bpresunto\b",
                r"\bmucarela\b",
                r"\bmuzzarela\b",
                r"\bperu\b",
                r"\bprovolone\b",
                r"\bquatro queijos\b",
                r"\bchocolate\b",
            ),
        )
        return not has_quantity or not has_option

    if _mentions_any(normalized, (r"\b(cappuccino|capuccino)\b",)):
        has_option = _mentions_any(normalized, (r"\bcanela\b", r"\bitaliano\b", r"\blotus\b", r"\bpistache\b"))
        return not has_quantity or not has_option

    if _mentions_any(normalized, (r"\bcafe\b", r"\bcafe com leite\b", r"\bmocaccino\b", r"\bachocolatado\b")):
        has_option = _mentions_any(normalized, (r"\bcurto\b", r"\blongo\b", r"\bcom leite\b", r"\bmocaccino\b", r"\bachocolatado\b"))
        return not has_quantity or not has_option

    if _mentions_any(normalized, (r"\b(coca|refrigerante)\b",)):
        has_option = _mentions_any(normalized, (r"\bzero\b", r"\bks\b", r"\blata\b"))
        return not has_quantity or not has_option

    if _mentions_any(normalized, (r"\bagua\b",)):
        has_option = _mentions_any(normalized, (r"\bsem gas\b", r"\bcom gas\b"))
        return not has_quantity or not has_option

    if _mentions_any(normalized, (r"\bsuco\b", r"\bsoda italiana\b", r"\bice\b")):
        has_option = _mentions_any(
            normalized,
            (
                r"\blaranja\b",
                r"\babacaxi\b",
                r"\bdel valle\b",
                r"\bpistache\b",
                r"\bcappuccino\b",
                r"\bchocolate\b",
                r"\bnegresco\b",
                r"\bovomaltine\b",
            ),
        )
        return not has_quantity or not has_option

    if _mentions_any(normalized, (r"\bfatia\b", r"\btorta\b", r"\bbolo gourmet\b", r"\bbolo gelado\b")):
        has_option = _mentions_any(
            normalized,
            (
                r"\bchocolate\b",
                r"\bninho\b",
                r"\bnozes\b",
                r"\bcheesecake\b",
                r"\blingua de gato\b",
                r"\blingua gato\b",
                r"\bice mousse\b",
                r"\bvulcaozinho\b",
                r"\bcenoura\b",
            ),
        )
        return not has_quantity or not has_option

    return False


def response_conflicts_with_cafeteria_specificity(
    reply: str | None,
    *,
    user_text: str,
    current_agent: str | None = None,
) -> bool:
    if current_agent != "CafeteriaAgent" or not cafeteria_order_needs_specificity(user_text):
        return False

    normalized = normalize_intent_text(reply or "")
    if not normalized:
        return False

    clarification_patterns = (
        r"\bqual sabor\b",
        r"\bquais sabores\b",
        r"\bqual opcao\b",
        r"\bquais opcoes\b",
        r"\bqual tipo\b",
        r"\bqual versao\b",
        r"\bqual item\b",
        r"\bqual bebida\b",
        r"\bquantos\b",
        r"\bquantas\b",
        r"\bks ou lata\b",
        r"\bzero ou normal\b",
        r"\bcom gas ou sem gas\b",
        r"\bespecific\b",
    )
    return not any(re.search(pattern, normalized) for pattern in clarification_patterns)


def build_cafeteria_specificity_retry_instruction(user_text: str) -> str:
    return (
        "CORRECAO DE SISTEMA: o cliente ainda nao especificou o suficiente para fechar um pedido da cafeteria. "
        "Antes de avancar, peca os detalhes faltantes. "
        "Colete no minimo item exato, sabor/tipo/versao quando existir e quantidade. "
        "Exemplos: croissant -> sabor e quantidade; coca/refrigerante -> lata ou KS, zero ou normal, e quantidade; "
        "cafe/cappuccino -> tipo/sabor e quantidade; fatia/torta -> sabor e quantidade. "
        f"Mensagem atual do cliente: '{user_text}'. "
        "Nao faca upsell, nao diga 'vou anotar', 'otima escolha' ou 'confirmar pedido' antes dessa especificacao."
    )


def response_conflicts_with_cutoff(reply: str | None, *, user_text: str, now: datetime | None = None) -> bool:
    if not reply or is_after_same_day_cake_order_cutoff(now) or not mentions_same_day(user_text, now):
        return False

    normalized = reply.casefold()
    if re.search(r"(j[aá]\s+)?passou\s+das?\s+11[:h]00", normalized):
        return True
    if re.search(r"encomendas?\s+para\s+hoje\s+se\s+encerraram", normalized):
        return True
    return False


def build_time_conflict_retry_instruction(now: datetime | None = None) -> str:
    current_time = normalize_reference_time(now)
    return (
        "CORRECAO DE SISTEMA: use exclusivamente o horario oficial de Brasilia. "
        f"Agora sao {current_time.strftime('%H:%M')} em Brasilia e ainda NAO passou das {SAME_DAY_CAKE_ORDER_CUTOFF_LABEL} para encomendas de bolo no mesmo dia. "
        "Reescreva a resposta sem afirmar que o horario limite das encomendas para hoje foi ultrapassado."
    )


def should_force_same_day_cafeteria_handoff(
    session: dict,
    user_text: str,
    now: datetime | None = None,
) -> bool:
    if not is_after_same_day_cake_order_cutoff(now) or not mentions_same_day(user_text, now):
        return False

    current_agent = session.get("current_agent")
    if current_agent == "CafeteriaAgent":
        return False
    return mentions_order_intent(user_text)


def should_force_gift_context_handoff(session: dict, user_text: str) -> str | None:
    current_agent = session.get("current_agent")
    if current_agent not in {
        "CakeOrderAgent",
        "SweetOrderAgent",
        "CafeteriaAgent",
        "GiftOrderAgent",
        "KnowledgeAgent",
        "TriageAgent",
    }:
        return None

    if requests_easter_gift_topic(user_text):
        return "KnowledgeAgent"

    if requests_regular_gift_topic(user_text):
        return "GiftOrderAgent"

    return None


def should_force_sweet_context_handoff(session: dict, user_text: str) -> str | None:
    current_agent = session.get("current_agent")
    if current_agent == "SweetOrderAgent":
        return None
    if requests_sweet_order_topic(user_text):
        return "SweetOrderAgent"
    return None


def should_force_basic_context_switch(session: dict, user_text: str) -> str | None:
    forced_gift_agent = should_force_gift_context_handoff(session, user_text)
    if forced_gift_agent:
        return forced_gift_agent

    forced_sweet_agent = should_force_sweet_context_handoff(session, user_text)
    if forced_sweet_agent:
        return forced_sweet_agent

    current_agent = session.get("current_agent")
    if current_agent not in {
        "CakeOrderAgent",
        "SweetOrderAgent",
        "CafeteriaAgent",
        "GiftOrderAgent",
        "KnowledgeAgent",
    }:
        return None
    if current_agent == "CakeOrderAgent":
        return None
    if requests_cake_order_topic(user_text):
        return "CakeOrderAgent"
    return None


def build_system_time_context(now: datetime | None = None) -> str:
    current_time = normalize_reference_time(now)
    same_day_cutoff_status = (
        "depois do limite" if is_after_same_day_cake_order_cutoff(current_time) else "antes do limite"
    )
    delivery_cutoff_status = "depois do limite" if is_after_delivery_cutoff(current_time) else "antes do limite"
    return (
        current_time.strftime("Hoje é %d/%m/%Y, e agora são %H:%M.")
        + " Horario oficial de Brasilia (America/Sao_Paulo)."
        + f" Status do corte das encomendas para hoje às {SAME_DAY_CAKE_ORDER_CUTOFF_LABEL}: {same_day_cutoff_status}."
        + f" Status do corte das entregas às {DELIVERY_CUTOFF_LABEL}: {delivery_cutoff_status}."
        + f" {build_calendar_reference_context(current_time)}"
        + f" {build_operational_calendar_context(current_time)}"
    )


def build_service_date_memory_instruction(service_date_context: dict | None) -> str | None:
    if not service_date_context:
        return None

    display = (service_date_context.get("display") or "").strip()
    source_text = (service_date_context.get("source_text") or "").strip()
    if not display:
        return None

    instruction = (
        "MEMORIA DE DATA DA CONVERSA: a referencia temporal mais recente e "
        f"{display}. Mantenha essa data em resumos, perguntas e tools ate o cliente corrigir explicitamente."
    )
    if source_text:
        instruction += f" Origem: '{source_text}'."
    return instruction


def build_conversation_correction_instruction(correction_context: dict | None) -> str | None:
    if not correction_context:
        return None

    parts: list[str] = []

    mode = (correction_context.get("modo_recebimento") or "").strip()
    if mode:
        parts.append(f"modo de recebimento mais recente = {mode}")

    payment_form = (correction_context.get("pagamento_forma") or "").strip()
    if payment_form:
        parts.append(f"pagamento mais recente = {payment_form}")

    troco_para = correction_context.get("troco_para")
    if payment_form == "Dinheiro" and troco_para not in (None, ""):
        parts.append(f"troco para = {troco_para}")
    parcelas = correction_context.get("parcelas")
    if payment_form == "Cartão (débito/crédito)" and parcelas not in (None, ""):
        parts.append(f"parcelamento mais recente = {parcelas}x")

    pickup_time = (correction_context.get("horario_retirada") or "").strip()
    if pickup_time:
        parts.append(f"horario mais recente = {pickup_time}")

    removed_additional = (correction_context.get("removed_adicional") or "").strip()
    if removed_additional:
        parts.append(f"adicional removido = {removed_additional}")

    if not parts:
        return None

    source_text = (correction_context.get("latest_source_text") or "").strip()
    instruction = (
        "MEMORIA DE CORRECOES DA CONVERSA: aplique estas correcoes mais recentes em resumos, perguntas e tools "
        "ate o cliente mudar explicitamente de novo. " + "; ".join(parts) + "."
    )
    if source_text:
        instruction += f" Origem: '{source_text}'."
    return instruction
