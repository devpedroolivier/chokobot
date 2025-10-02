import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.models import criar_tabelas
from app.routes import router
from app.db.init_db import ensure_views

app = FastAPI(title="Agente WhatsApp - Chokodelícia")

# Configura caminhos absolutos para static e templates
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

# Routers principais
app.include_router(router)

# Arquivos estáticos
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Templates
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Rotas separadas
from app.routes import clientes
app.include_router(clientes.router)

from app.routes import encomendas
app.include_router(encomendas.router)

from app.routes import web
app.include_router(web.router)  # ✅ habilita /painel


# Startup event → garante que DB e views estão criados
@app.on_event("startup")
def on_startup():
    criar_tabelas()
    ensure_views()
