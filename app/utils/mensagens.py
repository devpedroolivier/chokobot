import asyncio, os, json, re, unicodedata
import httpx
from app.config import ZAPI_ENDPOINT_TEXT, ZAPI_TOKEN
from app.observability import increment_counter, log_event
from app.security import hash_phone, preview_text

SAUDACOES = ["oi", "iae", "salve", "olá", "ola", "bom dia", "boa tarde", "boa noite"]

def is_saudacao(texto: str) -> bool:
    return any(sauda in (texto or "").lower() for sauda in SAUDACOES)

HTTP_TIMEOUT_CONNECT = int(os.getenv("HTTP_TIMEOUT_CONNECT", "5"))
HTTP_TIMEOUT_READ    = int(os.getenv("HTTP_TIMEOUT_READ", "20"))
HTTP_MAX_RETRIES     = int(os.getenv("HTTP_MAX_RETRIES", "3"))
HTTP_BACKOFF_FACTOR  = float(os.getenv("HTTP_BACKOFF_FACTOR", "1"))
OUTBOX_PATH          = os.getenv("OUTBOX_PATH", "dados/outbox.jsonl")

# 🔒 Evita que dois envios simultâneos disparem para o mesmo número
_locks_envio = {}

_HEADING_ICON_RULES = (
    ("kit festou", "🎉"),
    ("bolos pronta entrega", "🎂"),
    ("bolo pronta entrega", "🎂"),
    ("monte seu bolo", "🎂"),
    ("tradicional", "🎂"),
    ("cafeteria", "☕"),
    ("vitrine", "☕"),
    ("doces avulsos", "🍬"),
    ("linha gourmet", "✨"),
    ("ingles", "🍰"),
    ("redondo", "🍰"),
    ("mesversario", "🎈"),
    ("revelacao", "🎈"),
    ("baby cake", "🧁"),
    ("tortas", "🥧"),
    ("linha simples", "🍰"),
    ("cestas", "🎁"),
    ("presentes", "🎁"),
    ("entregas", "🚚"),
    ("pagamento", "💳"),
    ("pronta entrega", "🛍️"),
    ("encomendas", "📦"),
)


def _normalize_heading(texto: str) -> str:
    base = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(char for char in base if not unicodedata.combining(char))
    return sem_acento.casefold()


def _heading_icon(titulo: str) -> str:
    normalized = _normalize_heading(titulo)
    for pattern, icon in _HEADING_ICON_RULES:
        if pattern in normalized:
            return icon
    return "📌"


def formatar_mensagem_saida(mensagem: str) -> str:
    linhas_formatadas = []
    for linha in mensagem.splitlines():
        match = re.match(r"^\s*#{2,6}\s+(.*\S)\s*$", linha)
        if not match:
            linhas_formatadas.append(linha)
            continue

        titulo = re.sub(r"^\d+\.\s*", "", match.group(1)).strip()
        linhas_formatadas.append(f"{_heading_icon(titulo)} {titulo}")
    return "\n".join(linhas_formatadas)

def _enfileirar(phone: str, mensagem: str):
    try:
        os.makedirs(os.path.dirname(OUTBOX_PATH), exist_ok=True)
        with open(OUTBOX_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps({"phone": phone, "message": mensagem}, ensure_ascii=False) + "\n")
        increment_counter("outbox_events_total", status="queued")
        log_event("outbox_queued", phone_hash=hash_phone(phone), text=preview_text(mensagem, 80))
    except Exception as e:
        print(f"⚠️ Falha ao enfileirar mensagem: {e}")

async def responder_usuario(phone: str, mensagem: str) -> bool:
    """
    Envia mensagem de forma confiável com retry controlado e lock por telefone.
    Garante que apenas uma mensagem por número é enviada por vez, evitando duplicidade.
    """
    mensagem = formatar_mensagem_saida(mensagem)

    # Lock por número para evitar sobreposição
    lock = _locks_envio.setdefault(phone, asyncio.Lock())
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
                    resp = await client.post(ZAPI_ENDPOINT_TEXT, json=payload, headers=headers)
                    code = resp.status_code

                    if 200 <= code < 300:
                        increment_counter("provider_send_results_total", provider="zapi", status="success")
                        log_event("provider_send_success", provider="zapi", status_code=code, phone_hash=hash_phone(phone))
                        break  # ✅ interrompe imediatamente após sucesso
                    else:
                        increment_counter("provider_send_results_total", provider="zapi", status="http_error")
                        print(f"[ZAPI] http_error status={code} phone_hash={hash_phone(phone)}")
                        if code not in (429, 500, 502, 503, 504):
                            break  # não precisa tentar de novo

                except (httpx.ConnectTimeout, httpx.ReadTimeout) as e:
                    last_exc = e
                    increment_counter("provider_send_results_total", provider="zapi", status="timeout")
                    print(f"⏱️ Timeout na tentativa {attempt}: {repr(e)}")
                except httpx.HTTPError as e:
                    last_exc = e
                    increment_counter("provider_send_results_total", provider="zapi", status="transport_error")
                    print(f"❌ Erro HTTP na tentativa {attempt}: {repr(e)}")

                # backoff entre tentativas
                if attempt < HTTP_MAX_RETRIES:
                    backoff = HTTP_BACKOFF_FACTOR * (2 ** (attempt - 1))
                    await asyncio.sleep(backoff)

            else:
                print("❌ Falha definitiva ao enviar mensagem.", f"Último erro: {repr(last_exc)}")
                _enfileirar(phone, mensagem)
                return False

        return True
