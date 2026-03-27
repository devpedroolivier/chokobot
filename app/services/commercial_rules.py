from __future__ import annotations


SAME_DAY_CAKE_ORDER_CUTOFF = (11, 0)
DELIVERY_CUTOFF = (17, 30)
DELIVERY_FEE_STANDARD = 10.0
CROISSANT_PREP_MINUTES = 20
CARD_INSTALLMENT_MIN_TOTAL = 100.0
CARD_INSTALLMENT_MAX = 2

STORE_WINDOWS = {
    0: ("12:00", "18:00"),
    1: ("09:00", "18:00"),
    2: ("09:00", "18:00"),
    3: ("09:00", "18:00"),
    4: ("09:00", "18:00"),
    5: ("09:00", "18:00"),
}


def _format_brl(value: float) -> str:
    return f"R${value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _format_hhmm(parts: tuple[int, int]) -> str:
    hour, minute = parts
    return f"{hour:02d}:{minute:02d}"


SAME_DAY_CAKE_ORDER_CUTOFF_LABEL = _format_hhmm(SAME_DAY_CAKE_ORDER_CUTOFF)
DELIVERY_CUTOFF_LABEL = _format_hhmm(DELIVERY_CUTOFF)
DELIVERY_FEE_STANDARD_LABEL = _format_brl(DELIVERY_FEE_STANDARD)
STORE_HOURS_SUMMARY = "Segunda: 12h-18h | Terca a sabado: 9h-18h | Domingo: fechado."
STORE_OPERATION_RULE_LINE = f"Horario de funcionamento: {STORE_HOURS_SUMMARY}"
SUNDAY_RULE_LINE = "Nao fazemos pedidos, retiradas ou encomendas para domingo."
SUNDAY_UNAVAILABLE_MESSAGE = f"{SUNDAY_RULE_LINE} Horario de funcionamento: {STORE_HOURS_SUMMARY}"
DELIVERY_RULE_LINE = (
    f"A Chokodelícia FAZ entregas! Taxa padrão: {DELIVERY_FEE_STANDARD_LABEL}. "
    f"Horário limite: até {DELIVERY_CUTOFF_LABEL}."
)
PAYMENT_CHANGE_RULE_LINE = (
    "Regras de pagamento: troco so existe para Dinheiro. "
    "Se for Dinheiro, pergunte se o cliente precisa de troco (use troco_para=0 quando nao precisar). "
    "PIX e Cartao nao usam troco."
)
SIMPLE_PAYMENT_CHANGE_RULE_LINE = (
    "Troco so existe para Dinheiro. "
    "Se for Dinheiro, pergunte se o cliente precisa de troco (use troco_para=0 quando nao precisar). "
    "PIX e Cartao nao usam troco."
)
PAYMENT_INSTALLMENT_RULE_LINE = (
    f"Parcelamento so no Cartao e somente acima de {_format_brl(CARD_INSTALLMENT_MIN_TOTAL)}, em ate {CARD_INSTALLMENT_MAX}x."
)
CROISSANT_PREP_RULE_LINE = f"Se o cliente perguntar tempo de preparo do croissant, informe {CROISSANT_PREP_MINUTES} minutos."
