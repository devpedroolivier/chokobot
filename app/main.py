import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import traceback
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.models import criar_tabelas
from app.api.router import router
from app.db.init_db import ensure_views

app = FastAPI(title="Agente WhatsApp - Chokodelícia")

# Caminhos absolutos
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")

# Registra rotas unificadas
app.include_router(router)

# Arquivos estáticos e templates
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Evento de inicialização
@app.on_event("startup")
def on_startup():
    criar_tabelas()
    ensure_views()


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    print(f"❌ Excecao nao tratada: {exc}")
    traceback.print_exc()
    return JSONResponse(status_code=500, content={"status": "error", "detail": "internal_error"})
