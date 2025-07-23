import os
from dotenv import load_dotenv

load_dotenv()

ZAPI_TOKEN = os.getenv("ZAPI_TOKEN")
ZAPI_BASE = os.getenv("ZAPI_BASE")

if not ZAPI_TOKEN or not ZAPI_BASE:
    raise EnvironmentError("⚠️ Variáveis obrigatórias faltando no .env: ZAPI_TOKEN ou ZAPI_BASE")

ZAPI_ENDPOINT_TEXT = f"{ZAPI_BASE}/send-text"
ZAPI_ENDPOINT_IMAGE = f"{ZAPI_BASE}/send-image"

