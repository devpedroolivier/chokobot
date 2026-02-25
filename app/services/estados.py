from app.infrastructure.state.conversation_state_store import build_conversation_state_store

_store = build_conversation_state_store()

estados_encomenda = _store.estados_encomenda
estados_cafeteria = _store.estados_cafeteria
estados_entrega = _store.estados_entrega
estados_cestas_box = _store.estados_cestas_box
estados_atendimento = _store.estados_atendimento


def is_bot_ativo() -> bool:
    return _store.is_bot_ativo()


def set_bot_ativo(value: bool) -> None:
    _store.set_bot_ativo(value)


SUBESTADO_FORMA_PAGAMENTO = "AGUARDANDO_FORMA_PAGAMENTO"
SUBESTADO_TROCO = "AGUARDANDO_TROCO"
FORMAS_PAGAMENTO = {
    "1": "PIX",
    "2": "Cartão (débito/crédito)",
    "3": "Dinheiro",
}
