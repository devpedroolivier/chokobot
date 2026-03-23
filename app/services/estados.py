from app.infrastructure.state.conversation_state_store import build_conversation_state_store

_store = build_conversation_state_store()

estados_encomenda = _store.estados_encomenda
estados_cafeteria = _store.estados_cafeteria
estados_entrega = _store.estados_entrega
estados_cestas_box = _store.estados_cestas_box
estados_atendimento = _store.estados_atendimento
ai_sessions = _store.ai_sessions
recent_messages = _store.recent_messages


def is_bot_ativo() -> bool:
    return _store.is_bot_ativo()


def set_bot_ativo(value: bool) -> None:
    _store.set_bot_ativo(value)


def has_processed_message(message_id: str) -> bool:
    return _store.has_processed_message(message_id)


def mark_processed_message(message_id: str, seen_at) -> None:
    _store.mark_processed_message(message_id, seen_at)


def get_recent_message(phone: str) -> dict | None:
    return _store.get_recent_message(phone)


def set_recent_message(phone: str, text: str, seen_at) -> None:
    _store.set_recent_message(phone, text, seen_at)


def clear_runtime_state() -> None:
    _store.clear_runtime_state()


SUBESTADO_FORMA_PAGAMENTO = "AGUARDANDO_FORMA_PAGAMENTO"
SUBESTADO_TROCO = "AGUARDANDO_TROCO"
FORMAS_PAGAMENTO = {
    "1": "PIX",
    "2": "Cartão (débito/crédito)",
    "3": "Dinheiro",
}
