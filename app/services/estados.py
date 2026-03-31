from app.infrastructure.state.conversation_state_store import build_conversation_state_store

_store = build_conversation_state_store()

estados_encomenda = _store.estados_encomenda
estados_cafeteria = _store.estados_cafeteria
estados_entrega = _store.estados_entrega
estados_cestas_box = _store.estados_cestas_box
estados_atendimento = _store.estados_atendimento
ai_sessions = _store.ai_sessions
recent_messages = _store.recent_messages
conversation_threads = _store.conversation_threads


def is_bot_ativo() -> bool:
    return _store.is_bot_ativo()


def set_bot_ativo(value: bool) -> None:
    _store.set_bot_ativo(value)


def is_phone_opted_out(phone: str | None) -> bool:
    return _store.is_phone_opted_out(phone)


def set_phone_opted_out(phone: str | None, value: bool) -> None:
    _store.set_phone_opted_out(phone, value)


def get_phone_opted_out_updated_at(phone: str | None):
    return _store.get_phone_opted_out_updated_at(phone)


def has_processed_message(message_id: str) -> bool:
    return _store.has_processed_message(message_id)


def mark_processed_message(message_id: str, seen_at) -> None:
    _store.mark_processed_message(message_id, seen_at)


def mark_processed_message_if_new(message_id: str, seen_at, ttl_seconds: int = 60) -> bool:
    return _store.mark_processed_message_if_new(message_id, seen_at, ttl_seconds=ttl_seconds)


def get_recent_message(phone: str) -> dict | None:
    return _store.get_recent_message(phone)


def set_recent_message(phone: str, text: str, seen_at) -> None:
    _store.set_recent_message(phone, text, seen_at)


def get_conversation_messages(phone: str) -> list[dict]:
    return _store.get_conversation_messages(phone)


def append_conversation_message(phone: str, *, role: str, actor_label: str, content: str, seen_at) -> None:
    _store.append_conversation_message(
        phone,
        role=role,
        actor_label=actor_label,
        content=content,
        seen_at=seen_at,
    )


def clear_runtime_state() -> None:
    _store.clear_runtime_state()


SUBESTADO_FORMA_PAGAMENTO = "AGUARDANDO_FORMA_PAGAMENTO"
SUBESTADO_TROCO = "AGUARDANDO_TROCO"
FORMAS_PAGAMENTO = {
    "1": "PIX",
    "2": "Cartão (débito/crédito)",
    "3": "Dinheiro",
}
