from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.domain.repositories.customer_process_repository import CustomerProcessRepository
from app.domain.repositories.customer_repository import CustomerRepository
from app.domain.repositories.order_repository import OrderPanelItem
from app.observability import snapshot_metrics
from app.services.estados import (
    ai_sessions,
    estados_atendimento,
    estados_cafeteria,
    estados_cestas_box,
    estados_encomenda,
    estados_entrega,
    recent_messages,
)
from app.settings import get_settings

_CATEGORY_LABELS = {
    "tradicional": "Bolos Tradicionais",
    "ingles": "Gourmet Inglês",
    "redondo": "Gourmet Redondo",
    "torta": "Tortas",
    "simples": "Linha Simples",
    "cesta_box": "Cestas Box",
}

_STATUS_META = {
    "pendente": {"label": "Pendente", "badge_class": "badge badge-pending", "sort": 1},
    "em_preparo": {"label": "Em preparo", "badge_class": "badge badge-progress", "sort": 2},
    "agendada": {"label": "Agendada", "badge_class": "badge badge-scheduled", "sort": 3},
    "retirada": {"label": "Retirada na loja", "badge_class": "badge badge-pickup", "sort": 4},
    "entregue": {"label": "Entregue", "badge_class": "badge badge-done", "sort": 5},
}

_TYPE_META = {
    "entrega": "Entrega",
    "retirada": "Retirada",
    "cesta_box": "Cesta Box",
}

_TEST_NAME_TOKENS = ("teste", "suporte", "pessoal")
_WHATSAPP_STAGE_META = {
    "CakeOrderAgent": ("Pedido de bolo", "stage-cake"),
    "SweetOrderAgent": ("Pedido de doces", "stage-sweet"),
    "CafeteriaAgent": ("Pedido cafeteria", "stage-cafe"),
    "estados_encomenda": ("Fluxo de encomenda", "stage-cake"),
    "estados_cafeteria": ("Fluxo cafeteria", "stage-cafe"),
    "estados_cestas_box": ("Cesta box", "stage-gift"),
    "estados_entrega": ("Entrega / endereço", "stage-delivery"),
    "estados_atendimento": ("Aguardando humano", "stage-human"),
}
_PROCESS_STAGE_META = {
    "montando_pedido": {
        "label": "Montando pedido",
        "class": "stage-cafe",
        "priority": 4,
        "action_label": "Acompanhar conversa",
    },
    "coletando_dados": {
        "label": "Coletando dados",
        "class": "stage-gift",
        "priority": 3,
        "action_label": "Completar dados",
    },
    "coletando_endereco": {
        "label": "Coletando endereco",
        "class": "stage-delivery",
        "priority": 2,
        "action_label": "Completar dados",
    },
    "aguardando_confirmacao": {
        "label": "Aguardando confirmacao",
        "class": "stage-cake",
        "priority": 1,
        "action_label": "Pronto para fechar",
    },
    "pagamento_pendente": {
        "label": "Pagamento pendente",
        "class": "stage-sweet",
        "priority": 1,
        "action_label": "Cobrar pagamento",
    },
    "pedido_confirmado": {
        "label": "Pedido confirmado",
        "class": "stage-gift",
        "priority": 3,
        "action_label": "Convertido",
    },
}
_PROCESS_TYPE_META = {
    "delivery_order": "Entrega em montagem",
    "cafeteria_order": "Pedido cafeteria",
    "cesta_box_order": "Cesta box",
    "ai_cake_order": "Bolo IA aguardando confirmacao",
    "ai_sweet_order": "Doces IA aguardando confirmacao",
}

_PROCESS_ORIGIN_META = {
    "ai": {"label": "Rascunho IA", "class": "stage-sweet"},
    "manual": {"label": "Atendimento", "class": "stage-cafe"},
}
_PROCESS_OWNER_META = {
    "cliente": {"label": "Ação do cliente", "class": "stage-cake"},
    "bot": {"label": "Ação do bot", "class": "stage-delivery"},
    "humano": {"label": "Ação humana", "class": "stage-human"},
}


def current_business_date() -> date:
    timezone_name = get_settings().bot_timezone or get_settings().tz or "America/Sao_Paulo"
    try:
        timezone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        timezone = ZoneInfo("America/Sao_Paulo")
    return datetime.now(timezone).date()


def current_business_datetime() -> datetime:
    timezone_name = get_settings().bot_timezone or get_settings().tz or "America/Sao_Paulo"
    try:
        timezone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        timezone = ZoneInfo("America/Sao_Paulo")
    return datetime.now(timezone)


def parse_order_date(raw_value: str | None) -> date | None:
    value = (raw_value or "").strip()
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def parse_created_date(raw_value: str | None) -> date | None:
    value = (raw_value or "").strip()
    if not value:
        return None
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def normalize_status(raw_status: str | None, raw_type: str | None) -> str:
    status = (raw_status or "").strip().casefold()
    tipo = (raw_type or "").strip().casefold()

    if status == "entregue":
        return "entregue"
    if status in {"em preparo", "em_preparo"}:
        return "em_preparo"
    if status == "agendada":
        return "agendada"
    if "retir" in status or "retir" in tipo:
        return "retirada"
    return "pendente"


def _normalize_type(raw_type: str | None, status_slug: str) -> str:
    tipo = (raw_type or "").strip().casefold()
    if "cesta" in tipo:
        return "cesta_box"
    if "retir" in tipo or status_slug == "retirada":
        return "retirada"
    return "entrega"


def _safe_float(value) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _format_currency(value: float) -> str:
    formatted = f"{value:,.2f}"
    return "R$ " + formatted.replace(",", "X").replace(".", ",").replace("X", ".")


def _format_compact_date(value: date | None) -> str:
    if value is None:
        return "Sem data"
    return value.strftime("%d/%m")


def _format_full_date(value: date | None, raw_value: str | None) -> str:
    if value is None:
        return (raw_value or "Sem data").strip() or "Sem data"
    return value.strftime("%d/%m/%Y")


def _format_category(category: str | None) -> str:
    slug = (category or "").strip().lower()
    return _CATEGORY_LABELS.get(slug, (category or "Sem categoria").replace("_", " ").title())


def _looks_like_test_customer(name: str | None) -> bool:
    normalized = (name or "").casefold()
    return any(token in normalized for token in _TEST_NAME_TOKENS)


def _parse_runtime_timestamp(raw_value: str | None) -> datetime | None:
    value = (raw_value or "").strip()
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _latest_user_message(session: dict | None) -> str:
    for message in reversed((session or {}).get("messages", [])):
        if message.get("role") == "user" and message.get("content"):
            return str(message["content"])
    return ""


def _format_last_seen(value: datetime | None, *, now: datetime) -> str:
    if value is None:
        return "Sem horário"
    same_day = value.date() == now.date()
    return value.strftime("%H:%M" if same_day else "%d/%m %H:%M")


def _parse_process_timestamp(raw_value: str | None) -> datetime | None:
    value = (raw_value or "").strip()
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return _parse_runtime_timestamp(value)


def _build_process_summary(payload: dict) -> str:
    category = _format_category(payload.get("categoria"))
    if payload.get("itens"):
        product = ", ".join(str(item) for item in payload.get("itens") if item)
    else:
        product = (payload.get("cesta_nome") or payload.get("produto") or payload.get("descricao") or category).strip()
    parts = [product]
    if payload.get("data_entrega"):
        parts.append(_format_full_date(parse_order_date(payload.get("data_entrega")), payload.get("data_entrega")))
    if payload.get("horario_retirada") or payload.get("horario"):
        parts.append((payload.get("horario_retirada") or payload.get("horario") or "").strip())
    return " • ".join(part for part in parts if part) or category


def _process_missing_items(process_type: str, stage: str, payload: dict) -> list[str]:
    missing: list[str] = []

    if process_type == "cafeteria_order":
        if not payload.get("itens") and not payload.get("descricao"):
            missing.append("Itens")
        if stage == "montando_pedido":
            missing.append("Finalizacao do pedido")
        return missing

    if process_type == "cesta_box_order":
        if not payload.get("cesta_nome") and not payload.get("descricao"):
            missing.append("Cesta")
        if not (payload.get("modo_recebimento") or "").strip():
            missing.append("Modo de recebimento")

    if not (payload.get("data_entrega") or payload.get("data")):
        missing.append("Data")
    if not (payload.get("horario_retirada") or payload.get("horario")):
        missing.append("Horario")

    payment = payload.get("pagamento") or {}
    payment_method = (payment.get("forma") or payload.get("forma_pagamento") or "").strip()
    if not payment_method or payment_method.casefold() == "pendente":
        missing.append("Pagamento")

    if process_type in {"delivery_order", "cesta_box_order", "ai_cake_order", "ai_sweet_order"} and (
        (payload.get("modo_recebimento") or "entrega").strip().casefold() == "entrega"
        and not (payload.get("endereco") or "").strip()
    ):
        missing.append("Endereco")

    if stage == "aguardando_confirmacao" and not missing:
        missing.append("Confirmacao final")

    return missing


def _resolve_process_owner(process_type: str, stage: str, missing_items: list[str]) -> tuple[str, str]:
    if stage in {"aguardando_confirmacao", "pagamento_pendente"}:
        if stage == "pagamento_pendente":
            return "cliente", "Cobrar pagamento e comprovante"
        return "cliente", "Cobrar confirmacao final"

    if process_type.startswith("ai_"):
        return "bot", "Continuar coleta pelo WhatsApp"

    if stage in {"coletando_endereco", "coletando_dados", "montando_pedido"}:
        if missing_items:
            return "humano", "Completar dados faltantes"
        return "humano", "Revisar atendimento"

    return "humano", "Revisar processo"


def build_process_cards(
    process_repository: CustomerProcessRepository,
    customer_repository: CustomerRepository,
    *,
    now: datetime | None = None,
) -> list[dict]:
    reference = now or current_business_datetime()
    cards: list[dict] = []

    for process in process_repository.list_active_processes():
        customer = customer_repository.get_customer_by_phone(process.phone)
        customer_name = customer.nome if customer else process.phone
        if _looks_like_test_customer(customer_name):
            continue

        updated_at = _parse_process_timestamp(process.updated_at)
        if updated_at is not None and updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=reference.tzinfo)

        stage_meta = _PROCESS_STAGE_META.get(
            process.stage,
            {
                "label": process.stage.replace("_", " ").title(),
                "class": "stage-human",
                "priority": 9,
                "action_label": "Revisar processo",
            },
        )
        missing_items = _process_missing_items(process.process_type, process.stage, process.draft_payload)
        origin_slug = "ai" if process.process_type.startswith("ai_") else "manual"
        origin_meta = _PROCESS_ORIGIN_META[origin_slug]
        owner_slug, owner_hint = _resolve_process_owner(process.process_type, process.stage, missing_items)
        owner_meta = _PROCESS_OWNER_META[owner_slug]
        cards.append(
            {
                "process_id": process.id,
                "order_id": process.order_id,
                "phone": process.phone,
                "cliente_nome": customer_name,
                "process_label": _PROCESS_TYPE_META.get(
                    process.process_type,
                    process.process_type.replace("_", " ").title(),
                ),
                "stage_label": stage_meta["label"],
                "stage_class": stage_meta["class"],
                "priority_rank": stage_meta["priority"],
                "action_label": stage_meta["action_label"],
                "summary": _build_process_summary(process.draft_payload),
                "missing_items": missing_items,
                "missing_summary": ", ".join(missing_items),
                "origin_slug": origin_slug,
                "origin_label": origin_meta["label"],
                "origin_class": origin_meta["class"],
                "owner_slug": owner_slug,
                "owner_label": owner_meta["label"],
                "owner_class": owner_meta["class"],
                "owner_hint": owner_hint,
                "stage_slug": process.stage,
                "updated_label": _format_last_seen(updated_at, now=reference),
                "updated_sort": updated_at or datetime.min.replace(tzinfo=reference.tzinfo),
            }
        )

    cards.sort(key=lambda item: (item["priority_rank"], item["updated_sort"]), reverse=False)
    return cards


def build_whatsapp_cards(customer_repository: CustomerRepository, *, now: datetime | None = None) -> list[dict]:
    reference = now or current_business_datetime()
    phones = (
        set(ai_sessions)
        | set(estados_encomenda)
        | set(estados_cafeteria)
        | set(estados_cestas_box)
        | set(estados_entrega)
        | set(estados_atendimento)
    )
    cards: list[dict] = []

    for phone in phones:
        session = ai_sessions.get(phone)
        recent = recent_messages.get(phone) if phone in recent_messages else None
        last_seen = _parse_runtime_timestamp((recent or {}).get("hora"))
        if last_seen is not None and last_seen.tzinfo is None:
            last_seen = last_seen.replace(tzinfo=reference.tzinfo)
        if last_seen and (reference - last_seen) > timedelta(hours=24):
            continue

        source_key = None
        if phone in estados_atendimento:
            source_key = "estados_atendimento"
        elif phone in estados_entrega:
            source_key = "estados_entrega"
        elif phone in estados_cestas_box:
            source_key = "estados_cestas_box"
        elif phone in estados_encomenda:
            source_key = "estados_encomenda"
        elif phone in estados_cafeteria:
            source_key = "estados_cafeteria"
        elif session and session.get("current_agent") in {"CakeOrderAgent", "SweetOrderAgent", "CafeteriaAgent"}:
            source_key = str(session.get("current_agent"))

        if source_key is None:
            continue

        customer = customer_repository.get_customer_by_phone(phone)
        customer_name = customer.nome if customer else phone
        if _looks_like_test_customer(customer_name):
            continue

        stage_label, stage_class = _WHATSAPP_STAGE_META[source_key]
        last_message = (recent or {}).get("texto") or _latest_user_message(session) or "Sem mensagem recente"

        cards.append(
            {
                "phone": phone,
                "cliente_nome": customer_name,
                "stage_label": stage_label,
                "stage_class": stage_class,
                "last_message": str(last_message),
                "last_seen_label": _format_last_seen(last_seen, now=reference),
                "last_seen_sort": last_seen or datetime.min.replace(tzinfo=reference.tzinfo),
                "agent": (session or {}).get("current_agent") or source_key,
                "is_human_handoff": source_key == "estados_atendimento",
                "owner_slug": "humano" if source_key == "estados_atendimento" else "bot",
                "owner_label": (
                    _PROCESS_OWNER_META["humano"]["label"]
                    if source_key == "estados_atendimento"
                    else _PROCESS_OWNER_META["bot"]["label"]
                ),
                "owner_class": (
                    _PROCESS_OWNER_META["humano"]["class"]
                    if source_key == "estados_atendimento"
                    else _PROCESS_OWNER_META["bot"]["class"]
                ),
            }
        )

    cards.sort(key=lambda item: item["last_seen_sort"], reverse=True)
    return cards


def _normalize_order(item: OrderPanelItem, *, today: date) -> dict:
    delivery_date = parse_order_date(item.data_entrega)
    created_date = parse_created_date(item.criado_em)
    status_slug = normalize_status(item.status, item.tipo)
    type_slug = _normalize_type(item.tipo, status_slug)
    value = _safe_float(item.valor_total)
    category_slug = (item.categoria or "sem_categoria").strip().lower() or "sem_categoria"
    days_until = (delivery_date - today).days if delivery_date else None
    recent_delivery_cutoff = today - timedelta(days=7)
    recent_created_cutoff = today - timedelta(days=21)
    is_operational = status_slug != "entregue" and (
        (delivery_date is not None and delivery_date >= recent_delivery_cutoff)
        or (created_date is not None and created_date >= recent_created_cutoff)
    )

    if status_slug == "entregue":
        schedule_bucket = "done"
        schedule_label = "Concluído"
        urgency_rank = 5
    elif delivery_date is None:
        schedule_bucket = "unscheduled"
        schedule_label = "Sem data"
        urgency_rank = 4
    elif days_until < 0:
        schedule_bucket = "overdue"
        schedule_label = "Atrasado"
        urgency_rank = 0
    elif days_until == 0:
        schedule_bucket = "today"
        schedule_label = "Hoje"
        urgency_rank = 1
    elif days_until <= 7:
        schedule_bucket = "upcoming"
        schedule_label = "Próximos 7 dias"
        urgency_rank = 2
    else:
        schedule_bucket = "later"
        schedule_label = "Depois"
        urgency_rank = 3

    status_meta = _STATUS_META[status_slug]
    type_label = _TYPE_META.get(type_slug, type_slug.replace("_", " ").title())
    category_label = _format_category(item.categoria)
    product_label = (item.produto or "").strip() or category_label
    horario = (item.horario or "").strip()
    ready_status = "retirada" if type_slug == "retirada" else "agendada"
    search_blob = " ".join(
        part
        for part in [
            str(item.id),
            item.cliente_nome or "",
            product_label,
            category_label,
            status_meta["label"],
            type_label,
            _format_full_date(delivery_date, item.data_entrega),
        ]
        if part
    ).casefold()

    return {
        "id": item.id,
        "cliente_nome": item.cliente_nome or "Cliente não identificado",
        "produto": product_label,
        "categoria_label": category_label,
        "categoria_slug": category_slug,
        "data_label": _format_full_date(delivery_date, item.data_entrega),
        "data_compacta": _format_compact_date(delivery_date),
        "data_iso": delivery_date.isoformat() if delivery_date else "",
        "horario": horario or "Sem horário",
        "horario_sort": horario or "99:99",
        "valor_total": value,
        "valor_label": _format_currency(value),
        "status_slug": status_slug,
        "status_label": status_meta["label"],
        "status_badge_class": status_meta["badge_class"],
        "status_sort": status_meta["sort"],
        "tipo_slug": type_slug,
        "tipo_label": type_label,
        "ready_status": ready_status,
        "ready_label": "Retirada" if ready_status == "retirada" else "Agendada",
        "days_until": days_until,
        "schedule_bucket": schedule_bucket,
        "schedule_label": schedule_label,
        "urgency_rank": urgency_rank,
        "is_active": status_slug != "entregue",
        "is_operational": is_operational,
        "is_test_like": _looks_like_test_customer(item.cliente_nome),
        "missing_value": value <= 0,
        "missing_date": delivery_date is None,
        "missing_time": not horario,
        "missing_product": not (item.produto or "").strip(),
        "created_date_iso": created_date.isoformat() if created_date else "",
        "search_blob": search_blob,
    }


def _sort_orders(orders: list[dict]) -> list[dict]:
    return sorted(
        orders,
        key=lambda item: (
            item["urgency_rank"],
            item["data_iso"] or "9999-12-31",
            item["horario_sort"],
            item["id"],
        ),
    )


def _build_distribution(counter: Counter, labels: dict[str, str]) -> list[dict]:
    total = sum(counter.values()) or 1
    rows = []
    for key, count in counter.most_common():
        rows.append(
            {
                "key": key,
                "label": labels.get(key, key.replace("_", " ").title()),
                "count": count,
                "share": round((count / total) * 100, 1),
            }
        )
    return rows


def build_dashboard_context(items: list[OrderPanelItem], *, today: date | None = None) -> dict:
    reference_date = today or current_business_date()
    normalized_orders = [_normalize_order(item, today=reference_date) for item in items]
    orders = _sort_orders(
        [item for item in normalized_orders if not (item["is_test_like"] and not item["is_operational"])]
    )

    active_orders = [item for item in orders if item["is_active"]]
    operational_orders = [item for item in active_orders if item["is_operational"]]
    historical_open_orders = [item for item in active_orders if not item["is_operational"]]
    overdue_orders = [item for item in active_orders if item["schedule_bucket"] == "overdue"]
    today_orders = [item for item in active_orders if item["schedule_bucket"] == "today"]
    next_orders = [item for item in active_orders if item["schedule_bucket"] == "upcoming"]
    unscheduled_orders = [item for item in active_orders if item["schedule_bucket"] == "unscheduled"]

    valued_orders = [item["valor_total"] for item in orders if item["valor_total"] > 0]
    active_revenue = sum(item["valor_total"] for item in active_orders)

    category_counter = Counter(item["categoria_slug"] for item in orders)
    status_counter = Counter(item["status_slug"] for item in orders)
    type_counter = Counter(item["tipo_slug"] for item in orders)

    category_revenue: dict[str, float] = defaultdict(float)
    customer_summary: dict[str, dict] = defaultdict(lambda: {"orders": 0, "revenue": 0.0})
    for item in orders:
        category_revenue[item["categoria_slug"]] += item["valor_total"]
        customer_summary[item["cliente_nome"]]["orders"] += 1
        customer_summary[item["cliente_nome"]]["revenue"] += item["valor_total"]

    top_customers = sorted(
        (
            {
                "cliente_nome": customer,
                "orders": payload["orders"],
                "revenue": _format_currency(payload["revenue"]),
            }
            for customer, payload in customer_summary.items()
        ),
        key=lambda row: (-row["orders"], row["cliente_nome"]),
    )[:5]

    categories = []
    category_total = sum(category_counter.values()) or 1
    for slug, count in category_counter.most_common():
        categories.append(
            {
                "slug": slug,
                "label": _format_category(slug),
                "count": count,
                "share": round((count / category_total) * 100, 1),
                "revenue": _format_currency(category_revenue[slug]),
            }
        )

    filters = {
        "statuses": [
            {"value": key, "label": meta["label"]}
            for key, meta in _STATUS_META.items()
            if status_counter.get(key)
        ],
        "types": [
            {"value": key, "label": _TYPE_META.get(key, key.title())}
            for key, count in type_counter.items()
            if count
        ],
        "categories": [{"value": row["slug"], "label": row["label"]} for row in categories],
        "schedule_buckets": [
            {"value": "all", "label": "Todos"},
            {"value": "overdue", "label": "Atrasados"},
            {"value": "today", "label": "Hoje"},
            {"value": "upcoming", "label": "Próximos 7 dias"},
            {"value": "unscheduled", "label": "Sem data"},
            {"value": "done", "label": "Concluídos"},
        ],
    }

    kanban_columns = [
        {
            "key": "pendente",
            "title": "Pendentes",
            "description": "Pedidos aguardando ação",
            "items": [item for item in operational_orders if item["status_slug"] == "pendente"],
        },
        {
            "key": "em_preparo",
            "title": "Em preparo",
            "description": "Pedidos em produção",
            "items": [item for item in operational_orders if item["status_slug"] == "em_preparo"],
        },
        {
            "key": "saida",
            "title": "Retirada / Agendados",
            "description": "Pedidos quase concluídos",
            "items": [item for item in operational_orders if item["status_slug"] in {"retirada", "agendada"}],
        },
        {
            "key": "entregue",
            "title": "Concluídos",
            "description": "Pedidos finalizados recentemente",
            "items": [
                item
                for item in orders
                if item["status_slug"] == "entregue"
                and (
                    item["created_date_iso"] >= (reference_date - timedelta(days=21)).isoformat()
                    or item["data_iso"] >= (reference_date - timedelta(days=7)).isoformat()
                )
            ],
        },
    ]

    return {
        "generated_at": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "reference_date": reference_date.strftime("%d/%m/%Y"),
        "metrics": [
            {"label": "Em operação", "value": str(len(operational_orders)), "hint": "Pedidos atuais da fila"},
            {"label": "Hoje", "value": str(len(today_orders)), "hint": "Pedidos programados para hoje"},
            {"label": "Atrasados", "value": str(len(overdue_orders)), "hint": "Pedidos vencidos sem conclusão"},
            {
                "label": "Receita em operação",
                "value": _format_currency(active_revenue),
                "hint": "Valor dos pedidos em aberto",
            },
        ],
        "secondary_metrics": [
            {"label": "Hoje", "value": str(len(today_orders)), "hint": "Pedidos com data de hoje"},
            {"label": "Sem data", "value": str(len(unscheduled_orders)), "hint": "Pedidos que precisam revisão"},
            {"label": "Entregues", "value": str(status_counter.get("entregue", 0)), "hint": "Concluídos"},
            {
                "label": "Histórico aberto",
                "value": str(len(historical_open_orders)),
                "hint": "Pedidos antigos fora da fila atual",
            },
        ],
        "quality_metrics": [
            {"label": "Sem valor", "value": str(sum(1 for item in orders if item["missing_value"]))},
            {"label": "Sem data", "value": str(sum(1 for item in orders if item["missing_date"]))},
            {"label": "Sem horário", "value": str(sum(1 for item in orders if item["missing_time"]))},
            {"label": "Sem produto", "value": str(sum(1 for item in orders if item["missing_product"]))},
        ],
        "priority_sections": [
            {"title": "Atrasados", "tone": "critical", "items": overdue_orders[:8]},
            {"title": "Hoje", "tone": "today", "items": today_orders[:8]},
            {"title": "Próximos 7 dias", "tone": "upcoming", "items": next_orders[:8]},
        ],
        "categories": categories,
        "status_distribution": _build_distribution(
            status_counter,
            {key: meta["label"] for key, meta in _STATUS_META.items()},
        ),
        "type_distribution": _build_distribution(type_counter, _TYPE_META),
        "top_customers": top_customers,
        "orders": orders,
        "operational_orders": operational_orders,
        "historical_open_orders": historical_open_orders,
        "kanban_columns": kanban_columns,
        "filters": filters,
    }


def _counter_total(name: str) -> int:
    counters, _ = snapshot_metrics()
    total = 0.0
    for (metric_name, _labels), value in counters.items():
        if metric_name == name:
            total += value
    return int(total)


def build_sync_overview(
    process_cards: list[dict],
    whatsapp_cards: list[dict],
    *,
    confirmed_orders_count: int,
) -> dict:
    ai_drafts = [card for card in process_cards if card.get("origin_slug") == "ai"]
    ready_to_close = [
        card
        for card in process_cards
        if card.get("stage_slug") in {"aguardando_confirmacao", "pagamento_pendente"}
    ]
    handoff_cards = [card for card in whatsapp_cards if card.get("is_human_handoff")]
    blocked_attempts = _counter_total("ai_order_confirmation_blocks_total")

    alerts: list[dict] = []
    if blocked_attempts:
        alerts.append(
            {
                "tone": "danger",
                "title": "Bloqueios de confirmacao",
                "description": (
                    f"{blocked_attempts} tentativa(s) de salvar pedido pela IA foram bloqueadas "
                    "por falta de confirmacao explicita."
                ),
            }
        )
    if ai_drafts:
        alerts.append(
            {
                "tone": "warning",
                "title": "Rascunhos fora do board",
                "description": (
                    f"{len(ai_drafts)} rascunho(s) de IA seguem no atendimento e ainda nao entraram "
                    "na operacao como pedido confirmado."
                ),
            }
        )
    if handoff_cards:
        alerts.append(
            {
                "tone": "muted",
                "title": "Handoff humano ativo",
                "description": (
                    f"{len(handoff_cards)} conversa(s) dependem de acompanhamento humano no WhatsApp."
                ),
            }
        )

    return {
        "metrics": [
            {
                "label": "Rascunhos IA",
                "value": str(len(ai_drafts)),
                "hint": "Pedidos montados pela IA aguardando fechamento",
                "tone": "warning",
            },
            {
                "label": "Prontos para fechar",
                "value": str(len(ready_to_close)),
                "hint": "Atendimentos com dados quase completos",
                "tone": "accent",
            },
            {
                "label": "Pedidos confirmados",
                "value": str(confirmed_orders_count),
                "hint": "Pedidos ja no board operacional",
                "tone": "success",
            },
            {
                "label": "Handoff humano",
                "value": str(len(handoff_cards)),
                "hint": "Conversas sob atendimento manual",
                "tone": "muted",
            },
        ],
        "alerts": alerts,
    }


def build_process_sections(process_cards: list[dict]) -> list[dict]:
    ready_cards = [
        card for card in process_cards if card.get("stage_slug") in {"aguardando_confirmacao", "pagamento_pendente"}
    ]
    followup_cards = [
        card for card in process_cards if card.get("stage_slug") not in {"aguardando_confirmacao", "pagamento_pendente"}
    ]
    return [
        {
            "title": "Prontos para fechamento",
            "description": "Pedidos que dependem de resposta final do cliente",
            "count": len(ready_cards),
            "cards": ready_cards,
        },
        {
            "title": "Em coleta e acompanhamento",
            "description": "Fluxos ainda em montagem ou revisao",
            "count": len(followup_cards),
            "cards": followup_cards,
        },
    ]
