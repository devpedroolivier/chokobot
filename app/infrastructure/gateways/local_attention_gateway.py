from __future__ import annotations

import datetime

from app.services.estados import estados_atendimento


class LocalAttentionGateway:
    def activate_human_handoff(self, *, telefone: str, motivo: str) -> str:
        estados_atendimento[telefone] = {
            "humano": True,
            "inicio": datetime.datetime.now().isoformat(),
            "motivo": motivo,
        }
        return f"Atendimento humano solicitado para {telefone}. Motivo: {motivo}"
