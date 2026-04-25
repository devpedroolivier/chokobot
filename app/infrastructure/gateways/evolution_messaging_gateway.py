from __future__ import annotations

import asyncio
import json
import os

import httpx

from app.observability import increment_counter, log_event
from app.security import hash_phone, preview_text
from app.settings import get_settings

class EvolutionMessagingGateway:
    def __init__(self):
        self._locks_envio: dict[str, asyncio.Lock] = {}
        settings = get_settings()
        self._http_timeout_connect = settings.http_timeout_connect
        self._http_timeout_read = settings.http_timeout_read
        self._http_max_retries = settings.http_max_retries
        self._http_backoff_factor = settings.http_backoff_factor
        self._outbox_path = settings.outbox_path
        self._endpoint_text = settings.evolution_endpoint_text
        self._api_key = settings.evolution_api_key

    def _enqueue(self, phone: str, mensagem: str):
        try:
            os.makedirs(os.path.dirname(self._outbox_path), exist_ok=True)
            with open(self._outbox_path, "a", encoding="utf-8") as handle:
                handle.write(json.dumps({"phone": phone, "message": mensagem}, ensure_ascii=False) + "\n")
            increment_counter("outbox_events_total", status="queued")
            log_event("outbox_queued", phone_hash=hash_phone(phone), text=preview_text(mensagem, 80))
        except Exception as exc:
            log_event("outbox_queue_failed", error_type=type(exc).__name__)

    async def send_text(self, phone: str, mensagem: str) -> bool:
        lock = self._locks_envio.setdefault(phone, asyncio.Lock())
        async with lock:
            payload = {"number": phone, "text": mensagem}
            headers = {"Content-Type": "application/json", "apikey": self._api_key}
            timeout = httpx.Timeout(
                connect=self._http_timeout_connect,
                read=self._http_timeout_read,
                write=self._http_timeout_read,
                pool=self._http_timeout_connect,
            )

            last_exc = None
            async with httpx.AsyncClient(timeout=timeout) as client:
                for attempt in range(1, self._http_max_retries + 1):
                    try:
                        log_event(
                            "provider_send_attempt",
                            provider="evolution",
                            attempt=attempt,
                            max_attempts=self._http_max_retries,
                            phone_hash=hash_phone(phone),
                            text=preview_text(mensagem, 120),
                        )
                        increment_counter("provider_send_attempts_total", provider="evolution")
                        response = await client.post(self._endpoint_text, json=payload, headers=headers)
                        status_code = response.status_code

                        if 200 <= status_code < 300:
                            increment_counter("provider_send_results_total", provider="evolution", status="success")
                            log_event(
                                "provider_send_success",
                                provider="evolution",
                                status_code=status_code,
                                phone_hash=hash_phone(phone),
                            )
                            return True

                        increment_counter("provider_send_results_total", provider="evolution", status="http_error")
                        log_event(
                            "provider_send_http_error",
                            provider="evolution",
                            status_code=status_code,
                            phone_hash=hash_phone(phone),
                        )

                        if status_code not in (429, 500, 502, 503, 504):
                            self._enqueue(phone, mensagem)
                            return False

                    except (httpx.ConnectTimeout, httpx.ReadTimeout) as exc:
                        last_exc = exc
                        increment_counter("provider_send_results_total", provider="evolution", status="timeout")
                        log_event(
                            "provider_send_timeout",
                            provider="evolution",
                            attempt=attempt,
                            error_type=type(exc).__name__,
                        )
                    except httpx.HTTPError as exc:
                        last_exc = exc
                        increment_counter("provider_send_results_total", provider="evolution", status="transport_error")
                        log_event(
                            "provider_send_transport_error",
                            provider="evolution",
                            attempt=attempt,
                            error_type=type(exc).__name__,
                        )

                    if attempt < self._http_max_retries:
                        backoff = self._http_backoff_factor * (2 ** (attempt - 1))
                        await asyncio.sleep(backoff)

            log_event(
                "provider_send_failed",
                provider="evolution",
                error_type=type(last_exc).__name__ if last_exc else None,
                phone_hash=hash_phone(phone),
            )
            self._enqueue(phone, mensagem)
            return False
