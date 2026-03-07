from __future__ import annotations

from app.models.entregas import salvar_entrega


class LocalDeliveryGateway:
    def create_delivery(
        self,
        *,
        encomenda_id: int,
        tipo: str = "entrega",
        endereco: str | None = None,
        data_agendada: str | None = None,
        status: str = "pendente",
    ) -> None:
        salvar_entrega(
            encomenda_id=encomenda_id,
            tipo=tipo,
            endereco=endereco,
            data_agendada=data_agendada,
            status=status,
        )
