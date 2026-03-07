from __future__ import annotations

import os

import httpx


class HttpConversationGateway:
    def __init__(self, base_url: str | None = None, client_factory=None):
        self.base_url = (base_url or os.getenv("CONVERSATION_SERVICE_URL", "")).rstrip("/")
        if not self.base_url:
            raise ValueError("CONVERSATION_SERVICE_URL is required for HttpConversationGateway")
        self.timeout = float(os.getenv("CONVERSATION_SERVICE_TIMEOUT", "10"))
        self._client_factory = client_factory

    def _build_client(self):
        if self._client_factory is not None:
            return self._client_factory()
        return httpx.AsyncClient(timeout=self.timeout)

    async def handle_inbound_message(self, payload: dict) -> None:
        async with self._build_client() as client:
            response = await client.post(f"{self.base_url}/internal/messages/handle", json={"payload": payload})
            response.raise_for_status()

    async def generate_reply(
        self,
        *,
        telefone: str,
        text: str,
        nome_cliente: str,
        cliente_id: int,
    ) -> str:
        async with self._build_client() as client:
            response = await client.post(
                f"{self.base_url}/internal/messages/reply",
                json={
                    "telefone": telefone,
                    "text": text,
                    "nome_cliente": nome_cliente,
                    "cliente_id": cliente_id,
                },
            )
            response.raise_for_status()
            payload = response.json()
        return str(payload.get("reply", ""))
