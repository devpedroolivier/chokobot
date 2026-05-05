"""Public tools surface for the AI agent.

Domain logic was split into:
    - app/ai/tools/_common.py     (shared helpers + confirmation builders)
    - app/ai/tools/_schemas.py    (Pydantic schemas)
    - app/ai/tools/cake.py        (cake constants, pricing, validations)
    - app/ai/tools/sweet.py       (sweet validations)
    - app/ai/tools/gift.py        (gift box helpers + cesta_box catalog)
    - app/ai/tools/cafeteria.py   (cafeteria catalog + validations)

This module keeps the orchestration layer (create_*_order /
save_*_draft_process tools) and the catalog/learning/escalate tools.
"""
import re
from datetime import datetime, timedelta

from app.application.service_registry import (
    get_attention_gateway,
    get_catalog_gateway,
    get_customer_process_repository,
    get_delivery_gateway,
    get_order_gateway,
)
from app.observability import increment_counter, log_event
from app.security import ai_learning_enabled, security_audit
from app.services.precos import _norm
from app.utils.datetime_utils import normalize_to_bot_timezone, now_in_bot_timezone

# ============================================================
#  Helpers genéricos (extraídos para app/ai/tools/_common.py)
# ============================================================
from app.ai.tools._common import (
    _apply_card_installment_rule,
    _build_draft_confirmation_message,
    _build_payment_line,
    _build_service_line,
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


# ============================================================
#  Cafeteria helpers/constants extraídos para app/ai/tools/cafeteria.py.
# ============================================================
from app.ai.tools.cafeteria import (
    CAFETERIA_CATALOG_PATH,
    CAFETERIA_ITEM_KEYWORDS,
    CAFETERIA_NAME_ALIASES,
    CAFETERIA_VARIANT_REQUIRED_HINTS,
    CHOCO_COMBO_CANONICAL_NAME,
    COMBO_RELAMPAGO_OPTION_ALIASES,
    TAXA_ENTREGA_CAFETERIA,
    _build_cafeteria_confirmation_message,
    _build_cafeteria_process_payload,
    _cafeteria_item_merge_key,
    _cafeteria_search_blob,
    _canonical_cafeteria_name,
    _candidate_cafeteria_items,
    _format_cafeteria_item_label,
    _infer_combo_relampago_option,
    _load_cafeteria_catalog_items,
    _merge_cafeteria_validated_items,
    _prepare_cafeteria_order_data,
    _resolve_cafeteria_item,
    _validate_cafeteria_item_availability,
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


# Gift helpers/constants extraídos para app/ai/tools/gift.py.
from app.ai.tools.gift import (
    GIFT_CATEGORY_ALIASES,
    _build_gift_detail_line,
    _build_gift_process_payload,
    _canonical_cesta_box,
    _normalize_gift_category,
    _prepare_gift_order_data,
)


_REPEAT_ORDER_WINDOW = timedelta(minutes=30)


def _detect_repeat_confirmed_order(
    *,
    phone: str,
    process_type: str,
    now: datetime,
) -> bool:
    """Sinaliza quando um cliente confirma um 2º pedido em <30min.

    Não bloqueia o fluxo — apenas emite métrica/log para que a equipe
    consiga detectar pedidos que poderiam virar carrinho unificado.
    Real auto-merge fica para um próximo ciclo (ver task #11).
    """
    repository = get_customer_process_repository()
    getter = getattr(repository, "get_process", None)
    if not callable(getter):
        return False
    try:
        existing = getter(phone, process_type)
    except Exception:
        return False
    if existing is None:
        return False
    if existing.stage != "pedido_confirmado":
        return False
    last_at_raw = existing.updated_at or existing.created_at
    if not last_at_raw:
        return False
    try:
        last_at = normalize_to_bot_timezone(datetime.fromisoformat(last_at_raw))
    except Exception:
        return False
    return (now - last_at) <= _REPEAT_ORDER_WINDOW


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
    if stage == "pedido_confirmado" and process_type == "ai_cafeteria_order":
        now = normalize_to_bot_timezone(now_in_bot_timezone())
        if _detect_repeat_confirmed_order(
            phone=phone, process_type=process_type, now=now
        ):
            increment_counter("cafeteria_repeat_order_total")
            log_event(
                "cafeteria_repeat_confirmed_order_detected",
                level="WARNING",
                phone_suffix=str(phone)[-4:],
                window_minutes=int(_REPEAT_ORDER_WINDOW.total_seconds() // 60),
            )
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


# ============================================================
#  Sweet helpers (extraídos para app/ai/tools/sweet.py)
# ============================================================
from app.ai.tools.sweet import _build_sweet_process_payload, _prepare_sweet_order_data


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
    """Retorna o cardapio completo ou filtrado entre pronta entrega, encomendas e presentes regulares."""
    return get_catalog_gateway().get_menu(category)


def lookup_catalog_items(query: str, catalog: str = "auto") -> str:
    """Busca itens exatos ou aproximados no catalogo estruturado de cafeteria e presentes regulares."""
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
