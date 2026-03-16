from __future__ import annotations

from app.application.use_cases.manage_human_handoff import activate_human_handoff, deactivate_human_handoff


class LocalAttentionGateway:
    def activate_human_handoff(self, *, telefone: str, motivo: str) -> str:
        return activate_human_handoff(telefone, motivo=motivo)

    def deactivate_human_handoff(self, *, telefone: str) -> bool:
        return deactivate_human_handoff(telefone)
