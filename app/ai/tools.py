import json
import re
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, Field

from app.application.service_registry import (
    get_attention_gateway,
    get_catalog_gateway,
    get_customer_process_repository,
    get_delivery_gateway,
    get_order_gateway,
)
from app.application.use_cases.process_cesta_box_flow import CESTAS_BOX_CATALOGO
from app.db.database import get_connection
from app.infrastructure.gateways.local_catalog_gateway import _normalize_text
from app.security import ai_learning_enabled, security_audit
from app.services.commercial_rules import (
    CARD_INSTALLMENT_MAX,
    CARD_INSTALLMENT_MIN_TOTAL,
    DELIVERY_FEE_CAFETERIA,
    DELIVERY_FEE_STANDARD,
)
from app.services.encomendas_utils import (
    GOURMET_ALIASES,
    LIMITE_HORARIO_ENTREGA,
    REDONDOS_ALIASES,
    TORTAS_ALIASES,
    _horario_entrega_permitido,
    _linha_canonica,
    _normaliza_tamanho,
    _normaliza_produto,
)
from app.services.store_schedule import format_service_date, validate_service_schedule
from app.services.store_schedule import format_service_date_with_weekday, parse_service_date
from app.utils.datetime_utils import now_in_bot_timezone
from app.settings import get_settings
from app.services.precos import (
    DOCES_UNITARIOS,
    DOCES_ALIASES,
    INGLES,
    KIT_FESTOU_PRECO,
    LINHA_SIMPLES,
    MESVERSARIO,
    REDONDOS_P6,
    TORTAS,
    TRADICIONAL_BASE,
    calcular_total,
    _canonical_doce,
    _norm,
)

# ============================================================
#  Constantes de validação
# ============================================================

MASSAS_TRADICIONAIS = ("Branca", "Chocolate", "Mesclada")
MASSAS_VALIDAS = set(MASSAS_TRADICIONAIS)
MASSA_SINONIMOS = {
    "preta": "Chocolate",
    "massa preta": "Chocolate",
    "escura": "Chocolate",
    "massa escura": "Chocolate",
}

RECHEIOS_TRADICIONAIS = (
    "Beijinho",
    "Brigadeiro",
    "Brigadeiro de Nutella",
    "Brigadeiro Branco Gourmet",
    "Brigadeiro Branco de Ninho",
    "Casadinho",
    "Doce de Leite",
)
RECHEIOS_VALIDOS = set(RECHEIOS_TRADICIONAIS)

MOUSSES_TRADICIONAIS = ("Ninho", "Trufa Branca", "Chocolate", "Trufa Preta")
MOUSSES_VALIDOS = set(MOUSSES_TRADICIONAIS)

ADICIONAIS_TRADICIONAIS = ("Morango", "Ameixa", "Nozes", "Cereja", "Abacaxi")
TAMANHOS_TRADICIONAIS = ("B3", "B4", "B6", "B7")

MASSAS_MESVERSARIO = ("Branca", "Chocolate")
RECHEIOS_MESVERSARIO = (
    "Brigadeiro com Ninho",
    "Brigadeiro de Nutella com Ninho",
    "Brigadeiro e Beijinho",
    "Casadinho",
    "Brigadeiro Branco Gourmet com Ninho",
    "Brigadeiro Branco de Ninho com Ninho",
    "Beijinho com Ninho",
    "Doce de Leite e Brigadeiro",
    "Doce de Leite com Ninho",
)
TAMANHOS_MESVERSARIO = ("P4", "P6")

CAKE_OPTION_LABELS = {
    "massa": "massas",
    "tamanho": "tamanhos",
    "recheio": "recheios",
    "mousse": "mousses",
    "adicional": "adicionais",
}

CAKE_OPTION_VALUES = {
    ("tradicional", "massa"): MASSAS_TRADICIONAIS,
    ("tradicional", "tamanho"): TAMANHOS_TRADICIONAIS,
    ("tradicional", "recheio"): RECHEIOS_TRADICIONAIS,
    ("tradicional", "mousse"): MOUSSES_TRADICIONAIS,
    ("tradicional", "adicional"): ADICIONAIS_TRADICIONAIS,
    ("mesversario", "massa"): MASSAS_MESVERSARIO,
    ("mesversario", "tamanho"): TAMANHOS_MESVERSARIO,
    ("mesversario", "recheio"): RECHEIOS_MESVERSARIO,
    ("mesversario", "mousse"): ("Chocolate",),
}

TAMANHOS_BOLO = {"B3", "B4", "B6", "B7", "P4", "P6"}

LINHAS_VALIDAS = {"tradicional", "gourmet", "mesversario", "babycake", "torta", "simples"}

CATEGORIAS_VALIDAS = {"tradicional", "ingles", "redondo", "torta", "mesversario", "simples", "babycake"}

LINE_SIMPLE_FLAVORS = ("Chocolate", "Cenoura")
LINE_SIMPLE_COVERAGES = ("Vulcão", "Simples")

TAXA_ENTREGA_PADRAO = DELIVERY_FEE_STANDARD
TAXA_ENTREGA_CAFETERIA = DELIVERY_FEE_CAFETERIA
CAFETERIA_CATALOG_PATH = Path("app/ai/knowledge/catalogo_produtos.json")
CHOCO_COMBO_CANONICAL_NAME = "Choko Combo (Combo do Dia)"
CAFETERIA_VARIANT_REQUIRED_HINTS = {
    "Croissant": "Informe o sabor do croissant e a quantidade.",
    "Combo Relampago": "No Choko Combo (Combo do Dia), escolha a bebida: Suco natural ou Refri 220ml.",
    "Agua": "Informe se deseja agua com gas ou sem gas, e a quantidade.",
}
GIFT_CATEGORY_ALIASES = {
    "cesta box": "cesta_box",
    "cestas box": "cesta_box",
    "cesta": "cesta_box",
    "cestas": "cesta_box",
    "caixinha de chocolate": "caixinha_chocolate",
    "caixa de chocolate": "caixinha_chocolate",
    "flores": "flores",
}
CAFETERIA_NAME_ALIASES = {
    "croissant": "Croissant",
    "croassant": "Croissant",
    "croasant": "Croissant",
    "vulcaozinho": "Vulcaozinho de Cenoura com Calda de Chocolate",
    "petit": "Vulcaozinho de Cenoura com Calda de Chocolate",
    "bolo petit": "Vulcaozinho de Cenoura com Calda de Chocolate",
    "coca cola ks": "Coca Cola KS",
    "coca ks": "Coca Cola KS",
    "coca": "Coca Cola KS",
    "coca cola": "Coca Cola KS",
    "refrigerante lata": "Refrigerante Lata",
    "refrigerante": "Refrigerante Lata",
    "agua": "Agua",
    "cafe curto": "Cafe Curto",
    "cafe longo": "Cafe Longo",
    "cafe com leite": "Cafe com Leite",
    "mocaccino": "Mocaccino",
    "achocolatado": "Achocolatado",
    "chokobenta": "ChokoBenta",
    "combo relampago": "Combo Relampago",
    "relampago": "Combo Relampago",
    "combo de terca": "Combo Relampago",
    "combo da terca": "Combo Relampago",
    "combo suco": "Combo Relampago",
    "combo refri": "Combo Relampago",
    "combo refrigerante": "Combo Relampago",
    "choko combo": "Combo Relampago",
    "combo do dia": "Combo Relampago",
    "promocao de terca": "Combo Relampago",
    "promocao da terca": "Combo Relampago",
}
CAFETERIA_ITEM_KEYWORDS = {
    "Croissant": ("croissant", "croassant", "croasant"),
    "Combo Relampago": ("combo", "relampago", "terca"),
    "Agua": ("agua",),
    "Coca Cola KS": ("coca", "cola", "ks"),
    "Refrigerante Lata": ("refrigerante", "lata"),
    "Cafe Curto": ("cafe", "curto"),
    "Cafe Longo": ("cafe", "longo"),
    "Cafe com Leite": ("cafe", "leite"),
    "Mocaccino": ("mocaccino",),
    "Cappuccino com Canela": ("cappuccino", "canela"),
    "Cappuccino Italiano": ("cappuccino", "italiano"),
    "Cappuccino Lotus": ("cappuccino", "lotus"),
    "Cappuccino Pistache": ("cappuccino", "pistache"),
}
COMBO_RELAMPAGO_OPTION_ALIASES = {
    "suco": "Suco natural",
    "suco natural": "Suco natural",
    "laranja": "Suco natural",
    "laranja natural": "Suco natural",
    "refri": "Refri 220ml",
    "refri 220": "Refri 220ml",
    "refri 220ml": "Refri 220ml",
    "refrigerante": "Refri 220ml",
    "refrigerante 220": "Refri 220ml",
    "refrigerante 220ml": "Refri 220ml",
    "coca": "Refri 220ml",
    "coca cola": "Refri 220ml",
}
_PIX_KEY = (get_settings().pix_key or "").strip()


# ============================================================
#  Helpers
# ============================================================

def _normalizar_data_iso(data_str: str) -> str:
    """Converte DD/MM/YYYY → YYYY-MM-DD.  Se já estiver em ISO, retorna como está."""
    try:
        dt = datetime.strptime(data_str.strip(), "%d/%m/%Y")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        return data_str


def _match_closest(valor: str, validos: set[str]) -> str | None:
    """Busca case-insensitive em um conjunto de valores válidos."""
    if not valor:
        return None
    v = valor.strip()
    for valid in validos:
        if v.lower() == valid.lower():
            return valid
    return None


def _normalizar_massa(massa_raw: str | None) -> str | None:
    if not massa_raw:
        return massa_raw
    key = _norm(str(massa_raw))
    return MASSA_SINONIMOS.get(key, massa_raw)


def _is_missing_field(value) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, dict):
        return not bool(value)
    if isinstance(value, list):
        return not bool(value)
    return False


def _canonical_cafeteria_name(name: str | None) -> str:
    raw = (name or "").strip()
    if raw == "Combo Relampago":
        return CHOCO_COMBO_CANONICAL_NAME
    return raw


def _join_option_values(values: tuple[str, ...]) -> str:
    if not values:
        return ""
    if len(values) == 1:
        return values[0]
    return ", ".join(values[:-1]) + f" e {values[-1]}"


def _normalize_cake_option_category(category: str) -> str:
    normalized = (category or "tradicional").strip().lower()
    aliases = {
        "tradicional": "tradicional",
        "bolo tradicional": "tradicional",
        "mesversario": "mesversario",
        "mesversário": "mesversario",
        "revelacao": "mesversario",
        "revelação": "mesversario",
    }
    return aliases.get(normalized, normalized)


def _normalize_cake_option_type(option_type: str) -> str:
    normalized = (option_type or "recheio").strip().lower()
    aliases = {
        "massa": "massa",
        "massas": "massa",
        "tamanho": "tamanho",
        "tamanhos": "tamanho",
        "recheio": "recheio",
        "recheios": "recheio",
        "mousse": "mousse",
        "mousses": "mousse",
        "adicional": "adicional",
        "adicionais": "adicional",
    }
    return aliases.get(normalized, normalized)


def _normalize_payment_data(pagamento: dict | None) -> dict:
    payload = dict(pagamento or {})
    forma = (payload.get("forma") or "").strip()
    troco_para = payload.get("troco_para")
    parcelas = payload.get("parcelas")

    if forma != "Dinheiro":
        payload["troco_para"] = None
    elif troco_para in (None, ""):
        payload["troco_para"] = None
    else:
        try:
            payload["troco_para"] = float(troco_para)
        except (TypeError, ValueError):
            payload["troco_para"] = None

    try:
        parcelas_int = int(parcelas)
    except (TypeError, ValueError):
        parcelas_int = None

    payload["parcelas"] = parcelas_int if parcelas_int and parcelas_int > 1 else None
    return payload


def _validate_cash_change_requirement(payment_data: dict | None) -> str | None:
    payment = dict(payment_data or {})
    method = str(payment.get("forma") or "").strip()
    if method != "Dinheiro":
        return None
    if payment.get("troco_para") is None:
        return (
            "Pagamento em dinheiro: pergunte se o cliente precisa de troco. "
            "Se nao precisar, envie troco_para=0; se precisar, informe o valor."
        )
    return None


def _apply_card_installment_rule(pagamento: dict | None, total_value: float) -> dict:
    payload = dict(pagamento or {})
    forma = (payload.get("forma") or "").strip()
    parcelas = payload.get("parcelas")

    if forma != "Cartão (débito/crédito)":
        payload["parcelas"] = None
        return payload

    if float(total_value or 0) <= CARD_INSTALLMENT_MIN_TOTAL:
        payload["parcelas"] = None
        return payload

    try:
        parcelas_int = int(parcelas)
    except (TypeError, ValueError):
        parcelas_int = None

    if parcelas_int is None or parcelas_int <= 1:
        payload["parcelas"] = None
        return payload

    payload["parcelas"] = min(parcelas_int, CARD_INSTALLMENT_MAX)
    return payload


def _normalize_gift_category(category: str | None) -> str:
    normalized = _normalize_text(category or "cesta_box")
    return GIFT_CATEGORY_ALIASES.get(normalized, normalized.replace(" ", "_"))


def _canonical_cesta_box(raw_value: str | None) -> tuple[str | None, dict | None]:
    normalized = _normalize_text(raw_value)
    if not normalized:
        return None, None

    for code, item in CESTAS_BOX_CATALOGO.items():
        if normalized == code:
            return code, item

    aliases = {
        _normalize_text(item["nome"]): code
        for code, item in CESTAS_BOX_CATALOGO.items()
    }
    aliases.update(
        {
            "box p chocolates": "1",
            "box p chocolates com balao": "2",
            "box m chocolates": "3",
            "box m chocolates balao": "4",
            "box m cafe": "5",
            "box m cafe balao": "6",
            "cesta cafe": "5",
            "cesta de cafe": "5",
            "cesta chocolate": "3",
            "cesta box cafe": "5",
            "cesta box chocolate": "3",
        }
    )
    code = aliases.get(normalized)
    if not code:
        return None, None
    return code, CESTAS_BOX_CATALOGO.get(code)


def _format_currency_brl(value: float | int) -> str:
    return f"R${float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _parse_order_date_label(raw_value: str | None) -> str:
    value = (raw_value or "").strip()
    if not value:
        return ""
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            parsed = datetime.strptime(value, fmt)
            weekday_labels = {
                0: "Segunda",
                1: "Terca",
                2: "Quarta",
                3: "Quinta",
                4: "Sexta",
                5: "Sabado",
                6: "Domingo",
            }
            return f"{parsed.day}/{parsed.month} {weekday_labels[parsed.weekday()]}"
        except ValueError:
            continue
    return value


def _format_compact_hour(raw_value: str | None) -> str:
    value = (raw_value or "").strip()
    if not value:
        return ""
    try:
        parsed = datetime.strptime(value, "%H:%M")
        if parsed.minute == 0:
            return f"{parsed.hour}h"
        return value
    except ValueError:
        return value


@lru_cache(maxsize=1)
def _load_cafeteria_catalog_items() -> tuple[dict, ...]:
    payload = json.loads(CAFETERIA_CATALOG_PATH.read_text(encoding="utf-8"))
    return tuple(item for item in payload.get("items", []) if item.get("catalog") == "cafeteria")


def _cafeteria_search_blob(item: dict) -> str:
    parts = [
        item.get("name", ""),
        item.get("variant", ""),
        item.get("description", ""),
        item.get("section", ""),
        item.get("size", ""),
        item.get("weight_approx", ""),
        " ".join(item.get("options") or []),
        " ".join(item.get("aliases") or []),
    ]
    return _normalize_text(" ".join(part for part in parts if part))


def _candidate_cafeteria_items(raw_name: str, raw_variant: str | None = None) -> list[dict]:
    normalized_name = _normalize_text(raw_name)
    normalized_variant = _normalize_text(raw_variant or "")
    combined = " ".join(part for part in (normalized_name, normalized_variant) if part).strip()
    candidates: list[tuple[float, dict]] = []

    for item in _load_cafeteria_catalog_items():
        name = item.get("name", "")
        name_normalized = _normalize_text(name)
        blob = _cafeteria_search_blob(item)
        score = 0.0

        if combined and combined in blob:
            score += 8.0
        if normalized_name and normalized_name == name_normalized:
            score += 10.0

        alias_target = CAFETERIA_NAME_ALIASES.get(normalized_name)
        if alias_target and alias_target == name:
            score += 9.0

        keywords = CAFETERIA_ITEM_KEYWORDS.get(name, ())
        if keywords and any(keyword in combined for keyword in keywords):
            score += 6.0

        if normalized_variant and item.get("variant") and normalized_variant in _normalize_text(item.get("variant")):
            score += 5.0

        for option in item.get("options") or []:
            if normalized_variant and normalized_variant in _normalize_text(option):
                score += 5.0
            if normalized_name and normalized_name in _normalize_text(option):
                score += 2.5

        if score > 0:
            candidates.append((score, item))

    candidates.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _score, item in candidates]


def _infer_combo_relampago_option(raw_text: str | None) -> str | None:
    normalized = _normalize_text(raw_text or "")
    if not normalized:
        return None
    for alias, canonical in COMBO_RELAMPAGO_OPTION_ALIASES.items():
        if alias in normalized:
            return canonical
    return None


def _validate_cafeteria_item_availability(item: dict, data_entrega: str | None) -> str | None:
    availability_note = _normalize_text(str(item.get("availability_note") or ""))
    if not availability_note:
        return None
    target_date = parse_service_date(data_entrega)
    if target_date is None:
        return None

    # Combos promocionais com restricao semanal devem respeitar a data do atendimento.
    if "somente as tercas" in availability_note and target_date.weekday() != 1:
        return (
            f"{item.get('name', 'Este item')} esta disponivel somente as tercas-feiras. "
            f"Data solicitada: {format_service_date_with_weekday(target_date)}."
        )
    return None


def _resolve_cafeteria_item(
    raw_name: str,
    raw_variant: str | None = None,
) -> tuple[dict | None, str | None, str | None]:
    candidates = _candidate_cafeteria_items(raw_name, raw_variant)
    if not candidates:
        return None, None, f"Nao encontrei '{raw_name}' no catalogo oficial da cafeteria."

    candidate = candidates[0]
    name = candidate.get("name", "")
    normalized_name = _normalize_text(raw_name)
    normalized_variant = _normalize_text(raw_variant or "")
    combined = " ".join(part for part in (normalized_name, normalized_variant) if part).strip()

    if name == "Coca Cola KS" and not (
        "ks" in combined or "coca" in normalized_name or "coca cola" in normalized_name
    ):
        return None, None, "Para bebida, informe se deseja Coca Cola KS ou Refrigerante Lata."

    if name == "Refrigerante Lata" and not ("lata" in combined or "refrigerante" in normalized_name):
        return None, None, "Para bebida, informe se deseja Coca Cola KS ou Refrigerante Lata."

    options = candidate.get("options") or []
    if options:
        option_aliases = {
            _normalize_text(option): option for option in options
        }
        if name == "Combo Relampago":
            inferred_option = _infer_combo_relampago_option(raw_variant) or _infer_combo_relampago_option(raw_name)
            if inferred_option:
                raw_variant = inferred_option
            option_aliases.update(
                {
                    _normalize_text(alias): canonical
                    for alias, canonical in COMBO_RELAMPAGO_OPTION_ALIASES.items()
                }
            )
        matched_option = _match_catalog_value(
            raw_variant or raw_name,
            tuple(options),
            aliases=option_aliases,
        )
        if not matched_option:
            return None, None, CAFETERIA_VARIANT_REQUIRED_HINTS.get(
                name,
                f"Informe uma opcao valida para {name}: " + ", ".join(options) + ".",
            )
        return candidate, matched_option, None

    same_name_variants = [item for item in _load_cafeteria_catalog_items() if item.get("name") == name and item.get("variant")]
    if same_name_variants:
        matched_variant = None
        for item in same_name_variants:
            variant = item.get("variant", "")
            if normalized_variant and normalized_variant in _normalize_text(variant):
                matched_variant = item
                break
            if not normalized_variant and normalized_name in _normalize_text(variant):
                matched_variant = item
                break
        if matched_variant is None:
            variant_labels = [str(item.get("variant")) for item in same_name_variants if item.get("variant")]
            return None, None, CAFETERIA_VARIANT_REQUIRED_HINTS.get(
                name,
                f"Informe uma variacao valida para {name}: " + ", ".join(variant_labels) + ".",
            )
        return matched_variant, str(matched_variant.get("variant") or ""), None

    return candidate, raw_variant or None, None


def _format_cafeteria_item_label(item: dict, selected_variant: str | None = None) -> str:
    base_name = _canonical_cafeteria_name(str(item.get("name") or "Item"))
    variant = (selected_variant or item.get("variant") or "").strip()
    if variant:
        return f"{base_name} ({variant})"
    return base_name


def _build_cafeteria_process_payload(
    *,
    itens: list[dict],
    data_entrega: str | None,
    horario_retirada: str | None,
    modo_recebimento: str,
    endereco: str | None,
    pagamento: dict,
    valor_total: float,
    taxa_entrega: float,
) -> dict:
    return {
        "categoria": "cafeteria",
        "descricao": ", ".join(item["descricao"] for item in itens),
        "itens": itens,
        "data_entrega": data_entrega,
        "horario_retirada": horario_retirada,
        "modo_recebimento": modo_recebimento,
        "endereco": endereco,
        "pagamento": pagamento,
        "valor_total": valor_total,
        "taxa_entrega": taxa_entrega,
    }


def _today_service_date_str() -> str:
    return format_service_date(now_in_bot_timezone().date()) or ""


def _cafeteria_item_merge_key(item: dict) -> tuple[str, str, str]:
    return (
        str(item.get("nome") or "").strip(),
        str(item.get("variante") or "").strip(),
        str(item.get("observacao") or "").strip(),
    )


def _merge_cafeteria_validated_items(items: list[dict]) -> list[dict]:
    merged: list[dict] = []
    index_by_key: dict[tuple[str, str, str], int] = {}

    for item in items:
        key = _cafeteria_item_merge_key(item)
        existing_index = index_by_key.get(key)
        if existing_index is None:
            merged.append(dict(item))
            index_by_key[key] = len(merged) - 1
            continue

        current = merged[existing_index]
        current["quantidade"] += int(item.get("quantidade") or 0)
        current["preco_total"] = round(float(current.get("preco_total") or 0) + float(item.get("preco_total") or 0), 2)
        current["descricao"] = f"{current['quantidade']}x {current['label']}"
    return merged


def _build_cafeteria_confirmation_message(prepared: dict) -> str:
    item_lines = [f"- {item['descricao']}: {_format_currency_brl(float(item['preco_total']))}" for item in prepared["itens"]]
    mode = str(prepared.get("modo_recebimento") or "").strip().lower()
    date_label = _parse_order_date_label(prepared.get("data_entrega")) or "A confirmar"
    hour_label = _format_compact_hour(prepared.get("horario_retirada")) or "A confirmar"
    delivery_line = "Retirada na loja" if mode == "retirada" else "Entrega"
    endereco = str(prepared.get("endereco") or "").strip()
    if endereco and mode == "entrega":
        delivery_line = f"Entrega: {endereco}"

    total_label = _format_currency_brl(float(prepared["valor_total"]))
    if float(prepared.get("taxa_entrega") or 0) > 0:
        total_label += f" (+ {_format_currency_brl(float(prepared['taxa_entrega']))} entrega)"

    lines = [
        "Resumo final do pedido (rascunho)",
        "",
        "Confirma seu pedido?",
        "📦 Pedido cafeteria",
        "Itens:",
        *item_lines,
        f"📅 Data: {date_label} | Horario: {hour_label}",
        f"🚗 {delivery_line}",
        f"💰 Total: {total_label}",
        "💳 " + _build_payment_line(prepared.get("pagamento")).replace("Forma de pagamento: ", "Pagamento: "),
        "🎁 Kit Festou: Nao incluso",
    ]
    lines.extend(
        [
            f"Subtotal: {_format_currency_brl(float(prepared['subtotal']))}",
        ]
    )
    if float(prepared.get("taxa_entrega") or 0) > 0:
        lines.append(f"Taxa entrega: {_format_currency_brl(float(prepared['taxa_entrega']))}")
    lines.append(f"Valor: {_format_currency_brl(float(prepared['valor_total']))}")
    lines.append("")
    lines.append("Ainda nao foi salvo como pedido confirmado no sistema.")
    lines.append(
        'Se estiver tudo certo, me envie uma confirmacao final explicita para concluir '
        '(ex.: "sim", "ok", "ta bom", "certo" ou "confirmado").'
    )
    return "\n".join(lines)


def _prepare_cafeteria_order_data(order_details: "CafeteriaOrderSchema") -> tuple[dict | None, str | None]:
    dados = order_details.model_dump()
    dados["pagamento"] = _normalize_payment_data(dados.get("pagamento"))
    required_error = _validate_required_payment_data(dados.get("pagamento"))
    if required_error:
        return None, required_error
    payment_error = _validate_cash_change_requirement(dados.get("pagamento"))
    if payment_error:
        return None, payment_error
    if not (dados.get("data_entrega") or "").strip():
        dados["data_entrega"] = _today_service_date_str()

    schedule_error = validate_service_schedule(dados.get("data_entrega"), dados.get("horario_retirada"))
    if schedule_error:
        return None, schedule_error

    if dados["modo_recebimento"] == "entrega" and not (dados.get("endereco") or "").strip():
        return None, "Informe o endereco completo para entrega."

    if dados["modo_recebimento"] == "entrega" and not (dados.get("horario_retirada") or "").strip():
        return None, "Informe o horario da entrega."

    if dados["modo_recebimento"] == "entrega" and not _horario_entrega_permitido(dados.get("horario_retirada")):
        return None, (
            f"Entregas sao realizadas ate as {LIMITE_HORARIO_ENTREGA}. "
            "Ajuste o horario ou altere para retirada."
        )

    validated_items: list[dict] = []
    subtotal = 0.0
    for raw_item in dados.get("itens") or []:
        if int(raw_item["quantidade"]) <= 0:
            return None, f"A quantidade de '{raw_item['nome']}' deve ser maior que zero."
        item, selected_variant, error = _resolve_cafeteria_item(raw_item["nome"], raw_item.get("variante"))
        if error:
            return None, error
        assert item is not None
        availability_error = _validate_cafeteria_item_availability(item, dados.get("data_entrega"))
        if availability_error:
            return None, availability_error
        unit_price = float(item.get("price_brl") or 0)
        quantity = int(raw_item["quantidade"])
        line_total = unit_price * quantity
        subtotal += line_total
        label = _format_cafeteria_item_label(item, selected_variant)
        if raw_item.get("observacao"):
            label = f"{label} [{raw_item['observacao'].strip()}]"
        validated_items.append(
            {
                "nome": _canonical_cafeteria_name(str(item.get("name") or "")),
                "variante": selected_variant,
                "observacao": (raw_item.get("observacao") or "").strip() or None,
                "quantidade": quantity,
                "preco_unitario": unit_price,
                "preco_total": line_total,
                "label": label,
                "descricao": f"{quantity}x {label}",
            }
        )

    if not validated_items:
        return None, "Informe pelo menos um item valido da cafeteria."

    validated_items = _merge_cafeteria_validated_items(validated_items)
    subtotal = round(sum(float(item["preco_total"]) for item in validated_items), 2)

    taxa_entrega = float(dados.get("taxa_entrega") or 0)
    if dados["modo_recebimento"] == "entrega" and taxa_entrega <= 0:
        taxa_entrega = TAXA_ENTREGA_CAFETERIA
    valor_total = round(subtotal + taxa_entrega, 2)
    if valor_total <= 0:
        return None, "Valor total invalido. Revise os itens para gerar um total maior que R$0,00."
    dados["pagamento"] = _apply_card_installment_rule(dados.get("pagamento"), valor_total)

    return {
        "itens": validated_items,
        "data_entrega": dados.get("data_entrega"),
        "horario_retirada": dados.get("horario_retirada"),
        "modo_recebimento": dados["modo_recebimento"],
        "endereco": dados.get("endereco"),
        "pagamento": dados.get("pagamento", {}),
        "subtotal": subtotal,
        "taxa_entrega": taxa_entrega,
        "valor_total": valor_total,
    }, None


def _build_gift_process_payload(dados: dict) -> dict:
    return {
        "categoria": dados.get("categoria"),
        "cesta_nome": dados.get("produto") if dados.get("categoria") == "cesta_box" else None,
        "descricao": dados.get("descricao") or dados.get("produto") or "Presente especial",
        "data_entrega": dados.get("data_entrega"),
        "horario_retirada": dados.get("horario_retirada"),
        "modo_recebimento": dados.get("modo_recebimento"),
        "endereco": dados.get("endereco"),
        "pagamento": dados.get("pagamento", {}),
        "valor_total": dados.get("valor_total"),
        "taxa_entrega": dados.get("taxa_entrega", 0.0),
    }


def _build_gift_detail_line(dados: dict) -> str:
    description = (dados.get("descricao") or "").strip()
    if not description:
        return ""
    return f"Detalhes: {description}"


def _prepare_gift_order_data(order_details: "GiftOrderSchema") -> tuple[dict | None, str | None]:
    dados = order_details.model_dump()
    dados["categoria"] = _normalize_gift_category(dados.get("categoria"))
    dados["pagamento"] = _normalize_payment_data(dados.get("pagamento"))
    required_error = _validate_required_payment_data(dados.get("pagamento"))
    if required_error:
        return None, required_error
    payment_error = _validate_cash_change_requirement(dados.get("pagamento"))
    if payment_error:
        return None, payment_error

    missing_required: list[str] = []
    for field_name in ("categoria", "produto", "data_entrega", "modo_recebimento", "pagamento"):
        if _is_missing_field(dados.get(field_name)):
            missing_required.append(field_name)
    if str(dados.get("modo_recebimento") or "").strip().lower() == "entrega" and _is_missing_field(dados.get("endereco")):
        missing_required.append("endereco")
    if missing_required:
        return None, "Campos obrigatorios pendentes: " + ", ".join(sorted(set(missing_required))) + "."

    schedule_error = validate_service_schedule(dados.get("data_entrega"), dados.get("horario_retirada"))
    if schedule_error:
        return None, schedule_error

    if dados["categoria"] != "cesta_box":
        return None, (
            "Caixinha de chocolate e flores estao no catalogo regular, mas a montagem final ainda exige confirmacao humana. "
            "Use o catalogo estruturado para informar opcoes e, se o cliente quiser fechar, encaminhe para atendimento humano."
        )

    code, cesta_info = _canonical_cesta_box(dados.get("produto") or dados.get("descricao"))
    if not code or not cesta_info:
        return None, (
            "Nao encontrei essa cesta box no catalogo regular. "
            "Opcoes canonicas: BOX P Chocolates, BOX P Chocolates (com Balao), BOX M Chocolates, "
            "BOX M Chocolates Balao, BOX M Cafe e BOX M Cafe Balao."
        )

    dados["codigo"] = code
    dados["produto"] = str(cesta_info["nome"])
    dados["descricao"] = str(cesta_info.get("descricao") or dados.get("descricao") or cesta_info["nome"])
    dados["serve"] = int(cesta_info.get("serve") or 0)
    dados["valor_base"] = float(cesta_info.get("preco") or 0)

    if dados["modo_recebimento"] == "entrega":
        if not (dados.get("endereco") or "").strip():
            return None, "Informe o endereco completo para entrega."
        if not (dados.get("horario_retirada") or "").strip():
            return None, "Informe o horario da entrega."
        if not _horario_entrega_permitido(dados.get("horario_retirada")):
            return None, (
                f"Entregas sao realizadas ate as {LIMITE_HORARIO_ENTREGA}. "
                "Ajuste o horario ou altere para retirada."
            )
        if float(dados.get("taxa_entrega") or 0) <= 0:
            dados["taxa_entrega"] = TAXA_ENTREGA_PADRAO
    else:
        dados["endereco"] = None
        dados["taxa_entrega"] = 0.0

    dados["valor_total"] = round(float(dados["valor_base"]) + float(dados.get("taxa_entrega") or 0), 2)
    if float(dados.get("valor_total") or 0) <= 0:
        return None, "Valor total invalido. Revise os itens para gerar um total maior que R$0,00."
    dados["pagamento"] = _apply_card_installment_rule(dados.get("pagamento"), float(dados["valor_total"]))
    dados["data_entrega"] = _normalizar_data_iso(dados["data_entrega"])
    return dados, None


def _match_catalog_value(
    raw_value: str | None,
    valid_values: tuple[str, ...] | list[str],
    *,
    aliases: dict[str, str] | None = None,
) -> str | None:
    if not raw_value:
        return None

    normalized = _norm(raw_value)
    if aliases and normalized in aliases:
        alias_value = aliases[normalized]
        for valid in valid_values:
            if _norm(valid) == _norm(alias_value):
                return valid
        for valid in valid_values:
            if _norm(alias_value) in _norm(valid):
                return valid

    for valid in valid_values:
        valid_normalized = _norm(valid)
        if normalized == valid_normalized:
            return valid
        if normalized in valid_normalized or valid_normalized in normalized:
            return valid
    return None


def _normalize_cake_pricing_category(category: str) -> str:
    normalized = _normalize_cake_option_category(category)
    aliases = {
        "gourmet": "gourmet",
        "gourmet ingles": "ingles",
        "gourmet inglês": "ingles",
        "ingles": "ingles",
        "inglês": "ingles",
        "redondo": "redondo",
        "redondo p6": "redondo",
        "gourmet redondo": "redondo",
        "gourmet redondo p6": "redondo",
        "torta": "torta",
        "simples": "simples",
        "linha simples": "simples",
        "bolo simples": "simples",
        "caseiro": "simples",
        "bolo caseiro": "simples",
        "caseirinho": "simples",
        "bolo caseirinho": "simples",
    }
    return aliases.get(normalized, normalized)


def _normalize_simple_cake_flavor(value: str | None) -> str | None:
    if not value:
        return None
    normalized = _norm(value)
    aliases = {
        "chocolate": "Chocolate",
        "bolo de chocolate": "Chocolate",
        "cenoura": "Cenoura",
        "bolo de cenoura": "Cenoura",
    }
    canonical = aliases.get(normalized)
    if canonical:
        return canonical
    return _match_catalog_value(value, LINE_SIMPLE_FLAVORS)


def _normalize_simple_cake_coverage(value: str | None) -> str | None:
    if not value:
        return None
    normalized = _norm(value)
    aliases = {
        "vulcao": "Vulcão",
        "vulcão": "Vulcão",
        "bolo vulcao": "Vulcão",
        "bolo vulcão": "Vulcão",
        "simples": "Simples",
        "tradicional": "Simples",
    }
    canonical = aliases.get(normalized)
    if canonical:
        return canonical
    return _match_catalog_value(value, LINE_SIMPLE_COVERAGES)


def _extract_simple_cake_details(*values: str | None) -> tuple[str | None, str | None]:
    joined = " ".join((value or "") for value in values if value)
    flavor = _normalize_simple_cake_flavor(joined)
    coverage = _normalize_simple_cake_coverage(joined)
    return flavor, coverage


def _build_cake_pricing_payload(
    *,
    category: str,
    tamanho: str | None,
    produto: str | None,
    adicional: str | None,
    cobertura: str | None,
    kit_festou: bool,
    quantidade: int,
) -> tuple[dict | None, str | None]:
    try:
        normalized_quantity = max(1, int(quantidade or 1))
    except (TypeError, ValueError):
        normalized_quantity = 1

    payload: dict = {
        "categoria": category,
        "kit_festou": kit_festou,
        "quantidade": normalized_quantity,
    }

    if category == "tradicional":
        normalized_size = _normaliza_tamanho(tamanho or "")
        if normalized_size not in TAMANHOS_TRADICIONAIS:
            return None, "Informe um tamanho valido da linha tradicional: B3, B4, B6 ou B7."
        payload["tamanho"] = normalized_size
        payload["fruta_ou_nozes"] = _match_closest(adicional or "", set(ADICIONAIS_TRADICIONAIS)) or adicional
        return payload, None

    if category == "mesversario":
        normalized_size = _normaliza_tamanho(tamanho or "")
        if normalized_size not in TAMANHOS_MESVERSARIO:
            return None, "Informe um tamanho valido do mesversario: P4 ou P6."
        payload["tamanho"] = normalized_size
        return payload, None

    if category == "ingles":
        matched = _match_catalog_value(produto, tuple(INGLES.keys()), aliases=GOURMET_ALIASES)
        if not matched:
            return None, "Informe um sabor valido do gourmet ingles."
        payload["produto"] = matched
        return payload, None

    if category == "redondo":
        matched = _match_catalog_value(produto, tuple(REDONDOS_P6.keys()), aliases=REDONDOS_ALIASES)
        if not matched:
            return None, "Informe um sabor valido do gourmet redondo P6."
        payload["produto"] = matched
        return payload, None

    if category == "torta":
        matched = _match_catalog_value(produto, tuple(TORTAS.keys()), aliases=TORTAS_ALIASES)
        if not matched:
            return None, "Informe um sabor valido de torta."
        payload["produto"] = matched
        return payload, None

    if category == "simples":
        flavor, inferred_cover = _extract_simple_cake_details(produto, cobertura)
        normalized_cover = _normalize_simple_cake_coverage(cobertura) or inferred_cover
        if not normalized_cover:
            return None, "Informe uma cobertura valida da linha simples: Vulcao ou Simples."
        payload["cobertura"] = normalized_cover
        payload["sabor"] = flavor or "Chocolate"
        return payload, None

    return None, "Categoria de bolo invalida para consulta de preco."


def _build_cake_pricing_overview(category: str) -> str:
    if category == "tradicional":
        lines = ["Precos canonicos da linha tradicional:"]
        for size in TAMANHOS_TRADICIONAIS:
            info = TRADICIONAL_BASE[size]
            lines.append(f"- {size} (ate {info['serve']} pessoas): {_format_currency_brl(info['preco'])}")
        lines.append("- Adicionais alteram o valor final: Morango, Ameixa, Nozes, Cereja e Abacaxi.")
        return "\n".join(lines)

    if category == "mesversario":
        lines = ["Precos canonicos do mesversario:"]
        for size in TAMANHOS_MESVERSARIO:
            info = MESVERSARIO[size]
            lines.append(f"- {size} (ate {info['serve']} pessoas): {_format_currency_brl(info['preco'])}")
        return "\n".join(lines)

    if category == "ingles":
        lines = ["Precos canonicos do gourmet ingles (serve cerca de 10 pessoas):"]
        for name, info in INGLES.items():
            lines.append(f"- {name}: {_format_currency_brl(info['preco'])}")
        return "\n".join(lines)

    if category == "redondo":
        lines = ["Precos canonicos do gourmet redondo P6 (serve cerca de 20 pessoas):"]
        for name, info in REDONDOS_P6.items():
            lines.append(f"- {name}: {_format_currency_brl(info['preco'])}")
        return "\n".join(lines)

    if category == "torta":
        lines = ["Precos canonicos das tortas (serve 16 fatias):"]
        for name, info in TORTAS.items():
            lines.append(f"- {name}: {_format_currency_brl(info['preco'])}")
        return "\n".join(lines)

    if category == "simples":
        lines = ["Precos canonicos da linha simples (serve 8 fatias):"]
        for cover, price in LINHA_SIMPLES["coberturas"].items():
            lines.append(f"- {cover}: {_format_currency_brl(price)}")
        lines.append("- Sabores disponiveis: Chocolate e Cenoura.")
        return "\n".join(lines)

    if category == "gourmet":
        return (
            "A linha gourmet tem dois formatos com precos diferentes:\n"
            "- Gourmet ingles: serve cerca de 10 pessoas.\n"
            "- Gourmet redondo P6: serve cerca de 20 pessoas.\n"
            "Informe se o cliente quer ingles ou redondo P6 antes de citar o preco."
        )

    return "Categoria de bolo invalida para consulta de preco."


def _validar_campos_bolo(dados: dict) -> list[str]:
    """Valida campos do pedido e retorna lista de erros descritivos."""
    erros: list[str] = []
    linha = (dados.get("linha") or "").lower()
    categoria = (dados.get("categoria") or "").lower()

    if linha not in LINHAS_VALIDAS:
        erros.append(f"Linha '{dados.get('linha')}' invalida. Opcoes: {', '.join(sorted(LINHAS_VALIDAS))}.")

    if categoria not in CATEGORIAS_VALIDAS:
        erros.append(f"Categoria '{dados.get('categoria')}' invalida. Opcoes: {', '.join(sorted(CATEGORIAS_VALIDAS))}.")

    # --- Tradicional: precisa de tamanho, massa, recheio, mousse ---
    if categoria == "tradicional":
        tam = _normaliza_tamanho(dados.get("tamanho") or "")
        if tam not in TAMANHOS_BOLO:
            erros.append(f"Tamanho '{dados.get('tamanho')}' invalido. Use: B3, B4, B6 ou B7.")
        if not _match_closest(dados.get("massa") or "", MASSAS_VALIDAS):
            erros.append(f"Massa '{dados.get('massa')}' invalida. Opcoes: Branca, Chocolate ou Mesclada.")
        if not dados.get("recheio"):
            erros.append("Recheio e obrigatorio para linha tradicional.")
        if not dados.get("mousse") and (dados.get("recheio") or "").lower() != "casadinho":
            erros.append("Mousse e obrigatorio (exceto recheio Casadinho). Opcoes: Ninho, Trufa Branca, Chocolate, Trufa Preta.")

    # --- Mesversário: precisa de tamanho P4/P6 ---
    elif categoria == "mesversario":
        tam = _normaliza_tamanho(dados.get("tamanho") or "")
        if tam not in {"P4", "P6"}:
            erros.append(f"Tamanho '{dados.get('tamanho')}' invalido para mesversario. Use: P4 ou P6.")

    # --- Gourmet / Torta: precisa de produto ---
    elif categoria in ("ingles", "redondo", "torta"):
        if not dados.get("produto"):
            erros.append(f"Produto/sabor e obrigatorio para categoria {categoria}.")

    # --- Simples: precisa de produto (sabor+cobertura na descricao) ---
    elif categoria == "simples":
        pass  # descricao cobre

    # --- Entrega: precisa de endereço ---
    if dados.get("modo_recebimento") == "entrega":
        if not dados.get("endereco"):
            erros.append("Endereco e obrigatorio quando o modo de recebimento for entrega.")

    return erros


def _validate_required_payment_data(pagamento: dict | None) -> str | None:
    payment = dict(pagamento or {})
    method = str(payment.get("forma") or "").strip()
    if not method or method == "Pendente":
        return "Forma de pagamento obrigatoria: PIX, Cartão (débito/crédito) ou Dinheiro."
    return None


def _validate_required_cake_fields(dados: dict) -> list[str]:
    categoria = (dados.get("categoria") or "").strip().lower()
    missing: list[str] = []

    by_category = {
        "tradicional": ("massa", "recheio", "tamanho", "data_entrega", "modo_recebimento", "pagamento"),
        "ingles": ("produto", "data_entrega", "modo_recebimento", "pagamento"),
        "redondo": ("produto", "data_entrega", "modo_recebimento", "pagamento"),
        "torta": ("produto", "data_entrega", "modo_recebimento", "pagamento"),
        "mesversario": ("tamanho", "data_entrega", "modo_recebimento", "pagamento"),
        "simples": ("produto", "data_entrega", "modo_recebimento", "pagamento"),
        "babycake": ("produto", "data_entrega", "modo_recebimento", "pagamento"),
    }
    required = by_category.get(categoria, ("data_entrega", "modo_recebimento", "pagamento"))
    for field_name in required:
        if _is_missing_field(dados.get(field_name)):
            missing.append(field_name)

    if categoria == "tradicional":
        recheio = str(dados.get("recheio") or "").strip().casefold()
        if recheio != "casadinho" and _is_missing_field(dados.get("mousse")):
            missing.append("mousse")

    if str(dados.get("modo_recebimento") or "").strip().lower() == "entrega" and _is_missing_field(dados.get("endereco")):
        missing.append("endereco")

    return sorted(set(missing))


def _calcular_preco_pedido(dados: dict) -> Tuple[float, int]:
    """Calcula preço a partir dos dados do CakeOrderSchema mapeados para calcular_total."""
    categoria = (dados.get("categoria") or "").lower()

    payload: dict = {
        "categoria": categoria,
        "kit_festou": dados.get("kit_festou", False),
        "quantidade": dados.get("quantidade", 1),
    }

    if categoria == "tradicional":
        payload["tamanho"] = _normaliza_tamanho(dados.get("tamanho") or "")
        payload["fruta_ou_nozes"] = dados.get("adicional")
    elif categoria in ("ingles", "redondo", "torta"):
        payload["produto"] = dados.get("produto")
    elif categoria == "mesversario":
        payload["tamanho"] = _normaliza_tamanho(dados.get("tamanho") or "")
    elif categoria == "simples":
        payload["cobertura"] = dados.get("cobertura") or _normalize_simple_cake_coverage(dados.get("produto")) or "Simples"
        payload["sabor"] = dados.get("produto")

    return calcular_total(payload)


def _build_cake_process_payload(dados: dict) -> dict:
    return {
        "categoria": dados.get("categoria"),
        "linha": dados.get("linha"),
        "produto": dados.get("produto"),
        "cobertura": dados.get("cobertura"),
        "tamanho": dados.get("tamanho"),
        "massa": dados.get("massa"),
        "recheio": dados.get("recheio"),
        "mousse": dados.get("mousse"),
        "adicional": dados.get("adicional"),
        "descricao": dados.get("descricao"),
        "data_entrega": dados.get("data_entrega"),
        "horario_retirada": dados.get("horario_retirada"),
        "modo_recebimento": dados.get("modo_recebimento"),
        "endereco": dados.get("endereco"),
        "pagamento": dados.get("pagamento"),
        "quantidade": dados.get("quantidade"),
        "valor_total": dados.get("valor_total"),
    }


def _build_sweet_process_payload(
    *,
    data_entrega: str,
    horario_retirada: str | None,
    modo_recebimento: str,
    endereco: str | None,
    pagamento: dict,
    itens_validados: list[dict],
    valor_total: float,
) -> dict:
    return {
        "categoria": "doces",
        "descricao": "Doces avulsos",
        "itens": [f"{item['nome']} x{item['qtd']}" for item in itens_validados],
        "data_entrega": data_entrega,
        "horario_retirada": horario_retirada,
        "modo_recebimento": modo_recebimento,
        "endereco": endereco,
        "pagamento": pagamento,
        "valor_total": valor_total,
    }


def _build_cake_confirmation_title(dados: dict) -> str:
    categoria = (dados.get("categoria") or "").strip().lower()
    tamanho = (dados.get("tamanho") or "").strip()
    massa = (dados.get("massa") or "").strip()
    produto = (dados.get("produto") or "").strip()
    descricao = (dados.get("descricao") or "").strip()

    if categoria == "tradicional" and tamanho and massa:
        return f"Bolo {tamanho} de {massa.lower()}"
    if categoria == "mesversario" and tamanho:
        return f"Bolo mesversario {tamanho}"
    if categoria == "ingles" and produto:
        return f"Bolo gourmet ingles {produto}"
    if categoria == "redondo" and produto:
        return f"Bolo gourmet redondo {produto}"
    if categoria == "torta" and produto:
        return f"Torta {produto}"
    if categoria == "simples" and produto:
        coverage = (dados.get("cobertura") or "").strip()
        if coverage:
            return f"Bolo simples de {produto.lower()} ({coverage.lower()})"
        return f"Bolo simples de {produto.lower()}"
    return descricao or "Pedido"


def _build_cake_flavor_line(dados: dict) -> str:
    recheio = (dados.get("recheio") or "").strip()
    mousse = (dados.get("mousse") or "").strip()
    adicional = (dados.get("adicional") or "").strip()

    if not recheio and not mousse and not adicional:
        return ""

    base = recheio
    if mousse and recheio.casefold() != "casadinho":
        base = f"{recheio} com {mousse}" if recheio else mousse

    if adicional:
        if base:
            return f"Recheio: {base} e adicional de {adicional.lower()}"
        return f"Adicional: {adicional}"

    if base:
        return f"Recheio: {base}"
    return ""


def _build_service_line(dados: dict) -> str:
    mode_label = "Retirada" if (dados.get("modo_recebimento") or "").strip().lower() == "retirada" else "Entrega"
    date_label = _parse_order_date_label(dados.get("data_entrega"))
    hour_label = _format_compact_hour(dados.get("horario_retirada"))
    parts = [mode_label]
    if date_label:
        parts.append(date_label)
    if hour_label:
        parts.append(hour_label)
    return " ".join(parts)


def _build_payment_line(payment: dict | None) -> str:
    payment_data = payment or {}
    method = str(payment_data.get("forma") or "").strip() or "A confirmar"
    installments = payment_data.get("parcelas")
    change_for = payment_data.get("troco_para")

    details = [method]
    if method.casefold() == "pix" and _PIX_KEY:
        details.append(f"chave {_PIX_KEY}")
    if method.casefold().startswith("cartao") and installments:
        details.append(f"{int(installments)}x")
    if method.casefold() == "dinheiro" and change_for:
        details.append(f"troco para {_format_currency_brl(float(change_for))}")
    return "Forma de pagamento: " + " | ".join(details)


def _build_draft_confirmation_message(
    *,
    title: str,
    flavor_line: str,
    service_line: str,
    total_value: float,
    payment_line: str,
    endereco: str | None = None,
    delivery_fee: float = 0.0,
    kit_festou: bool = False,
) -> str:
    item_summary = title
    if flavor_line:
        item_summary = f"{title} | {flavor_line}"

    mode_token = "Retirada"
    date_line = service_line
    if service_line and " " in service_line:
        mode_token, date_line = service_line.split(" ", 1)

    delivery_line = "Retirada na loja" if mode_token.casefold() == "retirada" else "Entrega"
    if endereco and delivery_line.casefold() == "entrega":
        delivery_line = f"Entrega: {endereco}"

    date_label = date_line or "A confirmar"
    hour_label = "A confirmar"
    if date_line:
        hour_match = re.search(r"\b(\d{1,2}h(?:\d{2})?|\d{1,2}:\d{2})\b", date_line)
        if hour_match:
            hour_label = hour_match.group(1)
            date_label = date_line.replace(hour_match.group(1), "").strip() or "A confirmar"

    total_label = _format_currency_brl(total_value)
    if float(delivery_fee or 0) > 0:
        total_label += f" (+ {_format_currency_brl(float(delivery_fee))} entrega)"

    lines = [
        "Resumo final do pedido (rascunho)",
        "",
        "Confirma seu pedido?",
        f"📦 {item_summary}",
        f"📅 Data: {date_label} | Horario: {hour_label}",
        f"🚗 {delivery_line}",
        f"💰 Total: {total_label}",
        "💳 " + payment_line.replace("Forma de pagamento: ", "Pagamento: "),
        f"🎁 Kit Festou: {'Sim (+R$35,00)' if kit_festou else 'Nao incluso'}",
    ]
    if float(delivery_fee or 0) > 0:
        lines.append(f"Taxa entrega: {_format_currency_brl(float(delivery_fee))}")
    lines.append(f"Valor: {_format_currency_brl(total_value)}")
    lines.append("")
    lines.append("Ainda nao foi salvo como pedido confirmado no sistema.")
    lines.append(
        'Se estiver tudo certo, me envie uma confirmacao final explicita para concluir '
        '(ex.: "sim", "ok", "ta bom", "certo" ou "confirmado").'
    )
    return "\n".join(lines)


def _sync_ai_process(
    *,
    phone: str,
    customer_id: int,
    process_type: str,
    stage: str,
    status: str,
    draft_payload: dict,
    source: str,
    order_id: int | None = None,
) -> None:
    get_customer_process_repository().upsert_process(
        phone=phone,
        customer_id=customer_id,
        process_type=process_type,
        stage=stage,
        status=status,
        source=source,
        draft_payload=draft_payload,
        order_id=order_id,
    )


def _prepare_cake_order_data(order_details: "CakeOrderSchema") -> tuple[dict | None, str | None]:
    dados = order_details.model_dump()
    dados["linha"] = _linha_canonica(dados.get("linha"))
    categoria = (dados.get("categoria") or "").lower()
    dados["categoria"] = categoria
    dados["pagamento"] = _normalize_payment_data(dados.get("pagamento"))
    payment_error = _validate_cash_change_requirement(dados.get("pagamento"))
    if payment_error:
        return None, payment_error

    schedule_error = validate_service_schedule(dados.get("data_entrega"), dados.get("horario_retirada"))
    if schedule_error:
        return None, schedule_error

    if dados.get("tamanho"):
        dados["tamanho"] = _normaliza_tamanho(dados["tamanho"])

    if dados.get("massa"):
        dados["massa"] = _normalizar_massa(dados.get("massa"))
        matched = _match_closest(dados["massa"], MASSAS_VALIDAS)
        if matched:
            dados["massa"] = matched

    if dados.get("produto") and dados["linha"] in ("gourmet", "torta"):
        normalizado = _normaliza_produto(
            "torta" if categoria == "torta" else ("redondo" if categoria == "redondo" else "gourmet"),
            dados["produto"],
        )
        if normalizado:
            dados["produto"] = normalizado

    if categoria == "simples":
        inferred_flavor, inferred_coverage = _extract_simple_cake_details(
            dados.get("produto"),
            dados.get("cobertura"),
            dados.get("descricao"),
        )
        if inferred_flavor:
            dados["produto"] = inferred_flavor
        if inferred_coverage:
            dados["cobertura"] = inferred_coverage

    if dados["modo_recebimento"] == "entrega" and not _horario_entrega_permitido(dados.get("horario_retirada")):
        return None, (
            f"Entregas sao realizadas ate as {LIMITE_HORARIO_ENTREGA}. "
            "Ajuste o horario ou altere para retirada."
        )

    erros = _validar_campos_bolo(dados)
    if erros:
        return None, "Erro de validacao:\n- " + "\n- ".join(erros)

    payment_error = _validate_required_payment_data(dados.get("pagamento"))
    if payment_error:
        return None, payment_error

    missing_required = _validate_required_cake_fields(dados)
    if missing_required:
        return None, "Campos obrigatorios pendentes: " + ", ".join(missing_required) + "."

    try:
        valor_total, serve_pessoas = _calcular_preco_pedido(dados)
        if dados["modo_recebimento"] == "entrega":
            valor_total += dados.get("taxa_entrega", 0) or TAXA_ENTREGA_PADRAO
        dados["valor_total"] = valor_total
        dados["serve_pessoas"] = serve_pessoas
    except Exception:
        return None, "Nao consegui calcular o valor total com os dados informados. Revise os campos do pedido."

    if float(dados.get("valor_total") or 0) <= 0:
        return None, "Valor total invalido. Revise os itens para gerar um total maior que R$0,00."

    dados["pagamento"] = _apply_card_installment_rule(
        dados.get("pagamento"),
        float(dados.get("valor_total") or 0),
    )

    if dados["modo_recebimento"] == "entrega" and dados.get("taxa_entrega", 0) == 0:
        dados["taxa_entrega"] = TAXA_ENTREGA_PADRAO

    dados["data_entrega"] = _normalizar_data_iso(dados["data_entrega"])
    return dados, None


def _prepare_sweet_order_data(order_details: "SweetOrderSchema") -> tuple[dict | None, str | None]:
    dados = order_details.model_dump()
    dados["pagamento"] = _normalize_payment_data(dados.get("pagamento"))
    required_error = _validate_required_payment_data(dados.get("pagamento"))
    if required_error:
        return None, required_error
    payment_error = _validate_cash_change_requirement(dados.get("pagamento"))
    if payment_error:
        return None, payment_error
    itens_validados: List[Dict] = []
    total_doces = 0.0
    erros: list[str] = []

    schedule_error = validate_service_schedule(dados.get("data_entrega"), dados.get("horario_retirada"))
    if schedule_error:
        return None, schedule_error

    for item in dados.get("itens", []):
        nome_raw = item.get("nome", "")
        qtd = item.get("quantidade", 1)
        if int(qtd or 0) <= 0:
            erros.append(f"Quantidade invalida para '{nome_raw}': informe valor maior que zero.")
            continue

        nome_canonico = _canonical_doce(nome_raw)
        if not nome_canonico:
            erros.append(f"Doce nao reconhecido: '{nome_raw}'. Verifique o nome no cardapio.")
            continue

        preco_unit = DOCES_UNITARIOS[nome_canonico]
        preco_total = round(preco_unit * qtd, 2)
        total_doces += preco_total

        itens_validados.append(
            {
                "nome": nome_canonico,
                "qtd": qtd,
                "preco": preco_total,
                "unit": preco_unit,
            }
        )

    if erros:
        return None, "Erro de validacao:\n- " + "\n- ".join(erros)

    if not itens_validados:
        return None, "Nenhum doce valido foi informado."

    missing_required: list[str] = []
    for field_name in ("itens", "data_entrega", "modo_recebimento", "pagamento"):
        if _is_missing_field(dados.get(field_name)):
            missing_required.append(field_name)
    if str(dados.get("modo_recebimento") or "").strip().lower() == "entrega" and _is_missing_field(dados.get("endereco")):
        missing_required.append("endereco")
    if missing_required:
        return None, "Campos obrigatorios pendentes: " + ", ".join(sorted(set(missing_required))) + "."

    if dados["modo_recebimento"] == "entrega":
        if not dados.get("endereco"):
            return None, "Endereco e obrigatorio quando o modo de recebimento for entrega."
        if not _horario_entrega_permitido(dados.get("horario_retirada")):
            return None, (
                f"Entregas sao realizadas ate as {LIMITE_HORARIO_ENTREGA}. "
                "Ajuste o horario ou altere para retirada."
            )

    taxa_entrega = TAXA_ENTREGA_PADRAO if dados["modo_recebimento"] == "entrega" else 0.0
    valor_final = round(total_doces + taxa_entrega, 2)
    if valor_final <= 0:
        return None, "Valor total invalido. Revise os itens para gerar um total maior que R$0,00."
    dados["pagamento"] = _apply_card_installment_rule(dados.get("pagamento"), valor_final)
    data_iso = _normalizar_data_iso(dados["data_entrega"])
    desc_itens = ", ".join(f"{it['nome']} x{it['qtd']}" for it in itens_validados)
    order_data = {
        "categoria": "doces",
        "linha": "doces",
        "descricao": f"Doces Avulsos: {desc_itens}",
        "data_entrega": data_iso,
        "horario_retirada": dados.get("horario_retirada"),
        "modo_recebimento": dados["modo_recebimento"],
        "valor_total": valor_final,
        "quantidade": 1,
        "pagamento": dados.get("pagamento", {}),
        "taxa_entrega": taxa_entrega,
        "endereco": dados.get("endereco"),
    }
    return {
        "dados": dados,
        "itens_validados": itens_validados,
        "total_doces": total_doces,
        "taxa_entrega": taxa_entrega,
        "valor_final": valor_final,
        "data_iso": data_iso,
        "desc_itens": desc_itens,
        "order_data": order_data,
    }, None


# ============================================================
#  Schemas
# ============================================================

class PagamentoSchema(BaseModel):
    forma: Literal["PIX", "Cartão (débito/crédito)", "Dinheiro", "Pendente"] = Field(
        ..., description="Forma de pagamento escolhida"
    )
    troco_para: Optional[float] = Field(None, description="Valor para troco, se a forma for Dinheiro")
    parcelas: Optional[int] = Field(
        None,
        description="Parcelas no Cartao. So permitido acima de R$100,00 e no maximo 2x",
    )


class CakeOrderSchema(BaseModel):
    linha: str = Field(..., description="Linha do bolo. Ex: tradicional, gourmet, mesversario, babycake, torta, simples")
    categoria: str = Field(..., description="Categoria derivada da linha. Ex: tradicional, ingles, redondo, torta, mesversario, simples")
    produto: Optional[str] = Field(None, description="Nome do produto ou sabor. Na linha simples, use o sabor: Chocolate ou Cenoura")
    cobertura: Optional[str] = Field(None, description="Cobertura da linha simples: Vulcao ou Simples")
    tamanho: Optional[str] = Field(None, description="Tamanho: B3, B4, B6, B7, P4 ou P6")
    massa: Optional[str] = Field(None, description="Massa: Branca, Chocolate ou Mesclada (so para tradicional)")
    recheio: Optional[str] = Field(None, description="Recheio principal (so para tradicional/mesversario)")
    mousse: Optional[str] = Field(None, description="Mousse (so para tradicional, exceto recheio Casadinho)")
    adicional: Optional[str] = Field(None, description="Fruta ou nozes adicionais (so para tradicional)")
    descricao: str = Field(..., description="Descricao completa do bolo para o painel")
    kit_festou: bool = Field(False, description="Se adicionou kit festou (+R$35)")
    quantidade: int = Field(1, description="Quantidade do item")
    data_entrega: str = Field(..., description="Data de entrega no formato DD/MM/AAAA")
    horario_retirada: Optional[str] = Field(None, description="Horario de retirada/entrega HH:MM")
    modo_recebimento: Literal["retirada", "entrega"] = Field(..., description="retirada ou entrega")
    endereco: Optional[str] = Field(None, description="Endereco completo (obrigatorio se entrega)")
    taxa_entrega: float = Field(0.0, description="Taxa de entrega")
    pagamento: PagamentoSchema = Field(..., description="Dados de pagamento")


class SweetItemSchema(BaseModel):
    nome: str = Field(..., description="Nome do doce. Ex: Brigadeiro Escama, Bombom Camafeu")
    quantidade: int = Field(..., description="Quantidade do doce")


class SweetOrderSchema(BaseModel):
    itens: List[SweetItemSchema] = Field(..., description="Lista de doces com nome e quantidade")
    data_entrega: str = Field(..., description="Data de entrega no formato DD/MM/AAAA")
    horario_retirada: Optional[str] = Field(None, description="Horario de retirada/entrega HH:MM")
    modo_recebimento: Literal["retirada", "entrega"] = Field(..., description="retirada ou entrega")
    endereco: Optional[str] = Field(None, description="Endereco completo (obrigatorio se entrega)")
    pagamento: PagamentoSchema = Field(..., description="Dados de pagamento")


class CafeteriaOrderItemSchema(BaseModel):
    nome: str = Field(..., description="Nome base do item da cafeteria. Ex: Croissant, Coca Cola KS, Agua")
    variante: Optional[str] = Field(None, description="Sabor, versao ou opcao quando existir. Ex: Frango com requeijao, com gas")
    quantidade: int = Field(..., description="Quantidade do item")
    observacao: Optional[str] = Field(None, description="Observacao opcional do item")


class CafeteriaOrderSchema(BaseModel):
    itens: List[CafeteriaOrderItemSchema] = Field(..., description="Lista de itens da cafeteria com quantidade e variacoes")
    data_entrega: Optional[str] = Field(None, description="Data do atendimento no formato DD/MM/AAAA quando o cliente informar")
    horario_retirada: Optional[str] = Field(None, description="Horario de retirada/entrega HH:MM")
    modo_recebimento: Literal["retirada", "entrega"] = Field(..., description="retirada ou entrega")
    endereco: Optional[str] = Field(None, description="Endereco completo se for entrega")
    taxa_entrega: float = Field(0.0, description="Taxa de entrega, se aplicavel")
    pagamento: PagamentoSchema = Field(..., description="Dados de pagamento")


class GiftOrderSchema(BaseModel):
    categoria: Literal["cesta_box", "caixinha_chocolate", "flores"] = Field(
        ...,
        description="Categoria do presente regular. O fluxo automatico hoje so fecha cesta_box.",
    )
    produto: str = Field(..., description="Nome do presente ou da cesta box")
    descricao: Optional[str] = Field(None, description="Descricao opcional do item")
    data_entrega: str = Field(..., description="Data de entrega no formato DD/MM/AAAA")
    horario_retirada: Optional[str] = Field(None, description="Horario de retirada/entrega HH:MM")
    modo_recebimento: Literal["retirada", "entrega"] = Field(..., description="retirada ou entrega")
    endereco: Optional[str] = Field(None, description="Endereco completo se for entrega")
    taxa_entrega: float = Field(0.0, description="Taxa de entrega")
    pagamento: PagamentoSchema = Field(..., description="Dados de pagamento")


# ============================================================
#  Tools
# ============================================================

def get_menu(category: str = "todas") -> str:
    """Retorna o cardapio completo ou filtrado entre pronta entrega, encomendas, Pascoa e presentes regulares."""
    return get_catalog_gateway().get_menu(category)


def lookup_catalog_items(query: str, catalog: str = "auto") -> str:
    """Busca itens exatos ou aproximados no catalogo estruturado de cafeteria, Pascoa e presentes regulares."""
    return get_catalog_gateway().lookup_catalog_items(query, catalog)


def get_cake_pricing(
    category: str = "tradicional",
    tamanho: str | None = None,
    produto: str | None = None,
    adicional: str | None = None,
    cobertura: str | None = None,
    kit_festou: bool = False,
    quantidade: int = 1,
) -> str:
    """Retorna precos canonicos de bolos e tortas a partir da base estruturada do sistema."""
    normalized_category = _normalize_cake_pricing_category(category)
    try:
        normalized_quantity = max(1, int(quantidade or 1))
    except (TypeError, ValueError):
        normalized_quantity = 1

    if (
        not tamanho
        and not produto
        and not adicional
        and not cobertura
        and not kit_festou
        and normalized_quantity == 1
    ):
        return _build_cake_pricing_overview(normalized_category)

    payload, error = _build_cake_pricing_payload(
        category=normalized_category,
        tamanho=tamanho,
        produto=produto,
        adicional=adicional,
        cobertura=cobertura,
        kit_festou=kit_festou,
        quantidade=normalized_quantity,
    )
    if error:
        return error
    assert payload is not None

    total_price, serve_people = calcular_total(payload)
    unit_payload = dict(payload)
    unit_payload["quantidade"] = 1
    unit_price, _ = calcular_total(unit_payload)

    description = ""
    if normalized_category == "tradicional":
        description = f"Bolo tradicional {payload['tamanho']}"
        if adicional:
            matched_additional = _match_closest(adicional, set(ADICIONAIS_TRADICIONAIS)) or adicional
            description += f" com adicional {matched_additional}"
    elif normalized_category == "mesversario":
        description = f"Bolo mesversario {payload['tamanho']}"
    elif normalized_category == "ingles":
        description = f"Gourmet ingles {payload['produto']}"
    elif normalized_category == "redondo":
        description = f"Gourmet redondo P6 {payload['produto']}"
    elif normalized_category == "torta":
        description = f"Torta {payload['produto']}"
    elif normalized_category == "simples":
        flavor_label = payload.get("sabor") or "Chocolate"
        description = f"Bolo simples de {str(flavor_label).lower()} com cobertura {payload['cobertura']}"

    lines = [
        "Preco canonico consultado no sistema:",
        f"- Item: {description}",
        f"- Valor unitario: {_format_currency_brl(unit_price)}",
    ]
    if serve_people:
        lines.append(f"- Serve aproximadamente: {serve_people} pessoas")
    if kit_festou:
        lines.append(f"- Kit Festou incluido: +{_format_currency_brl(KIT_FESTOU_PRECO)} por unidade")
    if normalized_quantity > 1:
        lines.append(f"- Quantidade: {normalized_quantity}")
        lines.append(f"- Total calculado: {_format_currency_brl(total_price)}")
    else:
        lines.append(f"- Total calculado: {_format_currency_brl(total_price)}")
    lines.append("Use este valor como referencia oficial e nao invente preco fora deste retorno.")
    return "\n".join(lines)


def get_cake_options(category: str = "tradicional", option_type: str = "recheio") -> str:
    """Retorna a lista canonica de opcoes de bolo em formato pronto para resposta ao cliente."""
    normalized_category = _normalize_cake_option_category(category)
    normalized_option_type = _normalize_cake_option_type(option_type)
    values = CAKE_OPTION_VALUES.get((normalized_category, normalized_option_type))

    if not values:
        return (
            "Nao encontrei opcoes cadastradas para "
            f"{normalized_option_type} na categoria {normalized_category}."
        )

    label = CAKE_OPTION_LABELS.get(normalized_option_type, normalized_option_type)
    joined_values = _join_option_values(values)

    if normalized_category == "tradicional":
        if normalized_option_type == "recheio":
            return f"Temos estes recheios: {joined_values}. Se escolher Casadinho, nao precisa de mousse."
        if normalized_option_type == "mousse":
            return f"Temos estes mousses: {joined_values}."
        if normalized_option_type == "adicional":
            return f"Temos estes adicionais: {joined_values}."
        if normalized_option_type == "massa":
            return f"Temos estas massas: {joined_values}."
        if normalized_option_type == "tamanho":
            return f"Os tamanhos disponiveis para bolo tradicional sao: {joined_values}."

    if normalized_category == "mesversario":
        if normalized_option_type == "recheio":
            return f"Temos estes recheios para mesversario: {joined_values}."
        if normalized_option_type == "mousse":
            return "No mesversario, a troca opcional de mousse disponivel e Chocolate."
        if normalized_option_type == "massa":
            return f"As massas disponiveis para mesversario sao: {joined_values}."
        if normalized_option_type == "tamanho":
            return f"Os tamanhos disponiveis para mesversario sao: {joined_values}."

    return f"Temos estes {label}: {joined_values}."


def get_learnings() -> str:
    """Lê as instruções e regras aprendidas previamente pela IA."""
    return get_catalog_gateway().get_learnings()


def save_learning(aprendizado: str) -> str:
    """Salva uma nova regra de negócio, preferência do cliente ou correção aprendida para consultas futuras."""
    if not ai_learning_enabled():
        security_audit("ai_learning_blocked")
        return "Aprendizado persistente desativado neste ambiente."
    return get_catalog_gateway().save_learning(aprendizado)


def _sanitize_escalation_reason(motivo: str | None) -> str:
    raw_reason = " ".join(str(motivo or "").split()).strip()
    if not raw_reason:
        return "Cliente solicitou suporte humano; bot sem contexto suficiente para concluir com seguranca."

    normalized = _norm(raw_reason)
    generic_patterns = (
        r"\bfora de contexto\b",
        r"\bnao esta claro\b",
        r"\bnao entendi\b",
        r"\bduvida\b",
        r"\bcliente mencionou algo\b",
    )
    if len(raw_reason) < 20 or any(re.search(pattern, normalized) for pattern in generic_patterns):
        return (
            "Escalacao para humano com contexto obrigatorio: "
            f"{raw_reason}. Pedido requer validacao da equipe para concluir corretamente."
        )
    return raw_reason


def escalate_to_human(telefone: str, motivo: str):
    """Aciona o atendimento humano, pausando o bot para esse telefone."""
    reason = _sanitize_escalation_reason(motivo)
    return get_attention_gateway().activate_human_handoff(telefone=telefone, motivo=reason)


def create_cake_order(telefone: str, nome_cliente: str, cliente_id: int, order_details: CakeOrderSchema) -> str:
    """Valida, calcula preço e salva o pedido de bolo no banco de dados."""
    order_gateway = get_order_gateway()
    delivery_gateway = get_delivery_gateway()
    dados, error = _prepare_cake_order_data(order_details)
    if error:
        return error
    assert dados is not None

    # --- Salvar pedido ---
    encomenda_id = order_gateway.create_order(
        phone=telefone,
        dados=dados,
        nome_cliente=nome_cliente,
        cliente_id=cliente_id,
    )

    # --- Salvar entrega ---
    if dados["modo_recebimento"] == "entrega":
        delivery_gateway.create_delivery(
            encomenda_id=encomenda_id,
            tipo="entrega",
            data_agendada=dados["data_entrega"],
            status="pendente",
            endereco=dados.get("endereco"),
        )
    else:
        delivery_gateway.create_delivery(
            encomenda_id=encomenda_id,
            tipo="retirada",
            data_agendada=dados["data_entrega"],
            status="Retirar na loja",
        )

    _sync_ai_process(
        phone=telefone,
        customer_id=cliente_id,
        process_type="ai_cake_order",
        stage="pedido_confirmado",
        status="converted",
        source="ai_cake_order",
        draft_payload=_build_cake_process_payload(dados),
        order_id=encomenda_id,
    )

    preco_txt = f" | Valor: R${dados['valor_total']:.2f}" if dados.get("valor_total") else ""
    kit_flag = "sim" if bool(dados.get("kit_festou")) else "nao"
    return (
        f"Pedido salvo com sucesso! ID da Encomenda: {encomenda_id}{preco_txt}\n"
        f"Protocolo: CHK-{int(encomenda_id):06d}\n"
        f"Kit Festou incluido: {kit_flag}"
    )


def create_sweet_order(telefone: str, nome_cliente: str, cliente_id: int, order_details: SweetOrderSchema) -> str:
    """Valida, calcula preço e salva o pedido de doces avulsos no banco de dados."""
    order_gateway = get_order_gateway()
    delivery_gateway = get_delivery_gateway()
    prepared, error = _prepare_sweet_order_data(order_details)
    if error:
        return error
    assert prepared is not None
    dados = prepared["dados"]
    itens_validados = prepared["itens_validados"]
    total_doces = prepared["total_doces"]
    taxa_entrega = prepared["taxa_entrega"]
    valor_final = prepared["valor_final"]
    data_iso = prepared["data_iso"]
    desc_itens = prepared["desc_itens"]
    order_data = prepared["order_data"]

    encomenda_id = order_gateway.create_order(
        phone=telefone,
        dados=order_data,
        nome_cliente=nome_cliente,
        cliente_id=cliente_id,
    )

    # --- Salvar itens na tabela encomenda_doces ---
    try:
        conn = get_connection()
        cur = conn.cursor()
        for it in itens_validados:
            cur.execute(
                "INSERT INTO encomenda_doces (encomenda_id, nome, qtd, preco, unit) VALUES (?, ?, ?, ?, ?)",
                (encomenda_id, it["nome"], it["qtd"], it["preco"], it["unit"]),
            )
        conn.commit()
        conn.close()
    except Exception as exc:
        print(f"⚠️ Erro ao salvar itens de doces: {exc}")

    # --- Salvar entrega ---
    if dados["modo_recebimento"] == "entrega":
        delivery_gateway.create_delivery(
            encomenda_id=encomenda_id,
            tipo="entrega",
            data_agendada=data_iso,
            status="pendente",
            endereco=dados.get("endereco"),
        )
    else:
        delivery_gateway.create_delivery(
            encomenda_id=encomenda_id,
            tipo="retirada",
            data_agendada=data_iso,
            status="Retirar na loja",
        )

    _sync_ai_process(
        phone=telefone,
        customer_id=cliente_id,
        process_type="ai_sweet_order",
        stage="pedido_confirmado",
        status="converted",
        source="ai_sweet_order",
        draft_payload=_build_sweet_process_payload(
            data_entrega=data_iso,
            horario_retirada=dados.get("horario_retirada"),
            modo_recebimento=dados["modo_recebimento"],
            endereco=dados.get("endereco"),
            pagamento=dados.get("pagamento", {}),
            itens_validados=itens_validados,
            valor_total=valor_final,
        ),
        order_id=encomenda_id,
    )

    return (
        f"Pedido de doces salvo com sucesso! ID: {encomenda_id}\n"
        f"Itens: {desc_itens}\n"
        f"Total doces: R${total_doces:.2f}\n"
        + (f"Taxa entrega: R${taxa_entrega:.2f}\n" if taxa_entrega else "")
        + f"Total final: R${valor_final:.2f}\n"
        + f"Protocolo: CHK-{int(encomenda_id):06d}\n"
        + "Kit Festou incluido: nao"
    )


def create_cafeteria_order(
    telefone: str,
    nome_cliente: str,
    cliente_id: int,
    order_details: CafeteriaOrderSchema,
) -> str:
    """Valida itens da cafeteria e salva o pedido apenas apos confirmacao final explicita."""
    order_gateway = get_order_gateway()
    prepared, error = _prepare_cafeteria_order_data(order_details)
    if error:
        return error
    assert prepared is not None

    item_lines = [item["descricao"] for item in prepared["itens"]]
    order_gateway.save_cafeteria_order(
        phone=telefone,
        itens=item_lines,
        nome_cliente=nome_cliente,
    )
    _sync_ai_process(
        phone=telefone,
        customer_id=cliente_id,
        process_type="ai_cafeteria_order",
        stage="pedido_confirmado",
        status="converted",
        source="ai_cafeteria_order",
        draft_payload=_build_cafeteria_process_payload(
            itens=prepared["itens"],
            data_entrega=prepared.get("data_entrega"),
            horario_retirada=prepared.get("horario_retirada"),
            modo_recebimento=prepared["modo_recebimento"],
            endereco=prepared.get("endereco"),
            pagamento=prepared.get("pagamento", {}),
            valor_total=float(prepared["valor_total"]),
            taxa_entrega=float(prepared.get("taxa_entrega") or 0),
        ),
    )
    response_lines = [
        "Pedido cafeteria salvo com sucesso!",
        "Itens: " + ", ".join(item_lines),
        f"Subtotal: {_format_currency_brl(float(prepared['subtotal']))}",
        f"Protocolo: CAF-{telefone[-4:]}-{now_in_bot_timezone().strftime('%H%M')}",
        "Kit Festou incluido: nao",
    ]
    if float(prepared.get("taxa_entrega") or 0) > 0:
        response_lines.append(f"Taxa entrega: {_format_currency_brl(float(prepared['taxa_entrega']))}")
    response_lines.append(f"Total final: {_format_currency_brl(float(prepared['valor_total']))}")
    return "\n".join(response_lines)


def create_gift_order(
    telefone: str,
    nome_cliente: str,
    cliente_id: int,
    order_details: GiftOrderSchema,
) -> str:
    """Valida presentes regulares. Hoje o fechamento automatico e permitido apenas para cesta box."""
    order_gateway = get_order_gateway()
    delivery_gateway = get_delivery_gateway()
    dados, error = _prepare_gift_order_data(order_details)
    if error:
        return error
    assert dados is not None

    order_data = {
        "categoria": "cesta_box",
        "cesta_nome": dados["produto"],
        "cesta_preco": dados["valor_base"],
        "cesta_descricao": dados["descricao"],
        "data_entrega": dados["data_entrega"],
        "horario_retirada": dados.get("horario_retirada"),
        "modo_recebimento": dados["modo_recebimento"],
        "endereco": dados.get("endereco", ""),
        "valor_total": dados["valor_total"],
        "pagamento": dados.get("pagamento", {}),
        "taxa_entrega": dados.get("taxa_entrega", 0.0),
    }

    encomenda_id = order_gateway.create_order(
        phone=telefone,
        dados=order_data,
        nome_cliente=nome_cliente,
        cliente_id=cliente_id,
    )

    if dados["modo_recebimento"] == "entrega":
        delivery_gateway.create_delivery(
            encomenda_id=encomenda_id,
            tipo="cesta_box",
            endereco=dados.get("endereco"),
            data_agendada=dados["data_entrega"],
            status="agendada",
        )
    else:
        delivery_gateway.create_delivery(
            encomenda_id=encomenda_id,
            tipo="retirada",
            data_agendada=dados["data_entrega"],
            status="Retirar na loja",
        )

    _sync_ai_process(
        phone=telefone,
        customer_id=cliente_id,
        process_type="cesta_box_order",
        stage="pedido_confirmado",
        status="converted",
        source="ai_gift_order",
        draft_payload=_build_gift_process_payload(dados),
        order_id=encomenda_id,
    )
    fee_line = (
        f"Taxa entrega: {_format_currency_brl(float(dados.get('taxa_entrega') or 0))}\n"
        if float(dados.get("taxa_entrega") or 0) > 0
        else ""
    )
    return (
        f"Pedido presente salvo com sucesso! ID: {encomenda_id}\n"
        f"Item: {dados['produto']}\n"
        f"{fee_line}"
        f"Total final: {_format_currency_brl(float(dados['valor_total']))}\n"
        f"Protocolo: CHK-{int(encomenda_id):06d}\n"
        "Kit Festou incluido: nao"
    )


def save_cake_order_draft_process(
    telefone: str,
    nome_cliente: str,
    cliente_id: int,
    order_details: CakeOrderSchema,
) -> str:
    dados, error = _prepare_cake_order_data(order_details)
    if error:
        return error
    assert dados is not None
    _sync_ai_process(
        phone=telefone,
        customer_id=cliente_id,
        process_type="ai_cake_order",
        stage="aguardando_confirmacao",
        status="active",
        source="ai_cake_order",
        draft_payload=_build_cake_process_payload(dados),
    )
    return _build_draft_confirmation_message(
        title=_build_cake_confirmation_title(dados),
        flavor_line=_build_cake_flavor_line(dados),
        service_line=_build_service_line(dados),
        total_value=float(dados.get("valor_total") or 0),
        payment_line=_build_payment_line(dados.get("pagamento")),
        endereco=dados.get("endereco"),
        delivery_fee=float(dados.get("taxa_entrega") or 0),
        kit_festou=bool(dados.get("kit_festou")),
    )


def save_sweet_order_draft_process(
    telefone: str,
    nome_cliente: str,
    cliente_id: int,
    order_details: SweetOrderSchema,
) -> str:
    prepared, error = _prepare_sweet_order_data(order_details)
    if error:
        return error
    assert prepared is not None
    dados = prepared["dados"]
    _sync_ai_process(
        phone=telefone,
        customer_id=cliente_id,
        process_type="ai_sweet_order",
        stage="aguardando_confirmacao",
        status="active",
        source="ai_sweet_order",
        draft_payload=_build_sweet_process_payload(
            data_entrega=prepared["data_iso"],
            horario_retirada=dados.get("horario_retirada"),
            modo_recebimento=dados["modo_recebimento"],
            endereco=dados.get("endereco"),
            pagamento=dados.get("pagamento", {}),
            itens_validados=prepared["itens_validados"],
            valor_total=prepared["valor_final"],
        ),
    )
    return _build_draft_confirmation_message(
        title="Doces avulsos",
        flavor_line="Itens: " + ", ".join(f"{item['nome']} x{item['qtd']}" for item in prepared["itens_validados"]),
        service_line=_build_service_line(
            {
                "modo_recebimento": dados["modo_recebimento"],
                "data_entrega": prepared["data_iso"],
                "horario_retirada": dados.get("horario_retirada"),
            }
        ),
        total_value=float(prepared["valor_final"]),
        payment_line=_build_payment_line(dados.get("pagamento")),
        endereco=dados.get("endereco"),
        delivery_fee=float(prepared.get("taxa_entrega") or 0),
    )


def save_cafeteria_order_draft_process(
    telefone: str,
    nome_cliente: str,
    cliente_id: int,
    order_details: CafeteriaOrderSchema,
) -> str:
    prepared, error = _prepare_cafeteria_order_data(order_details)
    if error:
        return error
    assert prepared is not None
    _sync_ai_process(
        phone=telefone,
        customer_id=cliente_id,
        process_type="ai_cafeteria_order",
        stage="aguardando_confirmacao",
        status="active",
        source="ai_cafeteria_order",
        draft_payload=_build_cafeteria_process_payload(
            itens=prepared["itens"],
            data_entrega=prepared.get("data_entrega"),
            horario_retirada=prepared.get("horario_retirada"),
            modo_recebimento=prepared["modo_recebimento"],
            endereco=prepared.get("endereco"),
            pagamento=prepared.get("pagamento", {}),
            valor_total=float(prepared["valor_total"]),
            taxa_entrega=float(prepared.get("taxa_entrega") or 0),
        ),
    )
    return _build_cafeteria_confirmation_message(prepared)


def save_gift_order_draft_process(
    telefone: str,
    nome_cliente: str,
    cliente_id: int,
    order_details: GiftOrderSchema,
) -> str:
    dados, error = _prepare_gift_order_data(order_details)
    if error:
        return error
    assert dados is not None
    _sync_ai_process(
        phone=telefone,
        customer_id=cliente_id,
        process_type="cesta_box_order",
        stage="aguardando_confirmacao",
        status="active",
        source="ai_gift_order",
        draft_payload=_build_gift_process_payload(dados),
    )
    return _build_draft_confirmation_message(
        title=dados["produto"],
        flavor_line=_build_gift_detail_line(dados),
        service_line=_build_service_line(dados),
        total_value=float(dados["valor_total"]),
        payment_line=_build_payment_line(dados.get("pagamento")),
        endereco=dados.get("endereco"),
        delivery_fee=float(dados.get("taxa_entrega") or 0),
    )
