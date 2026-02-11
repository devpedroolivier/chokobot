import os
from dotenv import load_dotenv

load_dotenv()

ZAPI_TOKEN = os.getenv("ZAPI_TOKEN")
ZAPI_BASE = os.getenv("ZAPI_BASE")

PANEL_AUTH_USER = os.getenv("PANEL_AUTH_USER")
PANEL_AUTH_PASS = os.getenv("PANEL_AUTH_PASS")

WEBHOOK_TOKEN = os.getenv("WEBHOOK_TOKEN")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")
WEBHOOK_TOKEN_HEADER = os.getenv("WEBHOOK_TOKEN_HEADER", "X-Webhook-Token")
WEBHOOK_SIGNATURE_HEADER = os.getenv("WEBHOOK_SIGNATURE_HEADER", "X-Webhook-Signature")

missing = []
if not ZAPI_TOKEN or not ZAPI_BASE:
    missing.extend(["ZAPI_TOKEN", "ZAPI_BASE"])
if not PANEL_AUTH_USER or not PANEL_AUTH_PASS:
    missing.extend(["PANEL_AUTH_USER", "PANEL_AUTH_PASS"])
if not (WEBHOOK_TOKEN or WEBHOOK_SECRET):
    missing.append("WEBHOOK_TOKEN ou WEBHOOK_SECRET")

if missing:
    raise EnvironmentError(
        "Variaveis obrigatorias faltando no .env: " + ", ".join(missing)
    )

ZAPI_ENDPOINT_TEXT = f"{ZAPI_BASE}/send-text"
ZAPI_ENDPOINT_IMAGE = f"{ZAPI_BASE}/send-image"

CAFETERIA_URL = os.getenv("CAFETERIA_URL", "http://bit.ly/44ZlKlZ")
DOCES_URL = os.getenv("DOCES_URL", "https://bit.ly/doceschoko")
