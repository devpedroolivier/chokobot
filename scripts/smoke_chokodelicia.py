#!/usr/bin/env python3
"""Smoke test das regras determinísticas da Chokodelícia.

Cobre os caminhos do runner que NÃO chamam OpenAI: saudação, chave PIX,
catálogo/foto, Páscoa, handoff humano, opt-out, mensagem vazia (mídia),
e taxa de entrega. Não toca WhatsApp real nem OpenAI."""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _setup_env() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="chokobot-smoke-"))
    defaults = {
        "BOT_AUTO_REPLIES_ENABLED": "1",
        "AI_AUTO_SCHEDULE_ENABLED": "0",
        "OPENAI_API_KEY": "smoke-key",
        "ZAPI_TOKEN": "smoke-token",
        "ZAPI_BASE": "https://example.test",
        "MESSAGING_PROVIDER": "zapi",
        "DB_PATH": str(tmp / "chokobot.db"),
        "OUTBOX_EVENTS_PATH": str(tmp / "events.jsonl"),
        "OUTBOX_PATH": str(tmp / "outbox.jsonl"),
        "PIX_KEY": "Pix 16847366000130",
        "CATALOG_LINK": "https://bit.ly/presenteschoko",
        "CAFETERIA_URL": "http://bit.ly/44ZlKlZ",
        "DOCES_URL": "https://bit.ly/doceschoko",
    }
    for key, value in defaults.items():
        os.environ.setdefault(key, value)


_setup_env()

from app.ai.runner import process_message_with_ai  # noqa: E402
from app.models import criar_tabelas  # noqa: E402
from app.services.estados import ai_sessions, clear_runtime_state  # noqa: E402

criar_tabelas()

from app.welcome_message import (  # noqa: E402
    EASTER_CATALOG_MESSAGE,
    HUMAN_HANDOFF_MESSAGE,
    OPT_OUT_MESSAGE,
    WELCOME_MESSAGE,
)


SCENARIOS = [
    {
        "id": "saudacao_oi",
        "text": "oi",
        "expect_substring": WELCOME_MESSAGE.split("\n", 1)[0][:30],
        "description": "Saudação genérica → mensagem de boas-vindas",
    },
    {
        "id": "pix_chave",
        "text": "qual a chave pix de vocês?",
        "expect_substring": "16847366000130",
        "description": "Pedido de chave PIX → resposta com chave real",
    },
    {
        "id": "catalogo_bolo",
        "text": "me manda foto dos bolos",
        "expect_substring": "presenteschoko",
        "description": "Foto de bolos → link do catálogo de presentes",
    },
    {
        "id": "catalogo_doces",
        "text": "me manda o cardápio de doces",
        "expect_substring": "doceschoko",
        "description": "Cardápio de doces → link de doces",
    },
    {
        "id": "catalogo_cafeteria",
        "text": "quero ver o cardápio da cafeteria",
        "expect_substring": "44ZlKlZ",
        "description": "Cardápio cafeteria → link da cafeteria",
    },
    {
        "id": "pascoa_ovo",
        "text": "quero um ovo de páscoa",
        "expect_substring": "pascoachoko.goomer.app",
        "description": "Pedido de Páscoa → link oficial pascoachoko",
    },
    {
        "id": "pascoa_trio",
        "text": "tem trio de páscoa?",
        "expect_substring": "pascoachoko.goomer.app",
        "description": "Trio de Páscoa → link oficial",
    },
    {
        "id": "humano_explicito",
        "text": "quero falar com humano",
        "expect_substring": "transferindo",
        "description": "Pedido de humano → handoff para atendente",
    },
    {
        "id": "opt_out",
        "text": "para de me mandar mensagem, quero desativar o chat",
        "expect_substring": OPT_OUT_MESSAGE.split("\n", 1)[0][:25],
        "description": "Pedido de desativar → opt-out",
    },
    {
        "id": "midia_vazia",
        "text": "",
        "expect_substring": "mídia",
        "description": "Mensagem sem texto → resposta de mídia",
    },
    {
        "id": "taxa_entrega",
        "text": "qual a taxa de entrega?",
        "expect_substring": "10",
        "description": "Pergunta de taxa entrega → R$10,00",
    },
]


def _phone_for(scenario_id: str) -> str:
    digits = "".join(filter(str.isdigit, scenario_id.encode().hex()))[:4].zfill(4)
    return f"5511{digits}99999"[:13]


async def _run_scenario(scenario: dict) -> dict:
    phone = _phone_for(scenario["id"])
    ai_sessions.pop(phone, None)
    try:
        reply = await process_message_with_ai(phone, scenario["text"], "Cliente Smoke", 1)
    except Exception as exc:
        return {
            **scenario,
            "phone": phone,
            "reply": "",
            "passed": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
    expected = scenario["expect_substring"]
    passed = expected.lower() in (reply or "").lower()
    return {
        **scenario,
        "phone": phone,
        "reply": (reply or "").strip(),
        "passed": passed,
        "error": None,
    }


async def main() -> int:
    clear_runtime_state()
    print(f"\n{'=' * 80}\nSMOKE — Chokodelícia (regras determinísticas)\n{'=' * 80}\n")

    results = []
    for scenario in SCENARIOS:
        result = await _run_scenario(scenario)
        results.append(result)
        status = "✅ PASS" if result["passed"] else "❌ FAIL"
        print(f"{status}  [{result['id']}] {result['description']}")
        if not result["passed"]:
            if result["error"]:
                print(f"        ERRO: {result['error']}")
            else:
                print(f"        Esperava conter: {result['expect_substring']!r}")
                preview = result["reply"][:160].replace("\n", " | ")
                print(f"        Resposta:        {preview!r}")
        print()

    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    print(f"{'=' * 80}\nResultado: {passed}/{total} cenários passaram")
    print(f"{'=' * 80}\n")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
