from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.models import criar_tabelas
from app.routes import router
from app.db.init_db import ensure_views

app = FastAPI(title="Agente WhatsApp - Chokodelícia")

criar_tabelas()

app.include_router(router)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Rotas separadas
from app.routes import clientes
app.include_router(clientes.router)

from app.routes import encomendas
app.include_router(encomendas.router)

from app.routes import web
app.include_router(web.router)  # ✅ isso habilita /painel

@app.on_event("startup")
def on_startup():
    ensure_views()