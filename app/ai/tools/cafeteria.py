"""Cafeteria-domain helpers, catálogo e payload de pedidos da cafeteria.

create_cafeteria_order / save_cafeteria_order_draft_process continuam em
``app/ai/tools/__init__.py`` enquanto os helpers de orquestração
(_persist_order_with_optional_bundle, _sync_ai_process) ainda vivem lá.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.ai.tools._common import (
    _apply_card_installment_rule,
    _build_payment_line,
    _format_compact_hour,
    _format_currency_brl,
    _match_catalog_value,
    _normalize_payment_data,
    _normalize_text,
    _parse_order_date_label,
    _today_service_date_str,
    _validate_cash_change_requirement,
    _validate_required_payment_data,
)
from app.services.commercial_rules import DELIVERY_FEE_CAFETERIA
from app.services.encomendas_utils import LIMITE_HORARIO_ENTREGA, _horario_entrega_permitido
from app.services.store_schedule import (
    format_service_date_with_weekday,
    parse_service_date,
    validate_service_schedule,
)


TAXA_ENTREGA_CAFETERIA = DELIVERY_FEE_CAFETERIA
CAFETERIA_CATALOG_PATH = Path("app/ai/knowledge/catalogo_produtos.json")
CHOCO_COMBO_CANONICAL_NAME = "Choko Combo (Combo do Dia)"

CAFETERIA_VARIANT_REQUIRED_HINTS = {
    "Croissant": "Informe o sabor do croissant e a quantidade.",
    "Combo Relampago": "No Choko Combo (Combo do Dia), escolha a bebida: Suco natural ou Refri 220ml.",
    "Agua": "Informe se deseja agua com gas ou sem gas, e a quantidade.",
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


def _canonical_cafeteria_name(name: str | None) -> str:
    raw = (name or "").strip()
    if raw == "Combo Relampago":
        return CHOCO_COMBO_CANONICAL_NAME
    return raw


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


def _prepare_cafeteria_order_data(order_details) -> tuple[dict | None, str | None]:
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
