import os
from dotenv import load_dotenv

# Carrega variáveis do arquivo .env
load_dotenv()

# Recupera e valida variáveis
ZAPI_TOKEN = os.getenv("ZAPI_TOKEN")
ZAPI_URL = os.getenv("ZAPI_URL")

if not ZAPI_TOKEN or not ZAPI_URL:
    raise EnvironmentError("⚠️ Faltam variáveis no .env: ZAPI_TOKEN ou ZAPI_URL")
