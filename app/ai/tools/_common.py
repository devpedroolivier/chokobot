"""Helpers genéricos compartilhados entre as tools de pedido.

Funções aqui não devem depender de submódulos específicos de domínio
(cake/sweet/gift/cafeteria) — só de utilitários globais e settings.
"""
from __future__ import annotations

import re
from datetime import datetime

from app.infrastructure.gateways.local_catalog_gateway import _normalize_text
from app.services.commercial_rules import CARD_INSTALLMENT_MAX, CARD_INSTALLMENT_MIN_TOTAL
from app.services.precos import _norm
from app.services.store_schedule import format_service_date
from app.settings import get_settings
from app.utils.datetime_utils import now_in_bot_timezone


def _resolve_pix_key() -> str:
    return (get_settings().pix_key or "").strip()


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


def _join_option_values(values: tuple[str, ...]) -> str:
    if not values:
        return ""
    if len(values) == 1:
        return values[0]
    return ", ".join(values[:-1]) + f" e {values[-1]}"


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


def _validate_required_payment_data(pagamento: dict | None) -> str | None:
    payment = dict(pagamento or {})
    method = str(payment.get("forma") or "").strip()
    if not method or method == "Pendente":
        return "Forma de pagamento obrigatoria: PIX, Cartão (débito/crédito) ou Dinheiro."
    return None


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


def _today_service_date_str() -> str:
    return format_service_date(now_in_bot_timezone().date()) or ""


# ============================================================
#  Confirmation builders (compartilhados por todas as domains)
# ============================================================

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


# Re-exports — algumas tools podem precisar do helper bruto
__all__ = [
    "_apply_card_installment_rule",
    "_build_draft_confirmation_message",
    "_build_payment_line",
    "_build_service_line",
    "_format_compact_hour",
    "_format_currency_brl",
    "_is_missing_field",
    "_join_option_values",
    "_match_catalog_value",
    "_match_closest",
    "_normalize_payment_data",
    "_normalize_text",
    "_normalizar_data_iso",
    "_parse_order_date_label",
    "_resolve_pix_key",
    "_today_service_date_str",
    "_validate_cash_change_requirement",
    "_validate_required_payment_data",
]
