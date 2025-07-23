from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.routes import router

app = FastAPI(title="Agente WhatsApp - Chokodelícia")

app.include_router(router)

