import os
from dotenv import load_dotenv

load_dotenv()

ZAPI_TOKEN = os.getenv("ZAPI_TOKEN")
ZAPI_BASE = os.getenv("ZAPI_BASE")

if not ZAPI_TOKEN or not ZAPI_BASE:
    raise EnvironmentError("⚠️ Variáveis obrigatórias faltando no .env: ZAPI_TOKEN ou ZAPI_BASE")

ZAPI_ENDPOINT_TEXT = f"{ZAPI_BASE}/send-text"
ZAPI_ENDPOINT_IMAGE = f"{ZAPI_BASE}/send-image"

CAFETERIA_URL = os.getenv("CAFETERIA_URL", "http://bit.ly/44ZlKlZ")  # ajuste o link oficial se for outro
# no topo do arquivo já deve ter: import os
DOCES_URL = os.getenv("DOCES_URL", "https://bit.ly/doceschoko")  # ajuste se tiver link específico de doces

STORE_CLOSED_NOTICE = (
    "⚠️ *Aviso Importante*\n\n"
    "Loja *FECHADA* devido a manutencao na rede eletrica!\n"
    "Agradecemos a compreensao.\n\n"
    "Retornaremos ao atendimento na segunda-feira, a partir do meio-dia."
)


def is_store_closed() -> bool:
    return False


def get_store_closed_notice() -> str:
    raw_value = os.getenv("STORE_CLOSED_NOTICE", STORE_CLOSED_NOTICE).strip() or STORE_CLOSED_NOTICE
    return raw_value.replace("\\r\\n", "\n").replace("\\n", "\n")
