# app/utils/mensagens.py
import os, json, asyncio
import httpx
from app.config import ZAPI_ENDPOINT_TEXT, ZAPI_TOKEN

SAUDACOES = ["oi", "iae", "salve", "olá", "ola", "bom dia", "boa tarde", "boa noite"]

def is_saudacao(texto: str) -> bool:
    return any(sauda in (texto or "").lower() for sauda in SAUDACOES)

# --- Configs de rede (podem vir do .env; têm defaults seguros) ---
HTTP_TIMEOUT_CONNECT = int(os.getenv("HTTP_TIMEOUT_CONNECT", "5"))   # seg
HTTP_TIMEOUT_READ    = int(os.getenv("HTTP_TIMEOUT_READ", "20"))     # seg
HTTP_MAX_RETRIES     = int(os.getenv("HTTP_MAX_RETRIES", "3"))       # tentativas
HTTP_BACKOFF_FACTOR  = float(os.getenv("HTTP_BACKOFF_FACTOR", "1"))  # 1 -> 0s,1s,2s...
OUTBOX_PATH          = os.getenv("OUTBOX_PATH", "dados/outbox.jsonl")

def _enfileirar(phone: str, mensagem: str):
    """Guarda a mensagem localmente quando todas as tentativas falham."""
    try:
        os.makedirs(os.path.dirname(OUTBOX_PATH), exist_ok=True)
        with open(OUTBOX_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps({"phone": phone, "message": mensagem}, ensure_ascii=False) + "\n")
        print(f"📥 Mensagem enfileirada para retry offline: {phone}")
    except Exception as e:
        print(f"⚠️ Falha ao enfileirar mensagem: {e}")

async def responder_usuario(phone: str, mensagem: str) -> bool:
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
                print(f"\n📤 ENVIANDO MENSAGEM (tentativa {attempt}/{HTTP_MAX_RETRIES})"
                      f"\n📱 Para: {phone}\n💬 Conteúdo:\n{mensagem}\n")
                resp = await client.post(ZAPI_ENDPOINT_TEXT, json=payload, headers=headers)
                code = resp.status_code

                if 200 <= code < 300:
                    print(f"✅ Enviado! Código: {code}")
                    print(f"📦 Retorno: {resp.text}\n" + "-" * 50)
                    return True

                # Re-tenta apenas para códigos transitórios
                print(f"⚠️ HTTP {code} ao enviar: {resp.text[:200]}")
                if code not in (429, 500, 502, 503, 504):
                    return False

            except (httpx.ConnectTimeout, httpx.ReadTimeout) as e:
                last_exc = e
                print(f"⏱️ Timeout na tentativa {attempt}: {repr(e)}")
            except httpx.HTTPError as e:
                last_exc = e
                print(f"❌ Erro HTTP na tentativa {attempt}: {repr(e)}")

            # Backoff antes do próximo retry
            if attempt < HTTP_MAX_RETRIES:
                backoff = HTTP_BACKOFF_FACTOR * (2 ** (attempt - 1))
                await asyncio.sleep(backoff)

    print("❌ Falha definitiva ao enviar mensagem.", f"Último erro: {repr(last_exc)}")
    _enfileirar(phone, mensagem)
    return False
