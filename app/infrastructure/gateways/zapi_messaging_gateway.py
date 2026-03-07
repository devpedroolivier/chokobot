from __future__ import annotations

import asyncio
import json
import os

import httpx

from app.config import ZAPI_ENDPOINT_TEXT, ZAPI_TOKEN
from app.observability import increment_counter, log_event
from app.security import hash_phone, preview_text


HTTP_TIMEOUT_CONNECT = int(os.getenv("HTTP_TIMEOUT_CONNECT", "5"))
HTTP_TIMEOUT_READ = int(os.getenv("HTTP_TIMEOUT_READ", "20"))
HTTP_MAX_RETRIES = int(os.getenv("HTTP_MAX_RETRIES", "3"))
HTTP_BACKOFF_FACTOR = float(os.getenv("HTTP_BACKOFF_FACTOR", "1"))
OUTBOX_PATH = os.getenv("OUTBOX_PATH", "dados/outbox.jsonl")


class ZapiMessagingGateway:
    def __init__(self):
        self._locks_envio: dict[str, asyncio.Lock] = {}

    def _enqueue(self, phone: str, mensagem: str):
        try:
            os.makedirs(os.path.dirname(OUTBOX_PATH), exist_ok=True)
            with open(OUTBOX_PATH, "a", encoding="utf-8") as handle:
                handle.write(json.dumps({"phone": phone, "message": mensagem}, ensure_ascii=False) + "\n")
            increment_counter("outbox_events_total", status="queued")
            log_event("outbox_queued", phone_hash=hash_phone(phone), text=preview_text(mensagem, 80))
        except Exception as exc:
            print(f"⚠️ Falha ao enfileirar mensagem: {exc}")

    async def send_text(self, phone: str, mensagem: str) -> bool:
        lock = self._locks_envio.setdefault(phone, asyncio.Lock())
        async with lock:
            payload = {"phone": phone, "message": mensagem}
            headers = {"Content-Type": "application/json", "Client-Token": ZAPI_TOKEN}
            timeout = httpx.Timeout(
                connect=HTTP_TIMEOUT_CONNECT,
                read=HTTP_TIMEOUT_READ,
                write=HTTP_TIMEOUT_READ,
                pool=HTTP_TIMEOUT_CONNECT,
            )

            last_exc = None
            async with httpx.AsyncClient(timeout=timeout) as client:
                for attempt in range(1, HTTP_MAX_RETRIES + 1):
                    try:
                        print(
                            f"[ZAPI] sending attempt={attempt}/{HTTP_MAX_RETRIES} "
                            f"phone_hash={hash_phone(phone)} text='{preview_text(mensagem, 120)}'"
                        )
                        increment_counter("provider_send_attempts_total", provider="zapi")
                        response = await client.post(ZAPI_ENDPOINT_TEXT, json=payload, headers=headers)
                        status_code = response.status_code

                        if 200 <= status_code < 300:
                            increment_counter("provider_send_results_total", provider="zapi", status="success")
                            log_event(
                                "provider_send_success",
                                provider="zapi",
                                status_code=status_code,
                                phone_hash=hash_phone(phone),
                            )
                            return True

                        increment_counter("provider_send_results_total", provider="zapi", status="http_error")
                        print(f"[ZAPI] http_error status={status_code} phone_hash={hash_phone(phone)}")

                        if status_code not in (429, 500, 502, 503, 504):
                            self._enqueue(phone, mensagem)
                            return False

                    except (httpx.ConnectTimeout, httpx.ReadTimeout) as exc:
                        last_exc = exc
                        increment_counter("provider_send_results_total", provider="zapi", status="timeout")
                        print(f"⏱️ Timeout na tentativa {attempt}: {repr(exc)}")
                    except httpx.HTTPError as exc:
                        last_exc = exc
                        increment_counter("provider_send_results_total", provider="zapi", status="transport_error")
                        print(f"❌ Erro HTTP na tentativa {attempt}: {repr(exc)}")

                    if attempt < HTTP_MAX_RETRIES:
                        backoff = HTTP_BACKOFF_FACTOR * (2 ** (attempt - 1))
                        await asyncio.sleep(backoff)

            print("❌ Falha definitiva ao enviar mensagem.", f"Último erro: {repr(last_exc)}")
            self._enqueue(phone, mensagem)
            return False
