import os
from dotenv import load_dotenv

load_dotenv()

ZAPI_TOKEN = os.getenv("ZAPI_TOKEN")
ZAPI_URL = os.getenv("ZAPI_URL")
