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


def is_generic_greeting(text: str) -> bool:
    normalized = normalize_intent_text(text)
    if not normalized:
        return False

    # Mantem o detector estrito para nao capturar mensagens com intencao de pedido.
    greeting_patterns = (
        r"^(oi|ola|ol[aá]|bom dia|boa tarde|boa noite|tudo bem|opa|e ai|eai)$",
        r"^(oi|ola|ol[aá])\s+(bom dia|boa tarde|boa noite)$",
    )
    return any(re.search(pattern, normalized) for pattern in greeting_patterns)


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


def mentions_easter(text: str) -> bool:
    normalized = normalize_intent_text(text)
    if not normalized:
        return False
    if _mentions_non_easter_egg_context(normalized):
        return False
    return bool(
        re.search(
            r"\b(pascoa|ovo|ovos|trio|trios|tablete|tabletes|mini ovos?|mimos?|coelho)\b",
            normalized,
        )
    )


def _mentions_specific_easter_item(normalized: str) -> bool:
    """Detecta consultas a itens específicos de Páscoa.

    Usado para classificar contexto de Páscoa com maior precisão.
    """
    if not normalized:
        return False

    easter_anchor = bool(
        re.search(r"\b(pascoa|ovo|ovos|trio|trios|tablete|tabletes|mini ovos?|blister|coelho)\b", normalized)
    )
    if not easter_anchor:
        return False

    direct_item_patterns = (
        r"\b(trio|trios|tablete|tabletes|mini ovos?|mini ovo|blister|caneca|pelucia)\b",
        r"\b\d+\s*(g|kg|kilo)\b",
        r"\b(supremo|intenso|cookie|pudim|trufad|crocant|colher|vertical|drage|kinder|brownie)\b",
        r"\b(alpino|rafaello|amarena|cheesecake|pacoca|pistache|lotus|negresco|ovomaltine)\b",
        r"\b(brigadeiro|cereja|maracuja|nutella|prestigio|sensacao)\b",
    )
    return any(re.search(pattern, normalized) for pattern in direct_item_patterns)


def requests_easter_catalog(text: str) -> bool:
    """Retorna True apenas quando cliente pede catalogo/link/menu de Páscoa."""
    normalized = normalize_intent_text(text)
    if _mentions_non_easter_egg_context(normalized):
        return False
    if _mentions_catalog_item(text) and not re.search(r"\b(ovo|ovos|pascoa)\b", normalized):
        return False
    if re.search(r"\bpronta\s*entrega\b", normalized):
        return False

    easter_context = bool(
        re.search(r"\b(pascoa|ovos?|trio|trios|tablete|mini ovos?|mimos?)\b", normalized)
    )
    if not easter_context:
        return False

    link_or_menu_request = bool(
        re.search(r"\b(cardapio|catalogo|menu|link|site|mostrar|mostra|ver|fotos?)\b", normalized)
    )
    if not link_or_menu_request:
        return False

    if _mentions_specific_easter_item(normalized):
        return False
    return True


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


def message_has_easter_context(text: str) -> bool:
    normalized = normalize_intent_text(text)
    if not normalized:
        return False
    if _mentions_non_easter_egg_context(normalized):
        return False

    if mentions_easter(text):
        return True
    if requests_easter_catalog(text):
        return True
    if requests_easter_ready_delivery_handoff(text):
        return True
    if requests_easter_order_topic(text):
        return True
    if requests_easter_gift_topic(text):
        return True
    if requests_easter_date_info(text):
        return True
    if re.search(r"\bpascoa\b", normalized):
        return True
    if _mentions_specific_easter_item(normalized):
        return True

    if re.search(r"\bovos?\b", normalized) and re.search(
        r"\b(chocolate|trufad\w*|crocant\w*|kinder|colher|tablete|trio|mimo|nutella|prestigio|ovomaltine|rafaello|amarena|pistache|lotus|negresco)\b",
        normalized,
    ):
        return True
    return False


def requests_regular_gift_topic(text: str) -> bool:
    normalized = normalize_intent_text(text)
    if not normalized:
        return False
    if "pascoa" in normalized and "cesta" not in normalized:
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
        r"\bmimo(s)?\b",
        r"\bpresente(s)?\b",
    )
    return any(re.search(pattern, normalized) for pattern in patterns)


def requests_easter_order_topic(text: str) -> bool:
    normalized = normalize_intent_text(text)
    if not normalized:
        return False
    if _mentions_non_easter_egg_context(normalized):
        return False
    if requests_easter_ready_delivery_handoff(text):
        return False
    if requests_easter_catalog(text):
        return False

    explicit_easter = re.search(r"\bpascoa\b", normalized)
    explicit_item = re.search(
        r"\b(ovo|ovos|trio|trios|tablete|tabletes|mini ovos?|mimos?|coelho|colher|trufad\w*|crocant\w*)\b",
        normalized,
    )
    if explicit_easter and explicit_item:
        return True
    if explicit_easter and re.search(r"\b(quero|queria|pedido|encomenda|comprar|pedir)\b", normalized):
        return True
    if explicit_item and re.search(r"\b(pascoa|trufad\w*|crocant\w*|tablete\w*|trio\w*)\b", normalized):
        return True
    if re.search(r"\b(ovo|ovos)\b", normalized) and re.search(
        r"\b(quero|queria|pedido|encomenda|comprar|pedir|gostaria)\b",
        normalized,
    ):
        return True
    return False


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
        or _matches_any("comprovante", "recebido", "fiz", "mandei", "enviei", "enviado")
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


def requests_pix_key_info(text: str) -> bool:
    normalized = normalize_intent_text(text)
    if not normalized:
        return False
    if "pix" not in normalized:
        return False

    key_patterns = (
        r"\b(chave|chave pix)\b",
        r"\b(passa|me passa|manda|me manda|envia|me envia)\b.*\bpix\b",
        r"\bqual\b.*\bpix\b",
        r"\bpix\b.*\b(cnpj|cpf)\b",
    )
    if any(re.search(pattern, normalized) for pattern in key_patterns):
        return True
    return bool(re.search(r"\bq?r?\s*code\b", normalized))


def requests_delivery_fee_info(text: str) -> bool:
    normalized = normalize_intent_text(text)
    if not normalized:
        return False
    patterns = (
        r"\b(taxa|frete)\b.*\b(entrega|delivery)\b",
        r"\b(entrega|delivery)\b.*\b(taxa|frete|valor|quanto)\b",
        r"\bqual\b.*\btaxa\b",
        r"\bquanto\b.*\bfrete\b",
    )
    return any(re.search(pattern, normalized) for pattern in patterns)


def requests_catalog_photo(text: str) -> bool:
    normalized = normalize_intent_text(text)
    if not normalized:
        return False
    patterns = (
        r"\btem\s+foto(s)?\b",
        r"\bmanda\s+(uma\s+)?foto\b",
        r"\bme\s+manda\s+(uma\s+)?foto\b",
        r"\bme\s+envia\s+(uma\s+)?foto\b",
        r"\bposso\s+ver\s+como\s+fica\b",
        r"\btem\s+imagem\b",
        r"\bver\s+foto(s)?\b",
        r"\bcatalogo\s+visual\b",
        r"\b(manda|me manda|me envia|me passa|passa|envia)\b.*\b(cardapio|catalogo|menu|link)\b",
        r"\bquero\s+ver\b.*\b(cardapio|catalogo|menu)\b",
        r"\blink\b.*\b(cardapio|catalogo|menu|pascoa)\b",
        r"\b(cardapio|catalogo|menu)\b.*\b(foto|fotos|imagem|imagens|link)\b",
        r"\b(quero|quer)\s+(o\s+)?(cardapio|catalogo|menu)\b",
        r"\b(qual|tem)\s+(o\s+)?(cardapio|catalogo|menu)\b",
        r"\bme\s+mostra\s+(o\s+)?(cardapio|catalogo|menu)\b",
        r"^(cardapio|catalogo|menu)\b",
        r"\b(cardapio|catalogo|menu)\s+d[eao]s?\s+\w+",
    )
    return any(re.search(pattern, normalized) for pattern in patterns)


def requests_knowledge_topic(text: str) -> bool:
    normalized = normalize_intent_text(text)
    if not normalized:
        return False
    if requests_easter_catalog(text) or requests_easter_order_topic(text) or requests_easter_gift_topic(text):
        return False
    if mentions_order_intent(text):
        return False
    if requests_cafeteria_topic(text) or requests_sweet_order_topic(text) or requests_regular_gift_topic(text):
        return False
    if _mentions_cafeteria_order_intent(normalized):
        return False
    patterns = (
        r"\b(preco|valor|quanto custa|quanto fica|cardapio|catalogo|menu|opcoes|sabores)\b",
        r"\b(funcionamento|horario|abre|fecha|entrega|delivery|retirada|endereco)\b",
        r"\b(pagamento|pix|cartao|dinheiro|parcelamento|troco)\b",
    )
    return any(re.search(pattern, normalized) for pattern in patterns)


def requests_easter_date_info(text: str) -> bool:
    normalized = normalize_intent_text(text)
    if not normalized:
        return False
    asks_when = re.search(r"\b(quando|que dia|qual dia|data)\b", normalized)
    asks_easter = re.search(r"\bpascoa\b", normalized)
    return bool(asks_when and asks_easter)


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
    has_sweet_anchor = bool(
        re.search(
        r"\b(brigadeir[oa]s?|bombo(m|ns?)|beijinhos?|doces?|docinhos?|camafeus?|trufas?|chokobons?)\b",
        normalized,
        )
    )
    if not has_sweet_anchor:
        return False
    if re.search(r"\btrufas?\b", normalized):
        return True
    if re.search(r"\b(encomenda|pedido|quantidade|caixa|duzia|doces? avulsos|doces? em quantidade)\b", normalized):
        return True
    if re.search(r"\b\d+\b.*\b(brigadeir[oa]s?|bombo(m|ns?)|doces?|trufas?)\b", normalized):
        return True
    if re.search(r"\b(quero|queria|tem|quanto|preco|valor|cardapio|menu)\b", normalized):
        return True
    return False


def requests_cafeteria_topic(text: str) -> bool:
    """Detecta menção a itens exclusivos de cafeteria/pronta entrega.

    Usado para forçar troca de contexto para CafeteriaAgent quando o cliente menciona
    um item que claramente pertence à cafeteria, independente do agente ativo.
    Só inclui termos que NUNCA aparecem em encomenda (evita falsos positivos).
    """
    normalized = normalize_intent_text(text)
    if not normalized:
        return False
    patterns = (
        r"\b(croissant|croassant|croasant)\b",
        r"\b(cappuccino|capuccino)\b",
        r"\b(mocaccino|achocolatado)\b",
        r"\b(pao de queijo|bauru|lanche fit|croque madame|toast de parma)\b",
        r"\b(suco de laranja|soda italiana)\b",
        r"\b(ice pistache|ice cappuccino|ice negresco|ice ovomaltine|ice chocolate)\b",
        r"\b(chokobenta|vulcaozinho)\b",
        r"\b(cafe curto|cafe longo|cafe com leite)\b",
    )
    return any(re.search(pattern, normalized) for pattern in patterns)


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

    if re.search(r"\bcombo(s)?\b", normalized):
        has_croissant_option = _mentions_any(
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
        has_beverage = _mentions_any(
            normalized,
            (
                r"\bcoca\b",
                r"\brefrigerante\b",
                r"\bks\b",
                r"\blata\b",
                r"\bsuco\b",
                r"\bcafe\b",
                r"\bcappuccino\b",
                r"\bcapuccino\b",
                r"\bachocolatado\b",
                r"\bmocaccino\b",
            ),
        )
        return not (has_quantity and has_croissant_option and has_beverage)

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


def response_conflicts_with_cafeteria_total_claim(
    reply: str | None,
    *,
    current_agent: str | None = None,
) -> bool:
    if current_agent != "CafeteriaAgent":
        return False

    normalized = normalize_intent_text(reply or "")
    if not normalized:
        return False

    # Resumos estruturados vindos da tool de rascunho/persistencia sao permitidos.
    if "resumo final do pedido" in normalized:
        return False
    if "pedido cafeteria salvo com sucesso" in normalized:
        return False

    if not re.search(r"\b(total|subtotal)\b", normalized):
        return False
    if not re.search(r"r\$\s*\d", normalized):
        return False
    return True


def build_cafeteria_total_guard_retry_instruction(user_text: str) -> str:
    return (
        "CORRECAO DE SISTEMA: voce esta em CafeteriaAgent e nao pode calcular subtotal/total de memoria. "
        "Recalcule os valores usando apenas ferramentas estruturadas e catalogo canonico. "
        "Se ja houver dados suficientes (itens, quantidade, recebimento e pagamento), use create_cafeteria_order "
        "para gerar o resumo de rascunho com subtotal/taxa/valor. "
        "Se faltar detalhe, pergunte apenas os campos faltantes sem inventar preco. "
        f"Mensagem atual do cliente: '{user_text}'."
    )


def response_conflicts_with_cafeteria_combo_truth(
    reply: str | None,
    *,
    user_text: str,
    current_agent: str | None = None,
) -> bool:
    if current_agent != "CafeteriaAgent":
        return False

    normalized_user = normalize_intent_text(user_text)
    if not re.search(r"\b(combo|choko combo|relampago|croissant|croassant|croasant)\b", normalized_user):
        return False

    normalized_reply = normalize_intent_text(reply or "")
    if not normalized_reply:
        return False

    # Perguntas de esclarecimento sao validas antes de consultar o catalogo.
    clarification_patterns = (
        r"\bqual sabor\b",
        r"\bquais sabores\b",
        r"\bqual bebida\b",
        r"\bquais bebidas\b",
        r"\bquantos\b",
        r"\bquantas\b",
        r"\bqual opcao\b",
        r"\bquais opcoes\b",
    )
    if any(re.search(pattern, normalized_reply) for pattern in clarification_patterns):
        return False

    # Tambem permitimos resposta segura de escalacao/confirmacao humana.
    safe_fallback_patterns = (
        r"\b(confirmar com a equipe|vou confirmar com a equipe)\b",
        r"\b(atendimento humano|encaminhar para humano|transferir para humano)\b",
    )
    if any(re.search(pattern, normalized_reply) for pattern in safe_fallback_patterns):
        return False

    has_combo_or_croissant_claim = bool(re.search(r"\b(combo|croissant|croassant|croasant)\b", normalized_reply))
    has_assertive_content = bool(
        re.search(
            r"\b(inclui|vem com|acompanha|nao inclui|nao vem|disponivel|indisponivel|nao temos|temos)\b",
            normalized_reply,
        )
    )
    has_price = bool(re.search(r"r\$\s*\d", normalized_reply))

    return has_combo_or_croissant_claim and (has_assertive_content or has_price)


def build_cafeteria_combo_truth_retry_instruction(user_text: str) -> str:
    return (
        "CORRECAO DE SISTEMA: para combo/croissant, nao descreva composicao, disponibilidade ou preco de memoria. "
        "Consulte primeiro o catalogo oficial com lookup_catalog_items (catalog='cafeteria') e use apenas o retorno estruturado. "
        "Se faltar detalhe de pedido, pergunte somente os campos faltantes. "
        "Se algo nao existir no catalogo, diga que vai confirmar com a equipe e ofereca atendimento humano. "
        f"Mensagem atual do cliente: '{user_text}'."
    )


def _is_discount_denial_response(normalized_reply: str) -> bool:
    if not normalized_reply:
        return False
    if not re.search(r"\b(desconto|descontinho|cupom)\b", normalized_reply):
        return False
    denial_patterns = (
        r"\b(nao|sem)\b.{0,20}\b(desconto|descontinho|cupom)\b",
        r"\b(desconto|descontinho|cupom)\b.{0,25}\b(nao|indisponivel|somente atendente|apenas atendente)\b",
        r"\bnao\b.{0,20}\b(consigo|posso|aplico|libero|concedo)\b.{0,20}\b(desconto|cupom)\b",
    )
    return any(re.search(pattern, normalized_reply) for pattern in denial_patterns)


def response_conflicts_with_discount_offer(reply: str | None) -> bool:
    normalized = normalize_intent_text(reply or "")
    if not normalized:
        return False
    if _is_discount_denial_response(normalized):
        return False

    offer_patterns = (
        r"\b(oferec\w*|aplic\w*|conced\w*|dar|liber\w*|pass\w*)\b.{0,30}\b(desconto|descontinho|cupom)\b",
        r"\b(desconto|descontinho)\b.{0,20}\b(especial|de\s+\d+%|de\s+\d+\s*por\s*cento|aplicad\w*)\b",
        r"\btotal\b.{0,20}\bcom desconto\b",
        r"\bcupom\b.{0,20}\b(aplicad\w*|ativo|valido)\b",
    )
    return any(re.search(pattern, normalized) for pattern in offer_patterns)


def build_discount_guard_retry_instruction(user_text: str) -> str:
    return (
        "CORRECAO DE SISTEMA: o bot NAO pode oferecer, aplicar, prometer ou calcular desconto em nenhum produto. "
        "Desconto e negociacao comercial sao exclusivos do atendente humano. "
        "Reescreva a resposta sem desconto. Se o cliente pedir desconto, responda que apenas a equipe humana pode avaliar "
        "e ofereca transferencia para atendimento humano. "
        f"Mensagem atual do cliente: '{user_text}'."
    )


def _mentions_truffle_interest(user_text: str) -> bool:
    normalized = normalize_intent_text(user_text)
    if not normalized:
        return False
    return bool(re.search(r"\btrufas?\b", normalized))


def response_conflicts_with_truffle_availability_denial(reply: str | None, *, user_text: str) -> bool:
    if not _mentions_truffle_interest(user_text):
        return False
    normalized = normalize_intent_text(reply or "")
    if not normalized:
        return False
    denial_patterns = (
        r"\bnao\b.{0,20}\b(temos|trabalhamos|vendemos|fazemos)\b.{0,30}\btrufas?\b",
        r"\btrufas?\b.{0,30}\bnao\b.{0,20}\b(temos|trabalhamos|vendemos|fazemos)\b",
    )
    return any(re.search(pattern, normalized) for pattern in denial_patterns)


def build_truffle_availability_retry_instruction(user_text: str) -> str:
    return (
        "CORRECAO DE SISTEMA: nao negue trufas sem verificar catalogo canonico. "
        "Trufas fazem parte do cardapio de doces e a resposta deve vir de ferramenta. "
        "Use get_menu(category='encomendas') ou lookup_catalog_items para confirmar nomes e valores. "
        "Se algum detalhe nao estiver estruturado, diga que vai confirmar com a equipe e ofereca atendimento humano, sem inventar. "
        f"Mensagem atual do cliente: '{user_text}'."
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
        "TriageAgent",
    }:
        return None

    # Força troca para CafeteriaAgent quando o cliente menciona item exclusivo de cafeteria,
    # independentemente do agente ativo (incluindo CakeOrderAgent).
    # Deve rodar ANTES do early-return de CakeOrderAgent para garantir o roteamento correto.
    if current_agent != "CafeteriaAgent" and requests_cafeteria_topic(user_text):
        return "CafeteriaAgent"

    if current_agent == "CakeOrderAgent":
        return None
    if current_agent != "KnowledgeAgent" and requests_knowledge_topic(user_text):
        return "KnowledgeAgent"
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
