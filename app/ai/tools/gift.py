"""Gift-domain helpers: cestas box, caixinhas de chocolate e flores.

create_gift_order / save_gift_order_draft_process continuam em
``app/ai/tools/__init__.py`` enquanto os helpers de orquestração
ainda vivem lá.
"""
from __future__ import annotations

from app.ai.tools._common import (
    _apply_card_installment_rule,
    _is_missing_field,
    _normalize_payment_data,
    _normalize_text,
    _normalizar_data_iso,
    _validate_cash_change_requirement,
    _validate_required_payment_data,
)
from app.application.use_cases.process_cesta_box_flow import CESTAS_BOX_CATALOGO
from app.services.commercial_rules import DELIVERY_FEE_STANDARD
from app.services.encomendas_utils import LIMITE_HORARIO_ENTREGA, _horario_entrega_permitido
from app.services.store_schedule import validate_service_schedule


TAXA_ENTREGA_PADRAO = DELIVERY_FEE_STANDARD


GIFT_CATEGORY_ALIASES = {
    "cesta box": "cesta_box",
    "cestas box": "cesta_box",
    "cesta": "cesta_box",
    "cestas": "cesta_box",
    "caixinha de chocolate": "caixinha_chocolate",
    "caixa de chocolate": "caixinha_chocolate",
    "flores": "flores",
}


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


def _prepare_gift_order_data(order_details) -> tuple[dict | None, str | None]:
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
