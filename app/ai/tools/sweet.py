"""Sweet-domain helpers: validação e payload de pedidos de doces avulsos.

create_sweet_order / save_sweet_order_draft_process continuam em
``app/ai/tools/__init__.py`` enquanto os helpers de orquestração
(_persist_order_with_optional_bundle, _sync_ai_process,
_build_draft_confirmation_message) ainda vivem lá.
"""
from __future__ import annotations

from typing import Dict, List

from app.ai.tools._common import (
    _apply_card_installment_rule,
    _is_missing_field,
    _normalize_payment_data,
    _normalizar_data_iso,
    _validate_cash_change_requirement,
    _validate_required_payment_data,
)
from app.services.commercial_rules import DELIVERY_FEE_STANDARD
from app.services.encomendas_utils import LIMITE_HORARIO_ENTREGA, _horario_entrega_permitido
from app.services.precos import DOCES_UNITARIOS, _canonical_doce
from app.services.store_schedule import validate_service_schedule


TAXA_ENTREGA_PADRAO = DELIVERY_FEE_STANDARD


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


def _prepare_sweet_order_data(order_details) -> tuple[dict | None, str | None]:
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
