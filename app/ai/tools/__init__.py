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
# Cake constants moved to app/ai/tools/cake.py — re-imported abaixo.

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
# ============================================================
#  Helpers genéricos (extraídos para app/ai/tools/_common.py)
# ============================================================
from app.ai.tools._common import (
    _apply_card_installment_rule,
    _format_compact_hour,
    _format_currency_brl,
    _is_missing_field,
    _join_option_values,
    _match_catalog_value,
    _match_closest,
    _normalize_payment_data,
    _normalizar_data_iso,
    _parse_order_date_label,
    _resolve_pix_key,
    _today_service_date_str,
    _validate_cash_change_requirement,
    _validate_required_payment_data,
)


# Cake helpers/constants/tools moved to app/ai/tools/cake.py.
from app.ai.tools.cake import (
    ADICIONAIS_TRADICIONAIS,
    CAKE_OPTION_LABELS,
    CAKE_OPTION_VALUES,
    CATEGORIAS_VALIDAS,
    LINE_SIMPLE_COVERAGES,
    LINE_SIMPLE_FLAVORS,
    LINHAS_VALIDAS,
    MASSA_SINONIMOS,
    MASSAS_MESVERSARIO,
    MASSAS_TRADICIONAIS,
    MASSAS_VALIDAS,
    MOUSSES_TRADICIONAIS,
    MOUSSES_VALIDOS,
    RECHEIOS_MESVERSARIO,
    RECHEIOS_TRADICIONAIS,
    RECHEIOS_VALIDOS,
    TAMANHOS_BOLO,
    TAMANHOS_MESVERSARIO,
    TAMANHOS_TRADICIONAIS,
    TAXA_ENTREGA_PADRAO,
    _build_cake_confirmation_title,
    _build_cake_flavor_line,
    _build_cake_pricing_overview,
    _build_cake_pricing_payload,
    _build_cake_process_payload,
    _calcular_preco_pedido,
    _extract_simple_cake_details,
    _normalize_cake_option_category,
    _normalize_cake_option_type,
    _normalize_cake_pricing_category,
    _normalize_simple_cake_coverage,
    _normalize_simple_cake_flavor,
    _normalizar_massa,
    _prepare_cake_order_data,
    _validar_campos_bolo,
    _validate_required_cake_fields,
    get_cake_options,
    get_cake_pricing,
)


def _canonical_cafeteria_name(name: str | None) -> str:
    raw = (name or "").strip()
    if raw == "Combo Relampago":
        return CHOCO_COMBO_CANONICAL_NAME
    return raw


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
    pix_key = _resolve_pix_key()
    if method.casefold() == "pix" and pix_key:
        details.append(f"chave {pix_key}")
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


def _persist_order_with_optional_bundle(
    *,
    order_gateway,
    phone: str,
    dados: dict,
    nome_cliente: str,
    cliente_id: int,
    delivery_data: dict | None = None,
    process_data: dict | None = None,
    sweet_items: list[dict] | None = None,
) -> int:
    if hasattr(order_gateway, "create_order_bundle"):
        return order_gateway.create_order_bundle(
            phone=phone,
            dados=dados,
            nome_cliente=nome_cliente,
            cliente_id=cliente_id,
            delivery_data=delivery_data,
            process_data=process_data,
            sweet_items=sweet_items,
        )
    return order_gateway.create_order(
        phone=phone,
        dados=dados,
        nome_cliente=nome_cliente,
        cliente_id=cliente_id,
    )


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
#  Schemas (extraídas para app/ai/tools/_schemas.py)
# ============================================================
from app.ai.tools._schemas import (
    CafeteriaOrderItemSchema,
    CafeteriaOrderSchema,
    CakeOrderSchema,
    GiftOrderSchema,
    PagamentoSchema,
    SweetItemSchema,
    SweetOrderSchema,
)


# ============================================================
#  Tools
# ============================================================

def get_menu(category: str = "todas") -> str:
    """Retorna o cardapio completo ou filtrado entre pronta entrega, encomendas, Pascoa e presentes regulares."""
    return get_catalog_gateway().get_menu(category)


def lookup_catalog_items(query: str, catalog: str = "auto") -> str:
    """Busca itens exatos ou aproximados no catalogo estruturado de cafeteria, Pascoa e presentes regulares."""
    return get_catalog_gateway().lookup_catalog_items(query, catalog)


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

    delivery_payload = (
        {
            "tipo": "entrega",
            "data_agendada": dados["data_entrega"],
            "status": "pendente",
            "endereco": dados.get("endereco"),
        }
        if dados["modo_recebimento"] == "entrega"
        else {
            "tipo": "retirada",
            "data_agendada": dados["data_entrega"],
            "status": "Retirar na loja",
        }
    )
    process_payload = {
        "process_type": "ai_cake_order",
        "stage": "pedido_confirmado",
        "status": "converted",
        "source": "ai_cake_order",
        "draft_payload": _build_cake_process_payload(dados),
    }
    encomenda_id = _persist_order_with_optional_bundle(
        order_gateway=order_gateway,
        phone=telefone,
        dados=dados,
        nome_cliente=nome_cliente,
        cliente_id=cliente_id,
        delivery_data=delivery_payload,
        process_data=process_payload,
    )
    if encomenda_id <= 0:
        return "Erro interno ao salvar pedido. Tente novamente em instantes."

    if not hasattr(order_gateway, "create_order_bundle"):
        delivery_gateway.create_delivery(
            encomenda_id=encomenda_id,
            **delivery_payload,
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

    delivery_payload = (
        {
            "tipo": "entrega",
            "data_agendada": data_iso,
            "status": "pendente",
            "endereco": dados.get("endereco"),
        }
        if dados["modo_recebimento"] == "entrega"
        else {
            "tipo": "retirada",
            "data_agendada": data_iso,
            "status": "Retirar na loja",
        }
    )
    process_payload = {
        "process_type": "ai_sweet_order",
        "stage": "pedido_confirmado",
        "status": "converted",
        "source": "ai_sweet_order",
        "draft_payload": _build_sweet_process_payload(
            data_entrega=data_iso,
            horario_retirada=dados.get("horario_retirada"),
            modo_recebimento=dados["modo_recebimento"],
            endereco=dados.get("endereco"),
            pagamento=dados.get("pagamento", {}),
            itens_validados=itens_validados,
            valor_total=valor_final,
        ),
    }
    sweet_items = [
        {
            "nome": it["nome"],
            "qtd": it["qtd"],
            "preco": it["preco"],
            "unit": it["unit"],
        }
        for it in itens_validados
    ]
    encomenda_id = _persist_order_with_optional_bundle(
        order_gateway=order_gateway,
        phone=telefone,
        dados=order_data,
        nome_cliente=nome_cliente,
        cliente_id=cliente_id,
        delivery_data=delivery_payload,
        process_data=process_payload,
        sweet_items=sweet_items,
    )
    if encomenda_id <= 0:
        return "Erro interno ao salvar pedido de doces. Tente novamente em instantes."

    if not hasattr(order_gateway, "create_order_bundle"):
        conn = get_connection()
        try:
            cur = conn.cursor()
            for item in sweet_items:
                cur.execute(
                    "INSERT INTO encomenda_doces (encomenda_id, nome, qtd, preco, unit) VALUES (?, ?, ?, ?, ?)",
                    (encomenda_id, item["nome"], item["qtd"], item["preco"], item["unit"]),
                )
            conn.commit()
        finally:
            conn.close()
        delivery_gateway.create_delivery(
            encomenda_id=encomenda_id,
            **delivery_payload,
        )
        _sync_ai_process(
            phone=telefone,
            customer_id=cliente_id,
            process_type="ai_sweet_order",
            stage="pedido_confirmado",
            status="converted",
            source="ai_sweet_order",
            draft_payload=process_payload["draft_payload"],
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

    delivery_payload = (
        {
            "tipo": "cesta_box",
            "endereco": dados.get("endereco"),
            "data_agendada": dados["data_entrega"],
            "status": "agendada",
        }
        if dados["modo_recebimento"] == "entrega"
        else {
            "tipo": "retirada",
            "data_agendada": dados["data_entrega"],
            "status": "Retirar na loja",
        }
    )
    process_payload = {
        "process_type": "cesta_box_order",
        "stage": "pedido_confirmado",
        "status": "converted",
        "source": "ai_gift_order",
        "draft_payload": _build_gift_process_payload(dados),
    }
    encomenda_id = _persist_order_with_optional_bundle(
        order_gateway=order_gateway,
        phone=telefone,
        dados=order_data,
        nome_cliente=nome_cliente,
        cliente_id=cliente_id,
        delivery_data=delivery_payload,
        process_data=process_payload,
    )
    if encomenda_id <= 0:
        return "Erro interno ao salvar pedido de presente. Tente novamente em instantes."

    if not hasattr(order_gateway, "create_order_bundle"):
        delivery_gateway.create_delivery(
            encomenda_id=encomenda_id,
            **delivery_payload,
        )
        _sync_ai_process(
            phone=telefone,
            customer_id=cliente_id,
            process_type="cesta_box_order",
            stage="pedido_confirmado",
            status="converted",
            source="ai_gift_order",
            draft_payload=process_payload["draft_payload"],
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
